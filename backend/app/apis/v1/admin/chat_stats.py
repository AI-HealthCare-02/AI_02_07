# app/apis/v1/admin/chat_stats.py

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_admin
from app.models.admin import AdminUser
from app.services import chat_stats_service

router = APIRouter()


@router.get("/stats", summary="채팅 통계 목록 조회")
async def get_chat_stats(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    room_id: int | None = Query(None),
    model_name: str | None = Query(None),
    filter_result: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
):
    import logging

    try:
        data = await chat_stats_service.get_stats(
            page=page,
            size=size,
            room_id=room_id,
            model_name=model_name,
            filter_result=filter_result,
            start_date=start_date,
            end_date=end_date,
        )
        return {"status": 200, "message": "조회 성공", "data": data}
    except Exception as e:
        logging.getLogger(__name__).error("[chat_stats] 조회 오류: %s", e, exc_info=True)
        raise


@router.get("/stats/download", summary="채팅 통계 CSV 다운로드")
async def download_chat_stats_csv(
    room_id: int | None = Query(None),
    model_name: str | None = Query(None),
    filter_result: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
):
    rows = await chat_stats_service.get_all_stats(
        room_id=room_id,
        model_name=model_name,
        filter_result=filter_result,
        start_date=start_date,
        end_date=end_date,
    )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "message_id",
            "room_id",
            "model_name",
            "input_text",
            "output_text",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cost_usd",
            "latency_ms",
            "filter_result",
            "created_at",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": "attachment; filename=chat_stats.csv"},
    )
