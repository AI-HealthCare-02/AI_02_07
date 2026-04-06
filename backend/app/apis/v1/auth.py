# app/apis/v1/auth.py
# ──────────────────────────────────────────────
# 인증 API — OAuth 전용 (구글 + 카카오) + 개발용 바이패스
#
# 엔드포인트:
#   GET  /auth/providers              → 지원 OAuth 제공자 목록
#   GET  /auth/{provider}/login       → OAuth 로그인 URL 조회
#   GET  /auth/{provider}/callback    → OAuth 콜백 (서버 리다이렉트)
#   POST /auth/{provider}/callback    → OAuth 콜백 (프론트엔드 code 전달)
#   POST /auth/refresh                → JWT 토큰 갱신
#
# ⚠️ 개발 전용 (APP_ENV != production):
#   POST /auth/dev/login              → 테스터 계정으로 즉시 JWT 발급
#   POST /auth/dev/login-as/{user_id} → 특정 사용자로 즉시 JWT 발급
# ──────────────────────────────────────────────

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from jose import JWTError

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.dtos.auth_dto import (
    OAuthCallbackRequestDTO,
    OAuthLoginUrlResponseDTO,
    RefreshTokenRequestDTO,
    TokenResponseDTO,
)
from app.dtos.common_dto import ResponseDTO
from app.models.user import User
from app.services.auth_service import (
    dev_login,
    dev_login_as,
    get_oauth_login_url,
    process_oauth_callback,
)
from app.services.oauth_service import get_supported_providers

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================
# OAuth 제공자 목록
# ============================================================


@router.get(
    "/providers",
    response_model=ResponseDTO[list[str]],
    summary="지원 OAuth 제공자 목록",
)
async def list_providers():
    """
    지원하는 OAuth 제공자 목록을 반환합니다.
    현재: KAKAO, GOOGLE
    """
    providers = get_supported_providers()
    return ResponseDTO(success=True, data=providers)


# ============================================================
# OAuth 로그인 URL
# ============================================================


@router.get(
    "/{provider}/login",
    response_model=ResponseDTO[OAuthLoginUrlResponseDTO],
    summary="OAuth 로그인 URL 조회",
)
async def get_login_url(provider: str):
    """
    OAuth 제공자의 로그인 URL을 반환합니다.
    프론트엔드는 이 URL로 사용자를 리다이렉트하세요.

    Path Parameters:
        provider: "kakao" 또는 "google" (대소문자 무관)

    ⚠️ 개발 환경에서 OAuth 키가 미설정이면
    안내 메시지와 함께 개발용 로그인 API를 사용하라고 알려줍니다.
    """
    result = await get_oauth_login_url(provider)
    return ResponseDTO(success=True, data=result)


# ============================================================
# OAuth 콜백 — GET (서버 리다이렉트 방식)
# ============================================================


@router.get(
    "/{provider}/callback",
    summary="OAuth 콜백 (서버 리다이렉트)",
    response_class=RedirectResponse,
)
async def oauth_callback_redirect(
    provider: str,
    code: str = Query(..., description="OAuth authorization code"),
    state: str | None = Query(default=None, description="CSRF 방지용 state"),
    error: str | None = Query(default=None, description="OAuth 에러 코드"),
    error_description: str | None = Query(default=None, description="OAuth 에러 설명"),
):
    """
    OAuth 제공자가 리다이렉트하는 콜백 엔드포인트.
    성공 시 프론트엔드 URL로 토큰과 함께 리다이렉트합니다.
    """
    settings = get_settings()
    frontend_callback_url = f"{settings.FRONTEND_URL}/auth/callback"

    if error:
        logger.warning(f"OAuth 에러 ({provider}): {error} - {error_description}")
        params = urlencode(
            {
                "error": error,
                "message": error_description or "OAuth 인증에 실패했습니다.",
            }
        )
        return RedirectResponse(url=f"{frontend_callback_url}?{params}")

    try:
        tokens = await process_oauth_callback(
            provider_code=provider,
            code=code,
            state=state,
        )

        params = urlencode(
            {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "is_new_user": str(tokens.is_new_user).lower(),
            }
        )
        return RedirectResponse(url=f"{frontend_callback_url}?{params}")

    except HTTPException as e:
        params = urlencode({"error": "auth_failed", "message": e.detail})
        return RedirectResponse(url=f"{frontend_callback_url}?{params}")

    except Exception as e:
        logger.error(f"OAuth 콜백 처리 실패 ({provider}): {e}", exc_info=True)
        params = urlencode({"error": "server_error", "message": "로그인 처리 중 오류가 발생했습니다."})
        return RedirectResponse(url=f"{frontend_callback_url}?{params}")


# ============================================================
# OAuth 콜백 — POST (프론트엔드 code 전달 방식)
# ============================================================


@router.post(
    "/{provider}/callback",
    response_model=ResponseDTO[TokenResponseDTO],
    summary="OAuth 콜백 (프론트엔드 code 전달)",
)
async def oauth_callback_post(
    provider: str,
    body: OAuthCallbackRequestDTO,
):
    """
    프론트엔드가 OAuth authorization code를 전달하면 JWT를 발급합니다.

    ⚠️ 개발 팁:
        개발 환경에서 code를 "dev_bypass"로 보내면
        OAuth를 건너뛰고 테스터 계정으로 로그인됩니다.

        예시:
        POST /api/v1/auth/kakao/callback
        Body: {"code": "dev_bypass"}
    """
    tokens = await process_oauth_callback(
        provider_code=provider,
        code=body.code,
    )
    return ResponseDTO(success=True, message="로그인 성공", data=tokens)


# ============================================================
# JWT 토큰 갱신
# ============================================================


@router.post(
    "/refresh",
    response_model=ResponseDTO[TokenResponseDTO],
    summary="JWT 토큰 갱신",
)
async def refresh_token(body: RefreshTokenRequestDTO):
    """리프레시 토큰으로 새 액세스/리프레시 토큰을 발급합니다."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="리프레시 토큰이 아닙니다.",
            )
        user_id = payload.get("sub")
        role = payload.get("role", "user")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 리프레시 토큰입니다.",
        )

    if role == "admin":
        from app.models.admin import AdminUser

        admin = await AdminUser.get_or_none(admin_id=int(user_id))
        if admin is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="관리자를 찾을 수 없습니다.",
            )
        token_data = {"sub": str(admin.admin_id), "role": "admin"}
    else:
        user = await User.get_or_none(user_id=int(user_id))
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="사용자를 찾을 수 없습니다.",
            )
        token_data = {"sub": str(user.user_id), "role": "user"}

    tokens = TokenResponseDTO(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )
    return ResponseDTO(success=True, message="토큰 갱신 성공", data=tokens)


# ============================================================
# ⚠️ 개발 전용 엔드포인트 (APP_ENV != production)
# ============================================================
@router.post(
    "/dev/login",
    response_model=ResponseDTO[TokenResponseDTO],
    summary="[개발용] 테스터 계정 즉시 로그인",
    tags=["개발용"],
)
async def dev_login_endpoint(
    email: str | None = Query(
        default=None,
        description=("로그인할 이메일 주소. 비워두면 기본 테스터 계정을 사용합니다. 예시: tester@healthguide.dev"),
        examples=["tester@healthguide.dev"],
    ),
):
    """
    ⚠️ **개발 환경 전용** — 프로덕션에서는 403 에러를 반환합니다.

    OAuth 설정 없이 즉시 JWT 토큰을 발급받습니다.

    ## 사용법

    ### Swagger UI에서:
    1. 아래 "Try it out" 클릭
    2. email 칸은 **비워두거나** 이메일 주소만 입력 (예: tester@healthguide.dev)
    3. "Execute" 클릭
    4. 응답의 access_token 복사
    5. 페이지 상단 🔓 **Authorize** → `Bearer eyJ...` 붙여넣기

    ### curl에서:
    ```
    curl -X POST http://localhost:8000/api/v1/auth/dev/login
    curl -X POST "http://localhost:8000/api/v1/auth/dev/login?email=tester@healthguide.dev"
    ```
    """
    tokens = await dev_login(email=email)
    return ResponseDTO(success=True, message="🧪 개발용 로그인 성공", data=tokens)


@router.post(
    "/dev/login-as/{user_id}",
    response_model=ResponseDTO[TokenResponseDTO],
    summary="[개발용] 특정 사용자로 즉시 로그인",
    tags=["개발용"],
)
async def dev_login_as_endpoint(user_id: int):
    """
    ⚠️ **개발 환경 전용** — 프로덕션에서는 403 에러를 반환합니다.

    특정 user_id의 사용자로 즉시 로그인합니다.

    사용법:
        POST /api/v1/auth/dev/login-as/1
    """
    tokens = await dev_login_as(user_id=user_id)
    return ResponseDTO(success=True, message=f"🧪 user_id={user_id} 로 로그인 성공", data=tokens)
