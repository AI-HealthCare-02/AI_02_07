# app/apis/v1/pill_analysis.py
import io
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict

from app.core.s3 import delete_file, generate_presigned_url, generate_s3_key, upload_file
from app.dependencies.security import get_current_user
from app.dtos.common_dto import PaginatedResponseDTO, PaginationDTO, ResponseDTO
from app.models.pill_analysis import PillAnalysisHistory, UploadedFile
from app.models.user import User
from app.services.task_queue import TaskType, enqueue_task, wait_for_task_result

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}

UNIDENTIFIED_KEYWORDS = ("식별 불가", "미매칭", "알약 이미지가 아닙니다", "여러 알약", "분석 실패")


class PillAnalysisResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class PillAnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    analysis_id: int
    product_name: str | None
    efficacy: str | None
    created_at: str


def validate_image(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다. (지원: JPEG, PNG, WEBP, HEIC)")


async def read_and_validate_size(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail=f"이미지 용량이 5MB를 초과합니다: {len(data) / 1024 / 1024:.1f}MB")
    return data


@router.post("/analyze", summary="알약 이미지 분석")
async def analyze_pill(
    front_image: UploadFile = File(..., description="알약 이미지 (앞면 또는 앞뒤 모두 포함)"),
    back_image: UploadFile | None = File(None, description="알약 뒷면 이미지 (선택)"),
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    from app.core.config import get_settings

    settings = get_settings()

    validate_image(front_image)
    front_bytes = await read_and_validate_size(front_image)

    back_bytes: bytes | None = None
    if back_image and back_image.filename:
        validate_image(back_image)
        back_bytes = await read_and_validate_size(back_image)

    # S3 업로드
    s3_keys: list[str] = []
    for img_bytes, original_name in [
        (front_bytes, front_image.filename or "front.jpg"),
        *([(back_bytes, back_image.filename or "back.jpg")] if back_bytes and back_image else []),
    ]:
        s3_key = generate_s3_key("pill-images", original_name, user_id=current_user.user_id)
        await upload_file(io.BytesIO(img_bytes), s3_key, content_type="image/jpeg")
        s3_keys.append(s3_key)

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

    if settings.APP_ENV != "production":
        import asyncpg
        from openai import AsyncOpenAI

        from ai_worker.tasks.pill_analysis import (
            extract_imprint_ocr,
            extract_pill_features,
            fetch_drug_info_from_db,
            find_drug_by_imprint,
            preprocess_image,
        )

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        image_bytes_pairs = [front_bytes] + ([back_bytes] if back_bytes else [])
        b64_list, proc_bytes_list = zip(*[preprocess_image(b) for b in image_bytes_pairs], strict=False)

        import asyncio

        ocr_texts: list[str | None] = list(await asyncio.gather(*[extract_imprint_ocr(b) for b in proc_bytes_list]))

        db_url = settings.database_url.replace("asyncpg://", "postgresql://")
        db_conn = await asyncpg.connect(db_url)

        try:
            features = await extract_pill_features(client, list(b64_list), ocr_texts, settings.OPENAI_MODEL)
            logger.info("1단계 완료: %s", features)

            if not features.get("is_pill", True):
                analysis = await PillAnalysisHistory.create(
                    user=current_user,
                    file=uploaded,
                    product_name="알약 이미지가 아닙니다",
                    gpt_model_version=settings.OPENAI_MODEL,
                )
                return ResponseDTO(
                    success=True,
                    message="알약 이미지가 아닙니다.",
                    data={"analysis_id": analysis.analysis_id, "product_name": analysis.product_name},
                )

            if features.get("multiple_pills"):
                analysis = await PillAnalysisHistory.create(
                    user=current_user,
                    file=uploaded,
                    product_name="여러 알약 감지 - 분석 실패",
                    gpt_model_version=settings.OPENAI_MODEL,
                )
                return ResponseDTO(
                    success=True,
                    message="여러 알약이 감지되어 분석할 수 없습니다.",
                    data={"analysis_id": analysis.analysis_id, "product_name": analysis.product_name},
                )

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
    row = await PillAnalysisHistory.get_or_none(analysis_id=analysis_id, user=current_user)
    if row is None:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    from app.core.config import get_settings

    settings = get_settings()
    uploaded = await UploadedFile.get_or_none(file_id=row.file_id)
    image_url = generate_presigned_url(uploaded.s3_key, expiration=3600) if uploaded else None

    product_name = row.product_name or ""
    is_unidentified = any(kw in product_name for kw in UNIDENTIFIED_KEYWORDS)

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
            "image_url": image_url,
            "is_unidentified": is_unidentified,
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@router.delete("/{analysis_id}", summary="알약 분석 삭제")
async def delete_pill_analysis(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
) -> ResponseDTO:
    row = await PillAnalysisHistory.get_or_none(analysis_id=analysis_id, user=current_user)
    if row is None:
        raise HTTPException(status_code=404, detail="분석 결과를 찾을 수 없습니다.")

    uploaded = await UploadedFile.get_or_none(file_id=row.file_id)
    if uploaded:
        await delete_file(uploaded.s3_key)
        await uploaded.delete()

    await row.delete()
    return ResponseDTO(success=True, message="삭제되었습니다.")
