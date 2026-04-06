"""auth.py 라우터 테스트 — 현재 OAuth 기반 API 구조에 맞춤."""

import pytest
from starlette import status

from app.core.security import create_refresh_token


@pytest.mark.asyncio
class TestAuthProviders:
    async def test_list_providers(self, client):
        response = await client.get("/api/v1/auth/providers")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "KAKAO" in data["data"]
        assert "GOOGLE" in data["data"]


@pytest.mark.asyncio
class TestDevLogin:
    async def test_dev_login_default_tester(self, client):
        """기본 테스터 계정으로 개발용 로그인."""
        from app.models.user import User

        tester = await User.get_or_none(email="tester@healthguide.dev")
        if tester is None:
            tester = await User.create(
                email="tester@healthguide.dev",
                password=None,
                nickname="테스터",
                name="개발테스터",
                provider_code="LOCAL",
            )
        response = await client.post("/api/v1/auth/dev/login")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    async def test_dev_login_nonexistent_email(self, client):
        """존재하지 않는 이메일로 개발용 로그인 시 404."""
        response = await client.post("/api/v1/auth/dev/login?email=nobody@test.com")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_dev_login_as_user(self, client, test_user):
        """특정 user_id로 개발용 로그인."""
        response = await client.post(f"/api/v1/auth/dev/login-as/{test_user.user_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["access_token"]

    async def test_dev_login_as_nonexistent(self, client):
        """존재하지 않는 user_id로 로그인 시 404."""
        response = await client.post("/api/v1/auth/dev/login-as/999999")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestOAuthLoginUrl:
    async def test_get_login_url_kakao(self, client):
        response = await client.get("/api/v1/auth/kakao/login")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["provider"] == "KAKAO"

    async def test_get_login_url_google(self, client):
        response = await client.get("/api/v1/auth/google/login")
        assert response.status_code == status.HTTP_200_OK

    async def test_get_login_url_invalid_provider(self, client):
        response = await client.get("/api/v1/auth/naver/login")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
class TestOAuthCallbackPost:
    async def test_callback_dev_bypass(self, client):
        """dev_bypass 코드로 OAuth 콜백 테스트."""
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
        response = await client.post(
            "/api/v1/auth/kakao/callback",
            json={"code": "dev_bypass"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"]["access_token"]


@pytest.mark.asyncio
class TestRefreshToken:
    async def test_refresh_success(self, client, test_user):
        """유효한 리프레시 토큰으로 갱신."""
        refresh = create_refresh_token({"sub": str(test_user.user_id), "role": "user"})
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["access_token"]
        assert data["data"]["refresh_token"]

    async def test_refresh_invalid_token(self, client):
        """잘못된 토큰으로 갱신 시 401."""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_with_access_token(self, client, test_user):
        """액세스 토큰을 리프레시 토큰으로 사용 시 401."""
        from app.core.security import create_access_token

        access = create_access_token({"sub": str(test_user.user_id), "role": "user"})
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": access},
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
