# app/apis/v1/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 API — 이승원 담당
#
# 엔드포인트:
#   POST   /medical-doc/analyze           → 의료 문서 이미지 분석 + DB 저장
#   GET    /medical-doc/results           → 분석 결과 목록 조회
#   GET    /medical-doc/results/{id}      → 분석 결과 단건 조회
#   PATCH  /medical-doc/results/{id}      → 분석 결과 미확인 항목 수정
#   DELETE /medical-doc/results/{id}      → 분석 결과 삭제
# ──────────────────────────────────────────────

import logging
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ai_worker.tasks.medical_doc import analyze_medical_document
from app.core.dependencies import get_current_user
from app.dtos.common_dto import ResponseDTO
from app.models.medical_doc import DocAnalysisResult
from app.models.user import User
from app.services import medical_doc_service

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_PDF_SIZE = 20 * 1024 * 1024


# ============================================================
# DTO (PATCH용)
# ============================================================


class MedicationUpdate(BaseModel):
    medication_index: int  # medications 배열에서 몇 번째 약인지 (0부터 시작)
    medication_name: str | None = None  # ✅ 추가: 약품명
    dosage: str | None = None  # 투약량 (예: 1정, 500mg)
    frequency: str | None = None  # 복용횟수 (예: 1일 2회)
    timing: str | None = None  # 복용시점 (예: 식후, 식전, 취침 전)
    duration_days: int | None = None  # ✅ 추가: 총투약일수
    instructions: str | None = None  # 기타 복용 지시사항
    # ✅ 추가: 복약 시간대 (아침/점심/저녁/취침전 체크박스 선택값)
    # 예: ["아침", "저녁"] — 식사 기준 복용시점(timing)과 별개
    daily_slots: list[str] | None = None


class DocResultPatchRequest(BaseModel):
    # ✅ 추가: 기본 정보 수정 필드
    hospital_name: str | None = None  # 의료기관명
    visit_date: str | None = None  # 진료일 (YYYY-MM-DD)
    diagnosis_name: str | None = None  # 진단명
    # 약물별 수정
    medications: list[MedicationUpdate] = []


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

    valid_doc_types = {"처방전", "진료기록", "약봉투", "자동인식"}
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

        if result.get("error") == "non_medical_document":
            await medical_doc_service.fail_analysis_job(job, result["message"])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["message"],
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

    except HTTPException:
        raise
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

    analysis = result.analysis_json or {}

    return ResponseDTO(
        success=True,
        data={
            "doc_result_id": result.doc_result_id,
            "document_type": medical_doc_service.DOC_TYPE_NAME_MAP.get(result.doc_type_code, result.doc_type_code),
            "hospital_name": analysis.get("hospital_name"),
            "visit_date": analysis.get("visit_date"),
            "diagnosis_name": analysis.get("diagnosis_name"),
            "medications": analysis.get("medications", []),
            "medication_schedule": analysis.get("medication_schedule"),
            "cautions": analysis.get("cautions"),
            "overall_confidence": result.overall_confidence,
            "raw_summary": result.raw_summary,
            "ocr_raw_text": result.ocr_raw_text,
            "created_at": result.created_at.isoformat(),
        },
    )


# ============================================================
# 분석 결과 미확인 항목 수정 (PATCH)
# ============================================================


@router.patch(
    "/results/{doc_result_id}",
    response_model=ResponseDTO[dict],
    summary="분석 결과 미확인 항목 수정",
)
async def patch_analysis_result(
    doc_result_id: int,
    req: DocResultPatchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    분석 결과에서 미확인(null) 항목을 사용자가 직접 수정합니다.
    확인 완료 버튼 클릭 전 호출하여 수정 내용을 저장합니다.

    - **hospital_name**: 의료기관명
    - **visit_date**: 진료일 (YYYY-MM-DD)
    - **diagnosis_name**: 진단명
    - **medication_index**: medications 배열 인덱스 (0부터 시작)
    - **medication_name**: 약품명
    - **dosage**: 투약량 (예: 1정, 500mg)
    - **frequency**: 복용횟수 (예: 1일 2회)
    - **timing**: 복용시점 (예: 식후, 식전, 취침 전)
    - **duration_days**: 총투약일수
    - **daily_slots**: 복약 시간대 (예: ["아침", "저녁"])
    """
    result = await DocAnalysisResult.get_or_none(
        doc_result_id=doc_result_id,
        user_id=current_user.user_id,
        is_deleted=False,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="분석 결과를 찾을 수 없습니다.",
        )

    analysis = result.analysis_json or {}
    medications = analysis.get("medications", [])

    # ✅ 추가: 기본 정보 수정 처리
    if req.hospital_name is not None:
        analysis["hospital_name"] = req.hospital_name
    if req.visit_date is not None:
        analysis["visit_date"] = req.visit_date
    if req.diagnosis_name is not None:
        analysis["diagnosis_name"] = req.diagnosis_name

    # 약물별 수정 처리
    updated_count = 0
    for update in req.medications:
        idx = update.medication_index
        if not (0 <= idx < len(medications)):
            logger.warning(f"잘못된 medication_index: {idx} (총 {len(medications)}개)")
            continue

        if update.medication_name is not None:  # ✅ 추가
            medications[idx]["medication_name"] = update.medication_name
        if update.dosage is not None:
            medications[idx]["dosage"] = update.dosage
        if update.frequency is not None:
            medications[idx]["frequency"] = update.frequency
        if update.timing is not None:
            medications[idx]["timing"] = update.timing
        if update.duration_days is not None:  # ✅ 추가
            medications[idx]["duration_days"] = update.duration_days
        if update.instructions is not None:
            medications[idx]["instructions"] = update.instructions
        if update.daily_slots is not None:  # ✅ 추가: 복약 시간대 저장
            medications[idx]["daily_slots"] = update.daily_slots

        updated_count += 1

    analysis["medications"] = medications
    result.analysis_json = analysis
    await result.save()

    logger.info(f"분석 결과 수정 완료: doc_result_id={doc_result_id}, 수정된 약물={updated_count}개")

    return ResponseDTO(
        success=True,
        message=f"{updated_count}개 항목이 수정되었습니다.",
        data={
            "doc_result_id": doc_result_id,
            "updated_count": updated_count,
            "hospital_name": analysis.get("hospital_name"),
            "visit_date": analysis.get("visit_date"),
            "diagnosis_name": analysis.get("diagnosis_name"),
            "medications": medications,
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
