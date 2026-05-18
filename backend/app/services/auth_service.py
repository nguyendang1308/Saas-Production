from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient
from app.config import get_settings
from app.models.user import User

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError:
            return None

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
        user = await AuthService.get_user_by_email(db, email)
        if not user or not user.password_hash:
            return None
        if not AuthService.verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    async def register_user(db: AsyncSession, email: str, password: str) -> User:
        hashed = AuthService.hash_password(password)
        user = User(email=email, password_hash=hashed)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def verify_google_token(token: str) -> Optional[dict]:
        try:
            async with AsyncClient() as client:
                resp = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": token},
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                if data.get("aud") != settings.GOOGLE_CLIENT_ID:
                    return None
                return {
                    "email": data.get("email"),
                    "sub": data.get("sub"),
                    "name": data.get("name"),
                }
        except Exception:
            return None

    @staticmethod
    async def verify_github_token(token: str) -> Optional[dict]:
        try:
            async with AsyncClient() as client:
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(
                    "https://api.github.com/user",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return None
                user_data = resp.json()
                emails_resp = await client.get(
                    "https://api.github.com/user/emails",
                    headers=headers,
                    timeout=10.0,
                )
                primary_email = None
                if emails_resp.status_code == 200:
                    for e in emails_resp.json():
                        if e.get("primary"):
                            primary_email = e.get("email")
                            break
                if not primary_email:
                    primary_email = user_data.get("email")
                return {
                    "email": primary_email,
                    "sub": str(user_data.get("id")),
                    "name": user_data.get("login"),
                }
        except Exception:
            return None

    @staticmethod
    async def oauth_login_or_register(
        db: AsyncSession, provider: str, user_info: dict
    ) -> Optional[User]:
        email = user_info.get("email")
        oauth_id = user_info.get("sub")
        if not email or not oauth_id:
            return None

        result = await db.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id,
            )
        )
        user = result.scalar_one_or_none()
        if user:
            return user

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            await db.commit()
            await db.refresh(user)
            return user

        user = User(
            email=email,
            oauth_provider=provider,
            oauth_id=oauth_id,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
