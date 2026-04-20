# app/apis/v1/admin/users.py


from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.services import admin_service

router = APIRouter()


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: str | None = Query(None),
    status: str = Query("ALL"),
    admin: AdminUser = Depends(get_current_admin),
):
    data = await admin_service.get_admin_user_list(page, size, keyword, status)
    return {"status": 200, "message": "조회 성공", "data": data.model_dump()}


@router.patch("/{user_id}/suspend")
async def suspend_user(user_id: int, admin: AdminUser = Depends(get_current_admin)):
    data = await admin_service.suspend_user(user_id)
    return {"status": 200, "message": "사용자가 정지 처리되었습니다.", "data": data.model_dump()}


@router.patch("/{user_id}/unsuspend")
async def unsuspend_user(user_id: int, admin: AdminUser = Depends(get_current_admin)):
    data = await admin_service.unsuspend_user(user_id)
    return {"status": 200, "message": "사용자 정지가 해제되었습니다.", "data": data.model_dump()}
