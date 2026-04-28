from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token
from app.models.user import User

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다.")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="토큰에 사용자 정보가 없습니다.")

    user = await User.get_or_none(user_id=int(user_id), is_suspended=False)
    if user is None:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")

    return user
