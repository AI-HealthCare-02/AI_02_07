# app/services/auth_service.py
# ──────────────────────────────────────────────
# 인증 비즈니스 로직 — OAuth 전용 + 개발용 바이패스
#
# 수정 사항:
#   - seed_tester_account() 제거 (app/main.py로 이동)
#   - dev_login()에서 Tortoise 컨텍스트 문제 없음
#     (lifespan 내 init_db 완료 후 API 요청이 들어오므로)
# ──────────────────────────────────────────────

import logging
import secrets

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.security import create_access_token, create_refresh_token
from app.dtos.auth_dto import (
    OAuthLoginUrlResponseDTO,
    OAuthUserInfoDTO,
    TokenResponseDTO,
)
from app.models.user import User
from app.services.oauth_service import get_oauth_provider

logger = logging.getLogger(__name__)

_STATE_TTL = 300
_STATE_PREFIX = "oauth_state:"


# ============================================================
# 개발용 즉시 로그인
# ============================================================


async def dev_login(email: str | None = None) -> TokenResponseDTO:
    """
    개발용 즉시 로그인.
    OAuth 설정 없이 테스터 계정으로 바로 JWT를 발급합니다.

    Args:
        email: 로그인할 이메일. None이면 DEV_TESTER_EMAIL 사용.

    Raises:
        HTTPException 403: 프로덕션 환경
        HTTPException 404: 사용자 없음
    """
    settings = get_settings()

    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="프로덕션 환경에서는 개발용 로그인을 사용할 수 없습니다.",
        )

    target_email = email or settings.DEV_TESTER_EMAIL

    user = await User.get_or_none(email=target_email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"사용자를 찾을 수 없습니다: {target_email}\n"
                f"서버를 재시작하면 테스터 계정({settings.DEV_TESTER_EMAIL})이 자동 생성됩니다."
            ),
        )

    _check_account_status(user)

    tokens = TokenResponseDTO(
        access_token=create_access_token({"sub": str(user.user_id), "role": "user"}),
        refresh_token=create_refresh_token({"sub": str(user.user_id), "role": "user"}),
        is_new_user=False,
    )

    logger.info(f"🧪 개발용 로그인: user_id={user.user_id}, email={target_email}")
    return tokens


async def dev_login_as(user_id: int) -> TokenResponseDTO:
    """
    개발용 특정 사용자 로그인.

    Raises:
        HTTPException 403: 프로덕션 환경
        HTTPException 404: 사용자 없음
    """
    settings = get_settings()

    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="프로덕션 환경에서는 개발용 로그인을 사용할 수 없습니다.",
        )

    user = await User.get_or_none(user_id=user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"사용자를 찾을 수 없습니다: user_id={user_id}",
        )

    _check_account_status(user)

    tokens = TokenResponseDTO(
        access_token=create_access_token({"sub": str(user.user_id), "role": "user"}),
        refresh_token=create_refresh_token({"sub": str(user.user_id), "role": "user"}),
        is_new_user=False,
    )

    logger.info(f"🧪 개발용 대리 로그인: user_id={user.user_id}, email={user.email}")
    return tokens


# ============================================================
# OAuth 로그인 URL 생성
# ============================================================


async def get_oauth_login_url(provider_code: str) -> OAuthLoginUrlResponseDTO:
    """OAuth 로그인 URL을 생성합니다."""
    settings = get_settings()
    provider_upper = provider_code.upper()

    try:
        provider = get_oauth_provider(provider_upper)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 개발 환경에서 OAuth 키가 미설정인 경우 안내
    if settings.APP_ENV != "production":
        is_configured = _is_oauth_configured(provider_upper)
        if not is_configured:
            logger.warning(
                f"⚠️ {provider_upper} OAuth가 설정되지 않았습니다. "
                f"개발용 로그인을 사용하세요: POST /api/v1/auth/dev/login"
            )
            return OAuthLoginUrlResponseDTO(
                authorization_url=(f"⚠️ {provider_upper} OAuth 미설정. POST /api/v1/auth/dev/login 을 사용하세요."),
                provider=provider_upper,
            )

    # CSRF state 생성
    state = secrets.token_urlsafe(32)
    try:
        redis = get_redis()
        await redis.set(f"{_STATE_PREFIX}{state}", provider_upper, ex=_STATE_TTL)
    except Exception as e:
        logger.warning(f"OAuth state Redis 저장 실패 (무시): {e}")

    authorization_url = provider.get_authorization_url(state=state)

    return OAuthLoginUrlResponseDTO(
        authorization_url=authorization_url,
        provider=provider_upper,
    )


def _is_oauth_configured(provider_upper: str) -> bool:
    """OAuth 클라이언트 ID가 설정되어 있는지 확인."""
    settings = get_settings()
    if provider_upper == "KAKAO":
        return bool(settings.OAUTH_KAKAO_CLIENT_ID and settings.OAUTH_KAKAO_CLIENT_ID != "your-kakao-rest-api-key")
    elif provider_upper == "GOOGLE":
        return bool(settings.OAUTH_GOOGLE_CLIENT_ID and "your-google" not in settings.OAUTH_GOOGLE_CLIENT_ID)
    return False


# ============================================================
# OAuth 콜백 처리
# ============================================================


async def process_oauth_callback(
    provider_code: str,
    code: str,
    state: str | None = None,
) -> TokenResponseDTO:
    """OAuth 콜백 처리."""
    settings = get_settings()
    provider_upper = provider_code.upper()

    # ── 개발용 바이패스 ──
    if code == "dev_bypass" and settings.APP_ENV != "production":
        logger.info(f"🧪 개발용 OAuth 바이패스: provider={provider_upper}")
        return await dev_login()

    # ── State 검증 ──
    if state:
        try:
            redis = get_redis()
            stored_provider = await redis.get(f"{_STATE_PREFIX}{state}")
            if stored_provider is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth state가 만료되었거나 유효하지 않습니다.",
                )
            if stored_provider != provider_upper:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OAuth state의 제공자가 일치하지 않습니다.",
                )
            await redis.delete(f"{_STATE_PREFIX}{state}")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"OAuth state 검증 실패 (무시): {e}")

    # ── OAuth 제공자 ──
    try:
        provider = get_oauth_provider(provider_upper)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # ── code → access_token ──
    try:
        oauth_access_token = await provider.exchange_code_for_token(code)
    except Exception as e:
        logger.error(f"OAuth 토큰 교환 실패 ({provider_upper}): {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_upper} 인증 서버와 통신에 실패했습니다.",
        )

    # ── access_token → 사용자 정보 ──
    try:
        user_info: OAuthUserInfoDTO = await provider.get_user_info(oauth_access_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.error(f"OAuth 사용자 정보 조회 실패 ({provider_upper}): {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"{provider_upper}에서 사용자 정보를 가져오는데 실패했습니다.",
        )

    # ── DB 사용자 매칭/생성 ──
    user, is_new_user = await _find_or_create_user(user_info)

    # ── 계정 상태 확인 ──
    _check_account_status(user)

    # ── JWT 발급 ──
    tokens = TokenResponseDTO(
        access_token=create_access_token({"sub": str(user.user_id), "role": "user"}),
        refresh_token=create_refresh_token({"sub": str(user.user_id), "role": "user"}),
        is_new_user=is_new_user,
    )

    logger.info(f"OAuth 로그인 성공: user_id={user.user_id}, provider={provider_upper}, is_new={is_new_user}")
    return tokens


# ============================================================
# 내부 헬퍼
# ============================================================


async def _find_or_create_user(user_info: OAuthUserInfoDTO) -> tuple[User, bool]:
    """OAuth 사용자 정보로 기존 사용자 매칭 또는 신규 생성."""
    # 1단계: provider_code + provider_id
    user = await User.get_or_none(
        provider_code=user_info.provider_code,
        provider_id=user_info.provider_id,
    )
    if user is not None:
        return user, False

    # 2단계: email
    user = await User.get_or_none(email=user_info.email)
    if user is not None:
        user.provider_code = user_info.provider_code
        user.provider_id = user_info.provider_id
        await user.save()
        return user, False

    # 3단계: 신규 생성
    user = await User.create(
        email=user_info.email,
        password=None,
        nickname=user_info.nickname or user_info.email.split("@")[0],
        name=user_info.name or user_info.nickname or "사용자",
        provider_code=user_info.provider_code,
        provider_id=user_info.provider_id,
        gender_code=user_info.gender,
        birth_date=user_info.birth_date,
    )
    return user, True


def _check_account_status(user: User) -> None:
    """계정 상태 확인."""
    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="정지된 계정입니다. 관리자에게 문의하세요.",
        )
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="탈퇴한 계정입니다.",
        )
