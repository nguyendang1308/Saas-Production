import pytest
from unittest.mock import AsyncMock, patch
from app.services.auth_service import AuthService


pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "test@example.com",
            "password": "password123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        assert data["role"] == "user"
        assert "id" in data

    async def test_register_duplicate_email(self, client):
        await client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "password": "password123"
        })
        resp = await client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "password": "password123"
        })
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_register_weak_password(self, client):
        resp = await client.post("/api/auth/register", json={
            "email": "weak@example.com",
            "password": "123"
        })
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client):
        await client.post("/api/auth/register", json={
            "email": "login@example.com",
            "password": "password123"
        })
        resp = await client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "password123"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "refresh_token" in resp.cookies

    async def test_login_invalid_credentials(self, client):
        await client.post("/api/auth/register", json={
            "email": "bad@example.com",
            "password": "password123"
        })
        resp = await client.post("/api/auth/login", json={
            "email": "bad@example.com",
            "password": "wrongpass"
        })
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client):
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "password123"
        })
        assert resp.status_code == 401


class TestRefresh:
    async def test_refresh_success(self, client):
        await client.post("/api/auth/register", json={
            "email": "refresh@example.com",
            "password": "password123"
        })
        login_resp = await client.post("/api/auth/login", json={
            "email": "refresh@example.com",
            "password": "password123"
        })
        refresh_cookie = login_resp.cookies.get("refresh_token")

        client.cookies.set("refresh_token", refresh_cookie)
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_missing_cookie(self, client):
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401
        assert "Missing refresh token" in resp.json()["detail"]

    async def test_refresh_invalid_token(self, client):
        client.cookies.set("refresh_token", "invalid.token.here")
        resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401
        assert "Invalid refresh token" in resp.json()["detail"]


class TestLogout:
    async def test_logout_success(self, client, redis_client):
        await client.post("/api/auth/register", json={
            "email": "logout@example.com",
            "password": "password123"
        })
        login_resp = await client.post("/api/auth/login", json={
            "email": "logout@example.com",
            "password": "password123"
        })
        access_token = login_resp.json()["access_token"]
        refresh_token = login_resp.cookies.get("refresh_token")

        client.headers["Authorization"] = f"Bearer {access_token}"
        client.cookies.set("refresh_token", refresh_token)
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
        assert "Logged out successfully" in resp.json()["message"]

        # Verify tokens are blacklisted
        blacklisted_access = await redis_client.get(f"blacklist:{access_token}")
        blacklisted_refresh = await redis_client.get(f"blacklist:{refresh_token}")
        assert blacklisted_access == "1"
        assert blacklisted_refresh == "1"


class TestMe:
    async def test_me_success(self, client):
        await client.post("/api/auth/register", json={
            "email": "me@example.com",
            "password": "password123"
        })
        login_resp = await client.post("/api/auth/login", json={
            "email": "me@example.com",
            "password": "password123"
        })
        access_token = login_resp.json()["access_token"]
        client.headers["Authorization"] = f"Bearer {access_token}"

        resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"

    async def test_me_unauthorized(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_invalid_token(self, client):
        client.headers["Authorization"] = "Bearer invalidtoken"
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


class TestOAuthGoogle:
    async def test_oauth_google_success(self, client):
        mock_info = {"email": "google@example.com", "sub": "google123", "name": "Google User"}
        with patch.object(AuthService, "verify_google_token", new=AsyncMock(return_value=mock_info)):
            resp = await client.post("/api/auth/oauth/google", json={"token": "fake_google_token"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_oauth_google_invalid_token(self, client):
        with patch.object(AuthService, "verify_google_token", new=AsyncMock(return_value=None)):
            resp = await client.post("/api/auth/oauth/google", json={"token": "bad_token"})
        assert resp.status_code == 401
        assert "Invalid Google token" in resp.json()["detail"]


class TestOAuthGitHub:
    async def test_oauth_github_success(self, client):
        mock_info = {"email": "github@example.com", "sub": "github456", "name": "githubuser"}
        with patch.object(AuthService, "verify_github_token", new=AsyncMock(return_value=mock_info)):
            resp = await client.post("/api/auth/oauth/github", json={"token": "fake_github_token"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_oauth_github_invalid_token(self, client):
        with patch.object(AuthService, "verify_github_token", new=AsyncMock(return_value=None)):
            resp = await client.post("/api/auth/oauth/github", json={"token": "bad_token"})
        assert resp.status_code == 401
        assert "Invalid GitHub token" in resp.json()["detail"]


class TestRateLimit:
    async def test_login_rate_limit(self, client):
        await client.post("/api/auth/register", json={
            "email": "ratelimit@example.com",
            "password": "password123"
        })
        # First 5 should succeed
        for i in range(5):
            resp = await client.post("/api/auth/login", json={
                "email": "ratelimit@example.com",
                "password": "password123"
            })
            assert resp.status_code == 200, f"Request {i+1} should succeed"

        # 6th should be rate limited
        resp = await client.post("/api/auth/login", json={
            "email": "ratelimit@example.com",
            "password": "password123"
        })
        assert resp.status_code == 429
