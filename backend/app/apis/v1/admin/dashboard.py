# app/apis/v1/admin/dashboard.py

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.services import admin_service

router = APIRouter()


@router.get("/summary")
async def dashboard_summary(admin: AdminUser = Depends(get_current_admin)):
    data = await admin_service.get_dashboard_summary()
    return {"status": 200, "message": "조회 성공", "data": data.model_dump()}


@router.get("/chart")
async def dashboard_chart(
    type: str = Query(...),
    period: str = Query(...),
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    admin: AdminUser = Depends(get_current_admin),
):
    if type not in ("SIGNUP", "OCR_SUCCESS", "CHAT_USAGE", "FILTER_BLOCKED"):
        return {"status": 400, "message": "유효하지 않은 조회 조건입니다.", "error": "INVALID_PARAMETER"}
    if period not in ("DAILY", "MONTHLY", "YEARLY"):
        return {"status": 400, "message": "유효하지 않은 조회 조건입니다.", "error": "INVALID_PARAMETER"}

    start = date.fromisoformat(startDate) if startDate else None
    end = date.fromisoformat(endDate) if endDate else None

    data = await admin_service.get_dashboard_chart(type, period, start, end)
    return {"status": 200, "message": "조회 성공", "data": data.model_dump()}
