"""인증 API 테스트 — JWT 토큰 갱신 (GET 쿠키 → POST body 방식으로 변경)"""

import pytest
from starlette import status

from app.core.security import create_access_token, create_refresh_token


@pytest.mark.asyncio
class TestJWTTokenRefreshAPI:
    async def test_token_refresh_success(self, client, test_user):
        """유효한 리프레시 토큰으로 갱신 성공."""
        refresh_token = create_refresh_token(
            {"sub": str(test_user.user_id), "role": "user"}
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    async def test_token_refresh_invalid_token(self, client):
        """잘못된 토큰으로 갱신 시 401."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_token_refresh_with_access_token(self, client, test_user):
        """액세스 토큰을 리프레시 토큰 자리에 넣으면 401."""
        access_token = create_access_token(
            {"sub": str(test_user.user_id), "role": "user"}
        )

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access_token},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_token_refresh_missing_body(self, client):
        """body 없이 요청 시 422."""
        response = await client.post("/api/v1/auth/refresh")
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
