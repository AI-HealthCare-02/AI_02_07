"""사용자 API 테스트 — 프로필 조회/수정 (OAuth 기반 + ResponseDTO 래퍼 반영)"""

import pytest
from starlette import status


@pytest.mark.asyncio
class TestUserMeApis:
    async def test_get_user_me_success(self, client, test_user, auth_headers):
        """내 프로필 조회 성공."""
        response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["email"] == test_user.email
        assert data["data"]["name"] == test_user.name

    async def test_update_user_me_success(self, client, auth_headers):
        """내 프로필 수정 성공."""
        response = await client.patch(
            "/api/v1/users/me",
            json={"name": "수정후"},
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "수정후"

    async def test_get_user_me_unauthorized(self, client):
        """인증 없이 프로필 조회 시 401/403."""
        response = await client.get("/api/v1/users/me")
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
