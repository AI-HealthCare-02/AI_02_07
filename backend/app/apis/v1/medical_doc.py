# app/apis/v1/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 API — 이승원 담당
#
# 엔드포인트:
#   POST /medical-doc/analyze       → 의료 문서 이미지 분석 + DB 저장
#   GET  /medical-doc/results       → 분석 결과 목록 조회
#   GET  /medical-doc/results/{id}  → 분석 결과 단건 조회
#   DELETE /medical-doc/results/{id} → 분석 결과 삭제
# ──────────────────────────────────────────────

import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from ai_worker.tasks.medical_doc import analyze_medical_document
from app.core.dependencies import get_current_user
from app.dtos.common_dto import ResponseDTO
from app.models.user import User
from app.services import medical_doc_service

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_PDF_SIZE = 20 * 1024 * 1024


# ============================================================
# 의료 문서 분석 + DB 저장
# ============================================================

@router.post(
    "/analyze",
    response_model=ResponseDTO[dict],
    summary="의료 문서 분석",
)
async def analyze_document(
    file1: UploadFile = File(description="의료 문서 이미지 1 (필수)"),
    file2: UploadFile | None = File(default=None, description="의료 문서 이미지 2 (선택, 뒷면 등)"),
    file3: UploadFile | None = File(default=None, description="의료 문서 이미지 3 (선택)"),
    file4: UploadFile | None = File(default=None, description="의료 문서 이미지 4 (선택)"),
    file5: UploadFile | None = File(default=None, description="의료 문서 이미지 5 (선택)"),
    document_type: str = Form(default="자동인식", description="문서 종류: 처방전 / 진료기록 / 약봉투 / 자동인식"),
    current_user: User = Depends(get_current_user),
):
    """
    의료 문서 이미지를 업로드하면 AI가 분석하여 구조화된 JSON을 반환하고 DB에 저장합니다.

    - **file1**: 이미지 파일 (JPG, PNG, PDF) 필수
    - **file2~5**: 추가 이미지 (선택, 앞면/뒷면 등)
    - **document_type**: 처방전 / 진료기록 / 약봉투 / 자동인식 (기본값)
    """

    files = [f for f in [file1, file2, file3, file4, file5] if f is not None]

    # 검진결과 제거 — 처방전 / 진료기록 / 약봉투 / 자동인식만 지원
    valid_doc_types = {"처방전", "진료기록", "약봉투", "자동인식"}
    valid_doc_types = {"처방전", "진료기록", "약봉투", "검진결과", "자동인식"}
    if document_type not in valid_doc_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"유효하지 않은 문서 종류입니다. 선택 가능: {sorted(valid_doc_types)}",
        )

    image_bytes_list = []
    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{file.filename}: 지원하지 않는 파일 형식입니다. (JPG, PNG, PDF만 가능)",
            )
        file_bytes = await file.read()
        max_size = MAX_PDF_SIZE if file.content_type == "application/pdf" else MAX_IMAGE_SIZE
        if len(file_bytes) > max_size:
            max_mb = max_size // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{file.filename}: 파일 크기 초과 (최대 {max_mb}MB)",
            )
        image_bytes_list.append(file_bytes)
        logger.info(f"파일 수신: {file.filename} ({len(file_bytes)} bytes)")

    job = await medical_doc_service.create_analysis_job(
        user=current_user,
        document_type=document_type,
    )

    start_time = time.time()
    try:
        result = await analyze_medical_document(
            image_bytes_list=image_bytes_list,
            document_type=document_type,
        )
        processing_time = time.time() - start_time
        ocr_raw_text = result.get("raw_summary", "")

        saved_result = await medical_doc_service.save_analysis_result(
            job=job,
            user=current_user,
            analysis_result=result,
            ocr_raw_text=ocr_raw_text,
            processing_time=processing_time,
        )

        result["doc_result_id"] = saved_result.doc_result_id
        result["processing_time"] = round(processing_time, 2)

    except Exception as e:
        await medical_doc_service.fail_analysis_job(job, str(e))
        logger.error(f"의료 문서 분석 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="문서 분석 중 오류가 발생했습니다.",
        )

    return ResponseDTO(success=True, message="분석 완료", data=result)


# ============================================================
# 분석 결과 목록 조회
# ============================================================

@router.get(
    "/results",
    response_model=ResponseDTO[dict],
    summary="분석 결과 목록 조회",
)
async def list_analysis_results(
    page: int = 1,
    page_size: int = 10,
    current_user: User = Depends(get_current_user),
):
    """사용자의 의료 문서 분석 결과 목록을 조회합니다."""
    results = await medical_doc_service.get_analysis_results(
        user=current_user,
        page=page,
        page_size=page_size,
    )
    return ResponseDTO(success=True, data=results)


# ============================================================
# 분석 결과 단건 조회
# ============================================================

@router.get(
    "/results/{doc_result_id}",
    response_model=ResponseDTO[dict],
    summary="분석 결과 단건 조회",
)
async def get_analysis_result(
    doc_result_id: int,
    current_user: User = Depends(get_current_user),
):
    """특정 분석 결과를 조회합니다."""
    result = await medical_doc_service.get_analysis_result(
        user=current_user,
        doc_result_id=doc_result_id,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="분석 결과를 찾을 수 없습니다.",
        )


    # analysis_json 에서 상세 데이터 추출
    analysis = result.analysis_json or {}

    return ResponseDTO(
        success=True,
        data={
            "doc_result_id": result.doc_result_id,
            "document_type": medical_doc_service.DOC_TYPE_NAME_MAP.get(result.doc_type_code, result.doc_type_code),
            "hospital_name": analysis.get("hospital_name"),
            "visit_date": analysis.get("visit_date"),           # prescription_date → visit_date
            "diagnosis_name": analysis.get("diagnosis_name"),   # diagnosis → diagnosis_name
            "medications": analysis.get("medications", []),
            "medication_schedule": analysis.get("medication_schedule"),
            "prescription_date": analysis.get("prescription_date"),
            "diagnosis": analysis.get("diagnosis"),
            "medications": analysis.get("medications", []),
            "cautions": analysis.get("cautions"),
            "overall_confidence": result.overall_confidence,
            "raw_summary": result.raw_summary,
            "ocr_raw_text": result.ocr_raw_text,
            "created_at": result.created_at.isoformat(),
        },
    )


# ============================================================
# 분석 결과 삭제
# ============================================================

@router.delete(
    "/results/{doc_result_id}",
    response_model=ResponseDTO,
    summary="분석 결과 삭제",
)
async def delete_analysis_result(
    doc_result_id: int,
    current_user: User = Depends(get_current_user),
):
    """분석 결과를 삭제합니다 (소프트 삭제)."""
    deleted = await medical_doc_service.delete_analysis_result(
        user=current_user,
        doc_result_id=doc_result_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="분석 결과를 찾을 수 없습니다.",
        )
    return ResponseDTO(success=True, message="분석 결과가 삭제되었습니다.")