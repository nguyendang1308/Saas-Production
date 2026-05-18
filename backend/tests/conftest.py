import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
import app.database as database_module
from app.database import Base, get_db as original_get_db
from app.middleware.auth import get_redis_client as original_get_redis_client
from app.models.user import User
from app.services.auth_service import AuthService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Fake redis storage for tests
_fake_redis_store: dict = {}
_fake_redis_ttl: dict = {}


class FakeRedis:
    async def get(self, key: str):
        now = asyncio.get_event_loop().time()
        if key in _fake_redis_ttl and _fake_redis_ttl[key] < now:
            _fake_redis_store.pop(key, None)
            _fake_redis_ttl.pop(key, None)
            return None
        return _fake_redis_store.get(key)

    async def setex(self, key: str, seconds: int, value: str):
        _fake_redis_store[key] = value
        _fake_redis_ttl[key] = asyncio.get_event_loop().time() + seconds

    async def delete(self, key: str):
        _fake_redis_store.pop(key, None)
        _fake_redis_ttl.pop(key, None)

    async def flushall(self):
        _fake_redis_store.clear()
        _fake_redis_ttl.clear()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        # rollback all changes after test
        await session.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    client = FakeRedis()
    await client.flushall()
    yield client
    await client.flushall()


@pytest_asyncio.fixture
async def client(db, redis_client):
    # Monkeypatch database engine/session for the whole app
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    test_async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    import app.middleware.auth as auth_middleware
    import app.routers.auth as auth_router

    original_engine = database_module.engine
    original_async_session_local = database_module.AsyncSessionLocal
    original_middleware_async_session = auth_middleware.AsyncSessionLocal
    original_get_redis_func = auth_middleware.get_redis_client

    database_module.engine = test_engine
    database_module.AsyncSessionLocal = test_async_session
    auth_middleware.AsyncSessionLocal = test_async_session

    # Monkeypatch get_redis_client to return fake redis
    async def fake_get_redis():
        return redis_client
    auth_middleware.get_redis_client = fake_get_redis
    auth_router.get_redis_client = fake_get_redis

    async def override_get_db():
        async with test_async_session() as session:
            yield session

    async def override_get_redis():
        return redis_client

    app.dependency_overrides[original_get_db] = override_get_db
    app.dependency_overrides[original_get_redis_client] = override_get_redis

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    database_module.engine = original_engine
    database_module.AsyncSessionLocal = original_async_session_local
    auth_middleware.AsyncSessionLocal = original_middleware_async_session
    auth_middleware.get_redis_client = original_get_redis_func
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
def auth_service():
    return AuthService()
