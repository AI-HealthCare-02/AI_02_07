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

from app.core.s3 import delete_file, generate_s3_key, upload_file
from app.dependencies.security import get_current_user
from app.dtos.common_dto import PaginatedResponseDTO, PaginationDTO, ResponseDTO
from app.models.pill_analysis import PillAnalysisHistory, UploadedFile
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
    from app.core.config import get_settings

    settings = get_settings()

    validate_image(front_image)
    validate_image(back_image)

    front_bytes = await read_and_validate_size(front_image)
    back_bytes = await read_and_validate_size(back_image)

    # S3 업로드
    s3_keys = []
    for img_bytes, original_name in [
        (front_bytes, front_image.filename or "front.jpg"),
        (back_bytes, back_image.filename or "back.jpg"),
    ]:
        s3_key = generate_s3_key("pill-images", original_name, user_id=current_user.user_id)
        await upload_file(io.BytesIO(img_bytes), s3_key, content_type="image/jpeg")
        s3_keys.append(s3_key)

    # uploaded_file ORM 저장
    uploaded = await UploadedFile.create(
        user=current_user,
        original_name=front_image.filename or "front.jpg",
        stored_name=s3_keys[0].split("/")[-1],
        s3_bucket=settings.AWS_S3_BUCKET_NAME,
        s3_key=s3_keys[0],
        s3_url=f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{s3_keys[0]}",
        content_type="image/jpeg",
        file_size=len(front_bytes),
        file_extension=".jpg",
        file_category_grp="FILE_CATEGORY",
        file_category_code="IMG_PILL",
    )

    # ── 환경별 분기: 로컬은 직접 처리, 프로덕션은 Worker 큐 ──
    if settings.APP_ENV != "production":
        import asyncpg
        from openai import AsyncOpenAI

        from ai_worker.tasks.pill_analysis import (
            extract_pill_features,
            fetch_drug_info_from_db,
            find_drug_by_imprint,
            preprocess_image,
        )

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        image_b64_list = [preprocess_image(front_bytes), preprocess_image(back_bytes)]
        db_url = settings.database_url.replace("asyncpg://", "postgresql://")
        db_conn = await asyncpg.connect(db_url)

        try:
            # 1단계: GPT Vision - 각인/색상/모양만 추출
            features = await extract_pill_features(client, image_b64_list, settings.OPENAI_MODEL)
            logger.info("1단계 완료: %s", features)

            if not features.get("is_pill", True):
                product_name = "알약 이미지가 아닙니다"
                analysis = await PillAnalysisHistory.create(
                    user=current_user,
                    file=uploaded,
                    product_name=product_name,
                    gpt_model_version=settings.OPENAI_MODEL,
                )
                return ResponseDTO(
                    success=True,
                    message="알약 이미지가 아닙니다.",
                    data={"analysis_id": analysis.analysis_id, "product_name": product_name},
                )

            # 2단계: imprint RAG - 약품 특정
            matched_drug = await find_drug_by_imprint(db_conn, client, features)

            if matched_drug is None:
                parts = [v for v in [features.get("print_front"), features.get("print_back")] if v]
                product_name = f"각인: {', '.join(parts)} (DB 미매칭)" if parts else "식별 불가"
                analysis = await PillAnalysisHistory.create(
                    user=current_user,
                    file=uploaded,
                    product_name=product_name,
                    gpt_model_version=settings.OPENAI_MODEL,
                )
                return ResponseDTO(
                    success=True,
                    message="알약 분석이 완료되었습니다.",
                    data={"analysis_id": analysis.analysis_id, "product_name": product_name},
                )

            # 3단계: 허가정보 DB 직접 조회 (GPT 재호출 없음)
            db_info = await fetch_drug_info_from_db(db_conn, matched_drug["item_seq"])

        finally:
            await db_conn.close()

        analysis = await PillAnalysisHistory.create(
            user=current_user,
            file=uploaded,
            product_name=matched_drug["item_name"],
            active_ingredients=db_info.get("ingredient"),
            efficacy=db_info.get("efficacy"),
            caution=db_info.get("caution"),
            gpt_model_version=settings.OPENAI_MODEL,
        )

        return ResponseDTO(
            success=True,
            message="알약 분석이 완료되었습니다.",
            data={"analysis_id": analysis.analysis_id, "product_name": analysis.product_name},
        )

    # 프로덕션: Worker 태스크 큐에 등록 후 결과 대기
    task_id = await enqueue_task(
        task_type=TaskType.PILL_ANALYSIS,
        payload={"user_id": current_user.user_id, "file_id": uploaded.file_id, "s3_keys": s3_keys},
        user_id=current_user.user_id,
    )

    task_result = await wait_for_task_result(task_id, timeout=120)

    if not task_result or task_result.get("status") == "failed":
        raise HTTPException(status_code=500, detail="알약 분석에 실패했습니다.")

    result = task_result.get("result", {})
    return ResponseDTO(
        success=True,
        message="알약 분석이 완료되었습니다.",
        data={"analysis_id": result.get("analysis_id"), "product_name": result.get("product_name")},
    )


@router.get("", summary="알약 분석 목록 조회")
async def list_pill_analyses(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="제품명 검색"),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponseDTO:
    """사용자의 알약 분석 이력을 조회합니다."""
    qs = PillAnalysisHistory.filter(user=current_user)

    if search:
        qs = qs.filter(product_name__icontains=search)

    total = await qs.count()
    rows = await qs.offset((page - 1) * size).limit(size)

    total_pages = max((total + size - 1) // size, 1)

    return PaginatedResponseDTO(
        success=True,
        message="조회 성공",
        data=[
            {
                "analysis_id": r.analysis_id,
                "product_name": r.product_name,
                "efficacy": r.efficacy,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for r in rows
        ],
        pagination=PaginationDTO(page=page, size=size, total=total, total_pages=total_pages),
    )


@router.get("/{analysis_id}", summary="알약 분석 상세 조회")
async def get_pill_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    """알약 분석 상세 정보를 조회합니다."""
    row = await PillAnalysisHistory.get_or_none(analysis_id=analysis_id, user=current_user)

    if row is None:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    return ResponseDTO(
        success=True,
        message="조회 성공",
        data={
            "analysis_id": row.analysis_id,
            "product_name": row.product_name,
            "active_ingredients": row.active_ingredients,
            "efficacy": row.efficacy,
            "usage_method": row.usage_method,
            "warning": row.warning,
            "caution": row.caution,
            "interactions": row.interactions,
            "side_effects": row.side_effects,
            "storage_method": row.storage_method,
            "gpt_model_version": row.gpt_model_version,
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@router.delete("/{analysis_id}", summary="알약 분석 삭제")
async def delete_pill_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    """알약 분석 이력을 삭제합니다."""
    row = await PillAnalysisHistory.get_or_none(analysis_id=analysis_id, user=current_user)

    if row is None:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    # S3 파일 삭제
    uploaded = await UploadedFile.get_or_none(file_id=row.file_id)
    if uploaded:
        await delete_file(uploaded.s3_key)
        await uploaded.delete()

    await row.delete()

    return ResponseDTO(success=True, message="삭제되었습니다.")
