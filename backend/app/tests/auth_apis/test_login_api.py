"""인증 API 테스트 — 개발용 로그인 (기존 signup/login → dev/login 으로 변경)"""

import pytest
from starlette import status


@pytest.mark.asyncio
class TestLoginAPI:
    async def test_dev_login_success(self, client):
        """기본 테스터 계정으로 개발용 로그인 성공."""
        from app.models.user import User

        await User.get_or_create(
            email="tester@healthguide.dev",
            defaults={
                "password": None,
                "nickname": "테스터",
                "name": "개발테스터",
                "provider_code": "LOCAL",
            },
        )

        response = await client.post("/api/v1/auth/dev/login")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    async def test_dev_login_with_email(self, client, test_user):
        """특정 이메일로 개발용 로그인 성공."""
        response = await client.post(
            f"/api/v1/auth/dev/login?email={test_user.email}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["access_token"]

    async def test_dev_login_nonexistent_email(self, client):
        """존재하지 않는 이메일로 개발용 로그인 시 404."""
        response = await client.post(
            "/api/v1/auth/dev/login?email=nonexistent@example.com"
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_dev_login_as_user(self, client, test_user):
        """특정 user_id로 개발용 로그인 성공."""
        response = await client.post(
            f"/api/v1/auth/dev/login-as/{test_user.user_id}"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["access_token"]

    async def test_dev_login_as_nonexistent(self, client):
        """존재하지 않는 user_id로 로그인 시 404."""
        response = await client.post("/api/v1/auth/dev/login-as/999999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
