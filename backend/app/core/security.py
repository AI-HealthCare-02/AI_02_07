# app/core/security.py
# ──────────────────────────────────────────────
# JWT 토큰 생성 / 검증 유틸리티
#
# DDL 반영:
#   - users 테이블: user_id로 토큰 생성 (role="user")
#   - admin_users 테이블: admin_id로 토큰 생성 (role="admin")
# OAuth 전용이므로 비밀번호 해싱 함수는 제거합니다.
# 관리자(admin_users) 비밀번호가 필요하면
# admin 서비스에서 별도 passlib 사용을 권장합니다.
# ──────────────────────────────────────────────
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from app.core.config import get_settings


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    JWT 액세스 토큰 생성.

    Args:
        data: 토큰 페이로드.
              일반 사용자: {"sub": str(user_id), "role": "user"}
              관리자:     {"sub": str(admin_id), "role": "admin"}
        expires_delta: 만료 시간. None이면 설정값 사용.

    Returns:
        인코딩된 JWT 문자열
    """
    settings = get_settings()
    to_encode = data.copy()

    if "role" not in to_encode:
        to_encode["role"] = "user"

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire, "type": "access"})

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    JWT 리프레시 토큰 생성.
    액세스 토큰보다 긴 수명을 가짐.
    """
    settings = get_settings()
    to_encode = data.copy()

    if "role" not in to_encode:
        to_encode["role"] = "user"

    if expires_delta is None:
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire, "type": "refresh"})

    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """
    JWT 토큰 디코딩 및 검증.

    Raises:
        JWTError: 토큰이 유효하지 않거나 만료된 경우

    Returns:
        디코딩된 페이로드:
        {
            "sub": "42",
            "role": "user" | "admin",
            "type": "access" | "refresh",
            "exp": 1234567890,
        }
    """
    settings = get_settings()
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
