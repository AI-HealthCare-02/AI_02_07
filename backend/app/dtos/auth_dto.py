# app/dtos/auth_dto.py
# ──────────────────────────────────────────────
# 인증 관련 DTO — OAuth 전용
#
# 흐름:
#   1. 프론트엔드가 GET /auth/{provider}/login 호출 → OAuth 로그인 URL 반환
#   2. 사용자가 OAuth 제공자에서 로그인 + 동의
#   3. 제공자가 redirect_uri로 code와 함께 리다이렉트
#   4. 백엔드 GET /auth/{provider}/callback?code=xxx 에서
#      code → access_token 교환 → 사용자 정보 조회 → JWT 발급
# ──────────────────────────────────────────────

from pydantic import BaseModel, EmailStr, Field


class OAuthLoginUrlResponseDTO(BaseModel):
    """
    OAuth 로그인 URL 응답.
    프론트엔드는 이 URL로 사용자를 리다이렉트합니다.
    """

    authorization_url: str = Field(description="OAuth 제공자 로그인 URL")
    provider: str = Field(description="OAuth 제공자 (KAKAO, GOOGLE)")


class OAuthCallbackRequestDTO(BaseModel):
    """
    OAuth 콜백에서 전달받는 authorization code.
    프론트엔드가 code를 받아서 백엔드에 POST로 전달하는 경우 사용.
    """

    code: str = Field(description="OAuth 제공자로부터 받은 authorization code")


class TokenResponseDTO(BaseModel):
    """JWT 토큰 응답 (로그인/콜백 성공 시)"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = Field(
        default=False,
        description="True이면 신규 가입된 사용자 (추가 정보 입력 안내 필요)",
    )


class RefreshTokenRequestDTO(BaseModel):
    """토큰 갱신 요청"""

    refresh_token: str


class OAuthUserInfoDTO(BaseModel):
    """
    OAuth 제공자에서 가져온 사용자 정보 (내부 DTO).
    oauth_service에서 제공자별 응답을 이 형태로 정규화합니다.
    """

    provider_code: str  # KAKAO, GOOGLE
    provider_id: str  # OAuth 제공자에서의 고유 ID
    email: str  # 이메일
    nickname: str | None = None
    name: str | None = None
