"""인증 API 테스트 — OAuth 제공자 및 콜백 (기존 signup → OAuth 방식으로 변경)"""

import pytest
from starlette import status


@pytest.mark.asyncio
class TestOAuthProviders:
    async def test_list_providers(self, client):
        """지원 OAuth 제공자 목록 조회."""
        response = await client.get("/api/v1/auth/providers")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "KAKAO" in data["data"]
        assert "GOOGLE" in data["data"]

    async def test_get_login_url_kakao(self, client):
        """카카오 OAuth 로그인 URL 조회."""
        response = await client.get("/api/v1/auth/kakao/login")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["provider"] == "KAKAO"

    async def test_get_login_url_google(self, client):
        """구글 OAuth 로그인 URL 조회."""
        response = await client.get("/api/v1/auth/google/login")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["data"]["provider"] == "GOOGLE"

    async def test_get_login_url_invalid_provider(self, client):
        """지원하지 않는 제공자 요청 시 400."""
        response = await client.get("/api/v1/auth/naver/login")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
class TestOAuthCallback:
    async def test_callback_dev_bypass(self, client):
        """dev_bypass 코드로 OAuth 콜백 — 테스터 계정 JWT 발급."""
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
        data = response.json()
        assert data["success"] is True
        assert data["data"]["access_token"]
        assert data["data"]["refresh_token"]
