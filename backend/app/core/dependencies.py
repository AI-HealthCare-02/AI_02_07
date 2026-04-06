# app/core/dependencies.py
# ──────────────────────────────────────────────
# FastAPI 의존성 주입 (Depends)
#
# DDL 구조 반영:
#   - users 테이블 사용 (user_id PK, is_suspended, deleted_at)
#   - admin_users 테이블은 별도 (admin_id PK)
# ──────────────────────────────────────────────

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token
from app.models.admin import AdminUser
from app.models.user import User

# Bearer 토큰 스키마 (Swagger UI에 자물쇠 아이콘 표시)
security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> User:
    """
    JWT 토큰에서 현재 인증된 일반 사용자를 조회합니다.

    토큰 payload: {"sub": "<user_id>", "type": "access", "role": "user"}

    Raises:
        HTTPException 401: 토큰 유효하지 않음, 사용자 없음
        HTTPException 403: 정지된 계정
        HTTPException 410: 탈퇴한 계정
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        role: str | None = payload.get("role", "user")

        if user_id is None or token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="유효하지 않은 토큰입니다.",
            )

        # 관리자 토큰으로 일반 사용자 API 접근 방지
        if role == "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 토큰으로는 일반 사용자 API에 접근할 수 없습니다.",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 검증에 실패했습니다.",
        )

    # DB에서 사용자 조회
    user = await User.get_or_none(user_id=int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 계정 상태 확인
    if user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="탈퇴한 계정입니다.",
        )

    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="정지된 계정입니다.",
        )

    return user


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> AdminUser:
    """
    JWT 토큰에서 현재 인증된 관리자를 조회합니다.
    admin_users 테이블에서 조회합니다.

    토큰 payload: {"sub": "<admin_id>", "type": "access", "role": "admin"}

    Raises:
        HTTPException 401: 토큰 유효하지 않음
        HTTPException 403: 관리자 토큰이 아님
    """
    token = credentials.credentials
    try:
        payload = decode_token(token)
        admin_id: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")
        role: str | None = payload.get("role")

        if admin_id is None or token_type != "access" or role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 권한이 필요합니다.",
            )

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰 검증에 실패했습니다.",
        )

    admin = await AdminUser.get_or_none(admin_id=int(admin_id))
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="관리자를 찾을 수 없습니다.",
        )

    return admin
