# app/apis/v1/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 API — 이승원 담당
#
# 엔드포인트:
#   POST /medical-doc/analyze  → 의료 문서 이미지 분석
# ──────────────────────────────────────────────

import logging
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.dependencies.security import get_current_user
from app.dtos.common_dto import ResponseDTO
from app.models.user import User
from ai_worker.tasks.medical_doc import analyze_medical_document
from fastapi import Depends

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_PDF_SIZE = 20 * 1024 * 1024     # 20MB


# ============================================================
# 의료 문서 분석
# ============================================================

@router.post(
    "/analyze",
    response_model=ResponseDTO[dict],
    summary="의료 문서 분석",
)
async def analyze_document(
    files: Annotated[list[UploadFile], File(description="의료 문서 이미지 (JPG, PNG, PDF) 최대 5개")],
    document_type: Annotated[str, Form(description="문서 종류: 처방전 / 진료기록 / 약봉투 / 검진결과 / 자동인식")] = "자동인식",
    current_user: User = Depends(get_current_user),
):
    """
    의료 문서 이미지를 업로드하면 AI가 분석하여 구조화된 JSON을 반환합니다.

    - **files**: 이미지 파일 (JPG, PNG, PDF), 최대 5개 (앞면/뒷면 등)
    - **document_type**: 처방전 / 진료기록 / 약봉투 / 검진결과 / 자동인식 (기본값)
    """

    # 파일 개수 제한
    if len(files) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="파일은 최대 5개까지 업로드 가능합니다.",
        )

    # 문서 종류 유효성 검사
    valid_doc_types = {"처방전", "진료기록", "약봉투", "검진결과", "자동인식"}
    if document_type not in valid_doc_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 문서 종류입니다. 선택 가능: {valid_doc_types}",
        )

    image_bytes_list = []

    for file in files:
        # 파일 형식 검사
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{file.filename}: 지원하지 않는 파일 형식입니다. (JPG, PNG, PDF만 가능)",
            )

        # 파일 읽기
        file_bytes = await file.read()

        # 파일 크기 검사
        max_size = MAX_PDF_SIZE if file.content_type == "application/pdf" else MAX_IMAGE_SIZE
        if len(file_bytes) > max_size:
            max_mb = max_size // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{file.filename}: 파일 크기 초과 (최대 {max_mb}MB)",
            )

        image_bytes_list.append(file_bytes)
        logger.info(f"파일 수신: {file.filename} ({len(file_bytes)} bytes)")

    # 분석 실행
    try:
        result = await analyze_medical_document(
            image_bytes_list=image_bytes_list,
            document_type=document_type,
        )
    except Exception as e:
        logger.error(f"의료 문서 분석 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="문서 분석 중 오류가 발생했습니다.",
        )

    return ResponseDTO(success=True, message="분석 완료", data=result)