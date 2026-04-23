# app/apis/v1/admin/errors.py

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.models.system_error_log import SystemErrorLog

router = APIRouter()


@router.get("")
async def list_errors(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    error_type: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
):
    qs = SystemErrorLog.all()

    if error_type:
        qs = qs.filter(error_type=error_type)
    if start_date:
        qs = qs.filter(created_at__gte=date.fromisoformat(start_date))
    if end_date:
        from datetime import timedelta

        qs = qs.filter(created_at__lt=date.fromisoformat(end_date) + timedelta(days=1))

    total = await qs.count()
    logs = await qs.offset((page - 1) * size).limit(size)

    items = [
        {
            "logId": log.log_id,
            "userId": log.user_id,
            "errorType": log.error_type,
            "errorMessage": log.error_message,
            "stackTrace": log.stack_trace,
            "requestUrl": log.request_url,
            "createdAt": log.created_at.isoformat(),
        }
        for log in logs
    ]

    return {
        "status": 200,
        "message": "조회 성공",
        "data": {"totalCount": total, "page": page, "size": size, "items": items},
    }


@router.get("/types")
async def list_error_types(admin: AdminUser = Depends(get_current_admin)):
    """발생한 오류 타입 목록 조회 (필터용)"""
    types = await SystemErrorLog.filter(error_type__not_isnull=True).distinct().values_list("error_type", flat=True)
    return {
        "status": 200,
        "message": "조회 성공",
        "data": sorted(types),
    }


@router.delete("/{log_id}")
async def delete_error_log(log_id: int, admin: AdminUser = Depends(get_current_admin)):
    log = await SystemErrorLog.get_or_none(log_id=log_id)
    if log is None:
        return {"status": 404, "message": "로그를 찾을 수 없습니다.", "error": "NOT_FOUND"}
    await log.delete()
    return {"status": 200, "message": "삭제되었습니다."}
