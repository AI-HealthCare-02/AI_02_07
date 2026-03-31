# app/services/oauth_service.py
# ──────────────────────────────────────────────
# OAuth 제공자별 토큰 교환 및 사용자 정보 조회 서비스
#
# 각 제공자(카카오, 구글)의 OAuth 2.0 흐름을 처리합니다:
#   1. get_authorization_url()  → 로그인 URL 생성
#   2. exchange_code_for_token() → code → access_token 교환
#   3. get_user_info()          → access_token → 사용자 정보 조회
#
# 새로운 OAuth 제공자 추가 시:
#   1. 이 파일에 새 제공자 클래스를 추가
#   2. _PROVIDERS 딕셔너리에 등록
#   3. envs/.local.env에 CLIENT_ID/SECRET/REDIRECT_URI 추가
#   4. common_code 테이블에 PROVIDER 그룹에 코드 추가
# ──────────────────────────────────────────────

import logging
from abc import ABC, abstractmethod
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.dtos.auth_dto import OAuthUserInfoDTO

logger = logging.getLogger(__name__)


# ============================================================
# OAuth 제공자 추상 클래스
# ============================================================


class OAuthProvider(ABC):
    """
    OAuth 제공자 추상 베이스 클래스.
    새 제공자를 추가하려면 이 클래스를 상속하고
    3개의 추상 메서드를 구현하세요.
    """

    @abstractmethod
    def get_authorization_url(self, state: str | None = None) -> str:
        """
        OAuth 로그인 URL을 생성합니다.

        Args:
            state: CSRF 방지용 state 파라미터 (선택)

        Returns:
            OAuth 제공자 로그인 페이지 URL
        """
        ...

    @abstractmethod
    async def exchange_code_for_token(self, code: str) -> str:
        """
        Authorization code를 access_token으로 교환합니다.

        Args:
            code: OAuth 콜백에서 받은 authorization code

        Returns:
            access_token 문자열

        Raises:
            httpx.HTTPStatusError: 토큰 교환 실패
        """
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfoDTO:
        """
        access_token으로 사용자 정보를 조회합니다.

        Args:
            access_token: OAuth 제공자 access_token

        Returns:
            정규화된 사용자 정보 DTO
        """
        ...


# ============================================================
# 카카오 OAuth
# ============================================================


class KakaoOAuthProvider(OAuthProvider):
    """
    카카오 OAuth 2.0 구현.

    카카오 개발자 문서: https://developers.kakao.com/docs/latest/ko/kakaologin/rest-api

    필요한 동의 항목 (카카오 개발자 콘솔에서 설정):
        - profile_nickname (닉네임)
        - account_email (이메일)
    """

    # 카카오 OAuth 엔드포인트
    AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    USER_INFO_URL = "https://kapi.kakao.com/v2/user/me"

    def get_authorization_url(self, state: str | None = None) -> str:
        """카카오 로그인 URL 생성"""
        settings = get_settings()
        params = {
            "client_id": settings.OAUTH_KAKAO_CLIENT_ID,
            "redirect_uri": settings.OAUTH_KAKAO_REDIRECT_URI,
            "response_type": "code",
            # 카카오에서 제공하는 동의 항목
            # profile_nickname: 닉네임
            # account_email: 이메일 (필수 동의 설정 필요)
            "scope": "profile_nickname,account_email",
        }
        if state:
            params["state"] = state

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> str:
        """카카오: code → access_token 교환"""
        settings = get_settings()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.OAUTH_KAKAO_CLIENT_ID,
                    "client_secret": settings.OAUTH_KAKAO_CLIENT_SECRET,
                    "redirect_uri": settings.OAUTH_KAKAO_REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        access_token = data.get("access_token")
        if not access_token:
            logger.error(f"카카오 토큰 교환 실패: {data}")
            raise ValueError("카카오 access_token을 받지 못했습니다.")

        logger.info("카카오 토큰 교환 성공")
        return access_token

    async def get_user_info(self, access_token: str) -> OAuthUserInfoDTO:
        """카카오: access_token → 사용자 정보 조회"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

        # 카카오 응답 구조:
        # {
        #   "id": 123456789,                          ← provider_id
        #   "kakao_account": {
        #     "email": "user@example.com",             ← email
        #     "profile": {
        #       "nickname": "홍길동"                    ← nickname
        #     }
        #   }
        # }
        kakao_account = data.get("kakao_account", {})
        profile = kakao_account.get("profile", {})

        provider_id = str(data.get("id", ""))
        email = kakao_account.get("email", "")
        nickname = profile.get("nickname", "")

        if not provider_id:
            raise ValueError("카카오에서 사용자 ID를 받지 못했습니다.")
        if not email:
            raise ValueError(
                "카카오에서 이메일을 받지 못했습니다. "
                "카카오 개발자 콘솔에서 이메일 동의 항목을 필수로 설정해주세요."
            )

        logger.info(f"카카오 사용자 정보 조회 성공: provider_id={provider_id}")

        return OAuthUserInfoDTO(
            provider_code="KAKAO",
            provider_id=provider_id,
            email=email,
            nickname=nickname or None,
            name=nickname or None,  # 카카오는 실명이 없으므로 닉네임으로 대체
        )


# ============================================================
# 구글 OAuth
# ============================================================


class GoogleOAuthProvider(OAuthProvider):
    """
    구글 OAuth 2.0 구현.

    구글 개발자 문서: https://developers.google.com/identity/protocols/oauth2/web-server

    필요한 스코프:
        - openid (기본)
        - email (이메일)
        - profile (이름, 프로필 사진)
    """

    # 구글 OAuth 엔드포인트
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USER_INFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def get_authorization_url(self, state: str | None = None) -> str:
        """구글 로그인 URL 생성"""
        settings = get_settings()
        params = {
            "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
            "redirect_uri": settings.OAUTH_GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            # 매번 동의 화면을 보여주려면 "consent" 사용
            # 이미 동의한 사용자는 바로 로그인하려면 제거
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> str:
        """구글: code → access_token 교환"""
        settings = get_settings()

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.OAUTH_GOOGLE_CLIENT_ID,
                    "client_secret": settings.OAUTH_GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.OAUTH_GOOGLE_REDIRECT_URI,
                    "code": code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            data = response.json()

        access_token = data.get("access_token")
        if not access_token:
            logger.error(f"구글 토큰 교환 실패: {data}")
            raise ValueError("구글 access_token을 받지 못했습니다.")

        logger.info("구글 토큰 교환 성공")
        return access_token

    async def get_user_info(self, access_token: str) -> OAuthUserInfoDTO:
        """구글: access_token → 사용자 정보 조회"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.USER_INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

        # 구글 응답 구조:
        # {
        #   "id": "1234567890",        ← provider_id
        #   "email": "user@gmail.com", ← email
        #   "name": "홍길동",           ← name (실명)
        #   "given_name": "길동",
        #   "family_name": "홍",
        #   "picture": "https://...",   ← 프로필 이미지 URL (필요하면 저장)
        # }
        provider_id = str(data.get("id", ""))
        email = data.get("email", "")
        name = data.get("name", "")

        if not provider_id:
            raise ValueError("구글에서 사용자 ID를 받지 못했습니다.")
        if not email:
            raise ValueError("구글에서 이메일을 받지 못했습니다.")

        logger.info(f"구글 사용자 정보 조회 성공: provider_id={provider_id}")

        return OAuthUserInfoDTO(
            provider_code="GOOGLE",
            provider_id=provider_id,
            email=email,
            nickname=name or None,
            name=name or None,
        )


# ============================================================
# 제공자 레지스트리
# ============================================================

# 제공자 코드 → 인스턴스 매핑
# 새로운 OAuth 제공자를 추가할 때 여기에 등록하세요.
_PROVIDERS: dict[str, OAuthProvider] = {
    "KAKAO": KakaoOAuthProvider(),
    "GOOGLE": GoogleOAuthProvider(),
}


def get_oauth_provider(provider_code: str) -> OAuthProvider:
    """
    제공자 코드로 OAuth 제공자 인스턴스를 반환합니다.

    Args:
        provider_code: "KAKAO" 또는 "GOOGLE" (대소문자 무관)

    Returns:
        OAuthProvider 인스턴스

    Raises:
        ValueError: 지원하지 않는 제공자

    사용 예시:
        provider = get_oauth_provider("KAKAO")
        url = provider.get_authorization_url()
    """
    provider = _PROVIDERS.get(provider_code.upper())
    if provider is None:
        supported = ", ".join(_PROVIDERS.keys())
        raise ValueError(
            f"지원하지 않는 OAuth 제공자입니다: {provider_code}. "
            f"지원 제공자: {supported}"
        )
    return provider


def get_supported_providers() -> list[str]:
    """지원하는 OAuth 제공자 목록을 반환합니다."""
    return list(_PROVIDERS.keys())
