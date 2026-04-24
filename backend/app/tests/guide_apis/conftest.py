from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.user_id = 1
    return user


@pytest_asyncio.fixture
async def async_client(mock_user) -> AsyncGenerator[AsyncClient]:
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
        from app.core.dependencies import get_current_user as core_get_current_user
        from app.dependencies.security import get_current_user as security_get_current_user
        from app.main import app

        # ✅ 수정: 두 경로의 get_current_user 모두 override
        app.dependency_overrides[security_get_current_user] = lambda: mock_user
        app.dependency_overrides[core_get_current_user] = lambda: mock_user

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.clear()
