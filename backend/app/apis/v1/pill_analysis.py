# app/apis/v1/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 API
#
# POST   /pill-analysis/analyze     이미지 업로드 + 분석 요청
# GET    /pill-analysis             목록 조회 (검색)
# GET    /pill-analysis/{id}        상세 조회
# DELETE /pill-analysis/{id}        삭제
# ──────────────────────────────────────────────

import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from tortoise import Tortoise

from app.core.s3 import delete_file, generate_s3_key, upload_file
from app.dependencies.security import get_current_user
from app.dtos.common_dto import PaginatedResponseDTO, PaginationDTO, ResponseDTO
from app.models.user import User
from app.services.task_queue import TaskType, enqueue_task, wait_for_task_result

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


# ── DTO ───────────────────────────────────────


class PillAnalysisResult(BaseModel):
    analysis_id: int
    product_name: str | None
    active_ingredients: str | None
    efficacy: str | None
    usage_method: str | None
    warning: str | None
    caution: str | None
    interactions: str | None
    side_effects: str | None
    storage_method: str | None
    gpt_model_version: str | None
    created_at: str

    class Config:
        from_attributes = True


class PillAnalysisSummary(BaseModel):
    analysis_id: int
    product_name: str | None
    efficacy: str | None
    created_at: str

    class Config:
        from_attributes = True


# ── 이미지 유효성 검사 ─────────────────────────


def validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="지원하지 않는 이미지 형식입니다. (지원: JPEG, PNG, WEBP, HEIC)",
        )


async def read_and_validate_size(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"이미지 용량이 5MB를 초과합니다: {len(data) / 1024 / 1024:.1f}MB",
        )
    return data


# ── 엔드포인트 ────────────────────────────────


@router.post("/analyze", summary="알약 이미지 분석")
async def analyze_pill(
    front_image: UploadFile = File(..., description="알약 앞면 이미지"),
    back_image: UploadFile = File(..., description="알약 뒷면 이미지"),
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    """
    알약 앞/뒷면 이미지 2장을 업로드하여 분석합니다.

    - 이미지 포맷: JPEG, PNG, WEBP, HEIC
    - 이미지 용량: 각 5MB 이하
    - 분석 결과는 pill_analysis_history에 저장됩니다.
    """
    # 유효성 검사
    validate_image(front_image)
    validate_image(back_image)

    front_bytes = await read_and_validate_size(front_image)
    back_bytes = await read_and_validate_size(back_image)

    user_id = current_user.user_id

    # S3 업로드
    s3_keys = []
    for _i, (img_bytes, original_name) in enumerate(
        [
            (front_bytes, front_image.filename or "front.jpg"),
            (back_bytes, back_image.filename or "back.jpg"),
        ]
    ):
        s3_key = generate_s3_key("pill-images", original_name, user_id=user_id)
        await upload_file(
            io.BytesIO(img_bytes),
            s3_key,
            content_type="image/jpeg",
        )
        s3_keys.append(s3_key)

    # uploaded_file 테이블에 저장
    conn = Tortoise.get_connection("default")
    settings_row = await conn.execute_query_dict(
        "SELECT AWS_S3_BUCKET_NAME FROM pg_settings LIMIT 0"  # dummy
    )

    from app.core.config import get_settings

    settings = get_settings()

    file_row = await conn.execute_query_dict(
        """
        INSERT INTO uploaded_file (
            user_id, original_name, stored_name, s3_bucket, s3_key, s3_url,
            content_type, file_size, file_extension,
            file_category_grp, file_category_code
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'FILE_CATEGORY','PILL_IMG')
        RETURNING file_id
        """,
        [
            user_id,
            front_image.filename or "front.jpg",
            s3_keys[0].split("/")[-1],
            settings.AWS_S3_BUCKET_NAME,
            s3_keys[0],
            f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{s3_keys[0]}",
            "image/jpeg",
            len(front_bytes),
            ".jpg",
        ],
    )
    file_id = file_row[0]["file_id"]

    # 워커 태스크 큐에 등록
    task_id = await enqueue_task(
        task_type=TaskType.PILL_ANALYSIS,
        payload={
            "user_id": user_id,
            "file_id": file_id,
            "s3_keys": s3_keys,
        },
        user_id=user_id,
    )

    # 결과 대기 (최대 60초)
    task_result = await wait_for_task_result(task_id, timeout=60)

    if not task_result or task_result.get("status") == "failed":
        raise HTTPException(status_code=500, detail="알약 분석에 실패했습니다.")

    result = task_result.get("result", {})
    analysis_id = result.get("analysis_id")

    return ResponseDTO(
        success=True,
        message="알약 분석이 완료되었습니다.",
        data={"analysis_id": analysis_id, "product_name": result.get("product_name")},
    )


@router.get("", summary="알약 분석 목록 조회")
async def list_pill_analyses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="제품명 검색"),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponseDTO:
    """사용자의 알약 분석 이력을 조회합니다."""
    user_id = current_user.user_id
    offset = (page - 1) * size

    conn = Tortoise.get_connection("default")

    where = "WHERE user_id = $1"
    params: list = [user_id]

    if search:
        params.append(f"%{search}%")
        where += f" AND product_name ILIKE ${len(params)}"

    total_row = await conn.execute_query_dict(f"SELECT COUNT(*) AS cnt FROM pill_analysis_history {where}", params)
    total = total_row[0]["cnt"]

    params += [size, offset]
    rows = await conn.execute_query_dict(
        f"""
        SELECT analysis_id, product_name, efficacy,
               to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM pill_analysis_history
        {where}
        ORDER BY created_at DESC
        LIMIT ${len(params) - 1} OFFSET ${len(params)}
        """,
        params,
    )

    total_pages = (total + size - 1) // size

    return PaginatedResponseDTO(
        success=True,
        message="조회 성공",
        data=rows,
        pagination=PaginationDTO(page=page, size=size, total=total, total_pages=total_pages),
    )


@router.get("/{analysis_id}", summary="알약 분석 상세 조회")
async def get_pill_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    """알약 분석 상세 정보를 조회합니다."""
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        """
        SELECT analysis_id, product_name, active_ingredients, efficacy,
               usage_method, warning, caution, interactions,
               side_effects, storage_method, gpt_model_version,
               to_char(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at
        FROM pill_analysis_history
        WHERE analysis_id = $1 AND user_id = $2
        """,
        [analysis_id, current_user.user_id],
    )

    if not rows:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    return ResponseDTO(success=True, message="조회 성공", data=rows[0])


@router.delete("/{analysis_id}", summary="알약 분석 삭제")
async def delete_pill_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    """알약 분석 이력을 삭제합니다."""
    conn = Tortoise.get_connection("default")

    # 소유권 확인 + file_id 조회
    rows = await conn.execute_query_dict(
        "SELECT file_id FROM pill_analysis_history WHERE analysis_id = $1 AND user_id = $2",
        [analysis_id, current_user.user_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    file_id = rows[0]["file_id"]

    # S3 키 조회 후 삭제
    file_rows = await conn.execute_query_dict("SELECT s3_key FROM uploaded_file WHERE file_id = $1", [file_id])
    if file_rows:
        await delete_file(file_rows[0]["s3_key"])

    # DB 삭제 (CASCADE로 pill_analysis_history도 삭제)
    await conn.execute_query("DELETE FROM pill_analysis_history WHERE analysis_id = $1", [analysis_id])

    return ResponseDTO(success=True, message="삭제되었습니다.")
