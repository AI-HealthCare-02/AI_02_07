# app/services/medical_doc_service.py
# ──────────────────────────────────────────────
# 의료 문서 분석 서비스 — 이승원 담당
# DB 저장 및 조회 로직
# ──────────────────────────────────────────────

import logging

from app.models.medical_doc import DocAnalysisJob, DocAnalysisResult
from app.models.user import User

logger = logging.getLogger(__name__)

# ── 문서 종류 변환 맵 ──────────────────────────
DOC_TYPE_CODE_MAP = {
    "처방전": "DOC_PRESCRIPTION",
    "진료기록": "DOC_DIAGNOSIS",
    "약봉투": "DOC_MEDICATION_INFO",
    "검진결과": "DOC_TEST_RESULT",
    "자동인식": "DOC_OTHER",
}

DOC_TYPE_NAME_MAP = {v: k for k, v in DOC_TYPE_CODE_MAP.items()}


# ── 분석 작업 생성 ─────────────────────────────
async def create_analysis_job(
    user: User,
    document_type: str,
) -> DocAnalysisJob:
    """분석 요청 Job 생성 — 분석 시작 전 호출"""
    doc_type_code = DOC_TYPE_CODE_MAP.get(document_type, "DOC_OTHER")

    job = await DocAnalysisJob.create(
        user=user,
        status_grp="JOB_STATUS",
        status_code="JOB_PENDING",
        doc_type_grp="DOC_TYPE",
        doc_type_code=doc_type_code,
    )
    logger.info(f"분석 Job 생성: job_id={job.job_id}, user_id={user.user_id}")
    return job


# ── 분석 결과 저장 ─────────────────────────────
async def save_analysis_result(
    job: DocAnalysisJob,
    user: User,
    analysis_result: dict,
    ocr_raw_text: str,
    processing_time: float,
) -> DocAnalysisResult:
    """분석 완료 후 결과 저장"""

    overall_confidence = analysis_result.get("overall_confidence", 0.0)
    raw_summary = analysis_result.get("raw_summary", "")
    doc_type = analysis_result.get("document_type", "자동인식")
    doc_type_code = DOC_TYPE_CODE_MAP.get(doc_type, "DOC_OTHER")

    # 결과 저장
    result = await DocAnalysisResult.create(
        job=job,
        user=user,
        doc_type_grp="DOC_TYPE",
        doc_type_code=doc_type_code,
        ocr_status_grp="OCR_STATUS",
        ocr_status_code="OCR_COMPLETED",
        ocr_raw_text=ocr_raw_text,
        ocr_confidence=int(overall_confidence * 100),
        overall_confidence=overall_confidence,
        raw_summary=raw_summary,
    )

    # Job 상태 업데이트
    job.status_code = "JOB_COMPLETED"
    job.processing_time = processing_time
    await job.save()

    logger.info(f"분석 결과 저장: doc_result_id={result.doc_result_id}, job_id={job.job_id}")
    return result


# ── 분석 실패 처리 ─────────────────────────────
async def fail_analysis_job(
    job: DocAnalysisJob,
    error_message: str,
) -> None:
    """분석 실패 시 Job 상태 업데이트"""
    job.status_code = "JOB_FAILED"
    job.error_message = error_message
    await job.save()
    logger.error(f"분석 Job 실패: job_id={job.job_id}, error={error_message}")


# ── 분석 결과 목록 조회 ────────────────────────
async def get_analysis_results(
    user: User,
    page: int = 1,
    page_size: int = 10,
) -> dict:
    """사용자의 분석 결과 목록 조회"""
    offset = (page - 1) * page_size

    total = await DocAnalysisResult.filter(
        user=user,
        is_deleted=False,
    ).count()

    results = await DocAnalysisResult.filter(
        user=user,
        is_deleted=False,
    ).prefetch_related("job").order_by("-created_at").offset(offset).limit(page_size)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "results": [
            {
                "doc_result_id": r.doc_result_id,
                "document_type": DOC_TYPE_NAME_MAP.get(r.doc_type_code, r.doc_type_code),
                "overall_confidence": r.overall_confidence,
                "raw_summary": r.raw_summary,
                "created_at": r.created_at.isoformat(),
            }
            for r in results
        ],
    }


# ── 분석 결과 단건 조회 ────────────────────────
async def get_analysis_result(
    user: User,
    doc_result_id: int,
) -> DocAnalysisResult | None:
    """특정 분석 결과 단건 조회"""
    return await DocAnalysisResult.get_or_none(
        doc_result_id=doc_result_id,
        user=user,
        is_deleted=False,
    )


# ── 분석 결과 삭제 ─────────────────────────────
async def delete_analysis_result(
    user: User,
    doc_result_id: int,
) -> bool:
    """분석 결과 소프트 삭제"""
    result = await get_analysis_result(user, doc_result_id)
    if not result:
        return False
    result.is_deleted = True
    await result.save()
    logger.info(f"분석 결과 삭제: doc_result_id={doc_result_id}")
    return True