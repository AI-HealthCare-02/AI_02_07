from datetime import date

from fastapi import APIRouter, Depends, Query, status

from app.dependencies.security import get_current_user
from app.dtos.guide_dto import (
    AiGenerateRequest,
    AiGenerateResponse,
    AiResultDetailItem,
    ConditionsPutRequest,
    ConditionsResponse,
    GuideCreateRequest,
    GuideCreateResponse,
    GuideDetailResponse,
    GuideListResponse,
    GuidePatchRequest,
    GuidePatchResponse,
    MedCheckCreateRequest,
    MedCheckCreateResponse,
    MedCheckResponse,
    MessageResponse,
    ReminderCreateRequest,
    ReminderPatchRequest,
    ReminderResponse,
    ReminderSimpleResponse,
)
from app.models.user import User
from app.services.guide_service import GuideService

router = APIRouter(prefix="/guides", tags=["건강 가이드"])


def get_service() -> GuideService:
    return GuideService()


# ──────────────────────────────────────────
# 가이드 CRUD
# ──────────────────────────────────────────
@router.get("", response_model=GuideListResponse, summary="가이드 목록 조회")
async def list_guides(
    period: str | None = Query(None, description="ALL | 1M | 3M"),
    status_filter: str | None = Query(None, alias="status", description="GS_ACTIVE | GS_COMPLETED"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> GuideListResponse:
    return await svc.list_guides(current_user.user_id, period, status_filter, page, size)


@router.post("", response_model=GuideCreateResponse, status_code=status.HTTP_201_CREATED, summary="가이드 직접 입력 생성")
async def create_guide(
    req: GuideCreateRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> GuideCreateResponse:
    return await svc.create_guide(current_user.user_id, req)


@router.get("/{guide_id}", response_model=GuideDetailResponse, summary="가이드 상세 조회")
async def get_guide(
    guide_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> GuideDetailResponse:
    return await svc.get_guide(guide_id, current_user.user_id)


@router.patch("/{guide_id}", response_model=GuidePatchResponse, summary="가이드 기본 정보 수정")
async def patch_guide(
    guide_id: int,
    req: GuidePatchRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> GuidePatchResponse:
    return await svc.patch_guide(guide_id, current_user.user_id, req)


@router.delete("/{guide_id}", response_model=MessageResponse, summary="가이드 삭제 (소프트)")
async def delete_guide(
    guide_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MessageResponse:
    return await svc.delete_guide(guide_id, current_user.user_id)


# ──────────────────────────────────────────
# Conditions (기저질환·복용약·알레르기)
# ──────────────────────────────────────────
@router.get("/{guide_id}/conditions", response_model=ConditionsResponse, summary="기저질환·복용약·알레르기 조회")
async def get_conditions(
    guide_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> ConditionsResponse:
    return await svc.get_conditions(guide_id, current_user.user_id)


@router.put("/{guide_id}/conditions", response_model=MessageResponse, summary="기저질환·복용약·알레르기 전체 교체")
async def replace_conditions(
    guide_id: int,
    req: ConditionsPutRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MessageResponse:
    return await svc.replace_conditions(guide_id, current_user.user_id, req)


# ──────────────────────────────────────────
# AI 가이드 생성
# ──────────────────────────────────────────
@router.post(
    "/{guide_id}/ai-generate",
    response_model=AiGenerateResponse,
    summary="AI 복약 가이드 생성 (동기, RT_MEDICATION·RT_LIFESTYLE·RT_CAUTION | RT_DRUG_DETAIL은 명시적 요청 시에만 생성)",
)
async def generate_ai_guide(
    guide_id: int,
    req: AiGenerateRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> AiGenerateResponse:
    return await svc.generate_ai_guide(guide_id, current_user.user_id, req)


@router.get(
    "/{guide_id}/ai-results",
    response_model=list[AiResultDetailItem],
    summary="AI 생성 결과 조회 (최신 버전)",
)
async def get_ai_results(
    guide_id: int,
    result_type: str | None = Query(None, description="RT_MEDICATION | RT_LIFESTYLE | RT_CAUTION | RT_DRUG_DETAIL (명시적 요청 시에만 생성)"),
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> list[AiResultDetailItem]:
    return await svc.get_ai_results(guide_id, current_user.user_id, result_type)


# ──────────────────────────────────────────
# 복약 체크
# ──────────────────────────────────────────
@router.get("/{guide_id}/med-check", response_model=MedCheckResponse, summary="복약 현황 조회")
async def get_med_check(
    guide_id: int,
    check_date: date | None = Query(None, description="YYYY-MM-DD, 기본값: 오늘"),
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MedCheckResponse:
    return await svc.get_med_check(guide_id, current_user.user_id, check_date)


@router.post(
    "/{guide_id}/med-check",
    response_model=MedCheckCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="복약 완료 처리",
)
async def create_med_check(
    guide_id: int,
    req: MedCheckCreateRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MedCheckCreateResponse:
    return await svc.create_med_check(guide_id, current_user.user_id, req)


@router.delete("/{guide_id}/med-check/{check_id}", response_model=MessageResponse, summary="복약 완료 취소 (당일만)")
async def delete_med_check(
    guide_id: int,
    check_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MessageResponse:
    return await svc.delete_med_check(guide_id, check_id, current_user.user_id)


# ──────────────────────────────────────────
# 복약 알림 (설정 저장만 — 실제 발송 스케줄러 미포함)
# ──────────────────────────────────────────
@router.get(
    "/{guide_id}/reminder",
    response_model=ReminderResponse,
    summary="복약 알림 설정 조회 [1차: 저장만, 발송 미포함]",
)
async def get_reminder(
    guide_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> ReminderResponse:
    return await svc.get_reminder(guide_id, current_user.user_id)


@router.post(
    "/{guide_id}/reminder",
    response_model=ReminderSimpleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="복약 알림 등록 [1차: 저장만, 발송 미포함]",
)
async def create_reminder(
    guide_id: int,
    req: ReminderCreateRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> ReminderSimpleResponse:
    return await svc.create_reminder(guide_id, current_user.user_id, req)


@router.patch(
    "/{guide_id}/reminder",
    response_model=ReminderSimpleResponse,
    summary="복약 알림 수정·활성화/비활성화",
)
async def patch_reminder(
    guide_id: int,
    req: ReminderPatchRequest,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> ReminderSimpleResponse:
    return await svc.patch_reminder(guide_id, current_user.user_id, req)


@router.delete("/{guide_id}/reminder", response_model=MessageResponse, summary="복약 알림 삭제")
async def delete_reminder(
    guide_id: int,
    current_user: User = Depends(get_current_user),
    svc: GuideService = Depends(get_service),
) -> MessageResponse:
    return await svc.delete_reminder(guide_id, current_user.user_id)
