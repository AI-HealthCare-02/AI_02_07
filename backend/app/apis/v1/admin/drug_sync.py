# app/apis/v1/admin/drug_sync.py
# ──────────────────────────────────────────────
# 관리자 — 공공데이터 의약품 동기화 API
# ──────────────────────────────────────────────

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import get_current_admin
from app.dtos.common_dto import ResponseDTO

router = APIRouter(prefix="/drug-sync", tags=["관리자 - 약품 동기화"])
logger = logging.getLogger(__name__)


class SyncRequest(BaseModel):
    since_days: int | None = None   # 최근 N일 변경분
    since_date: str | None = None   # YYYYMMDD 이후 변경분
    item_seq: str | None = None     # 특정 item_seq만
    dry_run: bool = False           # True면 DB 변경 없이 시뮬레이션


class SyncResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    failed: int
    dry_run: bool
    since_date: str | None


@router.post("", summary="공공데이터 의약품 증분 동기화 (수동 실행)")
async def trigger_drug_sync(
    req: SyncRequest,
    _admin=Depends(get_current_admin),
) -> ResponseDTO:
    """
    공공데이터 API에서 변경된 의약품 데이터를 동기화합니다.

    - `since_days`: 최근 N일 변경분만 동기화 (예: 7 → 최근 7일)
    - `since_date`: YYYYMMDD 이후 변경분 동기화 (예: "20250101")
    - `item_seq`: 특정 약품만 강제 업데이트
    - `dry_run`: True면 실제 DB 변경 없이 결과만 확인
    """
    from app.core.config import get_settings

    settings = get_settings()

    if not getattr(settings, "PUBLIC_DATA_SERVICE_KEY", None):
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_DATA_SERVICE_KEY 환경변수가 설정되지 않았습니다.",
        )

    since = None
    if req.since_days:
        since = (date.today() - timedelta(days=req.since_days)).strftime("%Y%m%d")
    elif req.since_date:
        since = req.since_date

    try:
        # sync_drug_data.py의 sync 함수를 직접 호출
        import sys
        from pathlib import Path

        scripts_path = str(Path(__file__).resolve().parents[4] / "scripts")
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)

        from sync_drug_data import sync  # type: ignore

        stats = await sync(
            since_date=since,
            item_seq=req.item_seq,
            dry_run=req.dry_run,
        )

        return ResponseDTO(
            success=True,
            message=f"동기화 {'시뮬레이션' if req.dry_run else '완료'}",
            data=SyncResult(
                inserted=stats.get("inserted", 0),
                updated=stats.get("updated", 0),
                skipped=stats.get("skipped", 0),
                failed=stats.get("failed", 0),
                dry_run=req.dry_run,
                since_date=since,
            ).model_dump(),
        )

    except Exception as e:
        logger.error("약품 동기화 실패: %s", e)
        raise HTTPException(status_code=500, detail=f"동기화 실패: {e}")


@router.get("/logs", summary="동기화 이력 조회")
async def get_sync_logs(
    limit: int = Query(20, ge=1, le=100),
    _admin=Depends(get_current_admin),
) -> ResponseDTO:
    """최근 동기화 이력을 조회합니다."""
    import asyncpg

    from app.core.config import get_settings

    settings = get_settings()

    try:
        conn = await asyncpg.connect(
            settings.database_url.replace("asyncpg://", "postgresql://")
        )
        rows = await conn.fetch(
            """
            SELECT id, sync_type, since_date, inserted, updated, skipped, failed,
                   dry_run, synced_at
            FROM drug_sync_log
            ORDER BY synced_at DESC
            LIMIT $1
            """,
            limit,
        )
        await conn.close()

        return ResponseDTO(
            success=True,
            message="조회 성공",
            data=[
                {
                    "id": r["id"],
                    "sync_type": r["sync_type"],
                    "since_date": r["since_date"],
                    "inserted": r["inserted"],
                    "updated": r["updated"],
                    "skipped": r["skipped"],
                    "failed": r["failed"],
                    "dry_run": r["dry_run"],
                    "synced_at": r["synced_at"].strftime("%Y-%m-%d %H:%M:%S"),
                }
                for r in rows
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이력 조회 실패: {e}")
