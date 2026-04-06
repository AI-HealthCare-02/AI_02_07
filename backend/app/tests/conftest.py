import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from tortoise import Tortoise

from app.core.security import create_access_token
from app.db.databases import MODELS

TEST_BASE_URL = "http://test"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_db():
    """SQLite 인메모리 DB로 Tortoise ORM 초기화 (Redis mock 포함)."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_redis.scan_iter = AsyncMock(
        return_value=AsyncMock(__aiter__=lambda s: s, __anext__=AsyncMock(side_effect=StopAsyncIteration))
    )

    with (
        patch("app.core.redis.init_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch("app.core.redis._redis_client", mock_redis),
    ):
        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": MODELS},
        )
        await Tortoise.generate_schemas()
        yield
        await Tortoise.close_connections()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    """Redis를 mock한 상태로 FastAPI 테스트 클라이언트 생성."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with (
        patch("app.core.redis.init_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("app.core.redis.get_redis", return_value=mock_redis),
        patch("app.core.redis._redis_client", mock_redis),
    ):
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url=TEST_BASE_URL) as ac:
            yield ac


@pytest_asyncio.fixture
async def test_user():
    """테스트용 사용자 생성."""
    from app.models.user import User

    user = await User.create(
        email="test_router@healthguide.dev",
        password=None,
        nickname="테스트유저",
        name="테스트",
        provider_code="LOCAL",
    )
    yield user
    await user.delete()


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict[str, str]:
    """인증된 사용자의 Authorization 헤더."""
    token = create_access_token({"sub": str(test_user.user_id), "role": "user"})
    return {"Authorization": f"Bearer {token}"}
