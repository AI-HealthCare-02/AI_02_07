from app.models.user import User
from fastapi import HTTPException

async def get_current_user() -> User:
    user = await User.filter(is_suspended=False).first()
    if not user:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")
    return user