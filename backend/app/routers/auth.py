from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.middleware.auth import get_db, get_redis_client
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    OAuthRequest,
    MessageResponse,
)
from app.services.auth_service import AuthService
from app.middleware.auth import require_auth
from app.models.user import User
from app.config import get_settings

settings = get_settings()
router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"


async def _login_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:login:{client_ip}"
    redis_client = await get_redis_client()
    current = await redis_client.get(key)
    count = int(current) if current else 0
    if count >= 5:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    await redis_client.setex(key, 60, str(count + 1))


@router.post("/register", response_model=UserResponse)
async def register(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await AuthService.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = await AuthService.register_user(db, payload.email, payload.password)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    payload: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    _rate_limit=Depends(_login_rate_limit),
):
    user = await AuthService.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = AuthService.create_access_token({"sub": str(user.id)})
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    payload = AuthService.decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Check blacklist
    redis_client = await get_redis_client()
    is_blacklisted = await redis_client.get(f"blacklist:{refresh_token}")
    if is_blacklisted:
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    access_token = AuthService.create_access_token({"sub": user_id})
    new_refresh_token = AuthService.create_refresh_token({"sub": user_id})

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # Blacklist old refresh token
    await redis_client.setex(
        f"blacklist:{refresh_token}",
        settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        "1",
    )

    return TokenResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(require_auth),
):
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    response.delete_cookie(key=REFRESH_COOKIE_NAME)

    redis_client = await get_redis_client()

    # Blacklist access token
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:]
        await redis_client.setex(
            f"blacklist:{access_token}",
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "1",
        )

    # Blacklist refresh token
    if refresh_token:
        await redis_client.setex(
            f"blacklist:{refresh_token}",
            settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            "1",
        )

    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(require_auth)):
    return current_user


@router.post("/oauth/google", response_model=TokenResponse)
async def oauth_google(
    payload: OAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user_info = await AuthService.verify_google_token(payload.token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid Google token")

    user = await AuthService.oauth_login_or_register(db, "google", user_info)
    if not user:
        raise HTTPException(status_code=400, detail="OAuth login failed")

    access_token = AuthService.create_access_token({"sub": str(user.id)})
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(access_token=access_token)


@router.post("/oauth/github", response_model=TokenResponse)
async def oauth_github(
    payload: OAuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    user_info = await AuthService.verify_github_token(payload.token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid GitHub token")

    user = await AuthService.oauth_login_or_register(db, "github", user_info)
    if not user:
        raise HTTPException(status_code=400, detail="OAuth login failed")

    access_token = AuthService.create_access_token({"sub": str(user.id)})
    refresh_token = AuthService.create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    return TokenResponse(access_token=access_token)
