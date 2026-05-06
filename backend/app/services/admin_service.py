# app/services/admin_service.py

import logging
import time
from datetime import UTC, date, datetime, timedelta

import bcrypt
from fastapi import HTTPException, status
from tortoise.expressions import Q

from app.core.redis import get_redis
from app.core.security import create_access_token
from app.dtos.admin_dto import (
    AdminInfoDTO,
    AdminLoginDataDTO,
    AdminUserItemDTO,
    AdminUserListDTO,
    AnswerModelConfigDTO,
    ChartDatasetDTO,
    DashboardChartDTO,
    DashboardSummaryDTO,
    FilterBlockedCountDTO,
    FilterModelConfigDTO,
    LLMTestResultDTO,
    SystemSettingsDTO,
    SystemSettingsUpdateRequestDTO,
    UserSuspendResultDTO,
)
from app.models.admin import AdminUser
from app.models.ai_settings import AISettings
from app.models.chat import ChatMessage
from app.models.user import User

logger = logging.getLogger(__name__)

_LOGIN_FAIL_PREFIX = "admin_login_fail:"
_LOGIN_LOCK_PREFIX = "admin_login_lock:"
_TOKEN_BLACKLIST_PREFIX = "admin_token_blacklist:"
_MAX_FAIL = 5
_LOCK_SECONDS = 300  # 5분


# ── 비밀번호 검증 ──
def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


# ============================================================
# Auth
# ============================================================


async def admin_login(admin_email: str, password: str) -> AdminLoginDataDTO:
    redis = get_redis()
    lock_key = f"{_LOGIN_LOCK_PREFIX}{admin_email}"
    fail_key = f"{_LOGIN_FAIL_PREFIX}{admin_email}"

    # 잠금 확인
    if await redis.exists(lock_key):
        ttl = await redis.ttl(lock_key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"로그인이 잠겼습니다. {ttl}초 후 다시 시도하세요.",
        )

    admin = await AdminUser.get_or_none(admin_email=admin_email)

    if admin is None or not _verify_password(password, admin.password):
        # 실패 횟수 증가
        fail_count = await redis.incr(fail_key)
        await redis.expire(fail_key, _LOCK_SECONDS)

        if fail_count >= _MAX_FAIL:
            await redis.set(lock_key, "1", ex=_LOCK_SECONDS)
            await redis.delete(fail_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="5회 연속 실패로 5분간 로그인이 잠겼습니다.",
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    # 성공 시 실패 카운트 초기화
    await redis.delete(fail_key)

    # last_login_at 갱신
    admin.last_login_at = datetime.now(UTC)
    await admin.save(update_fields=["last_login_at"])

    access_token = create_access_token({"sub": str(admin.admin_id), "role": "admin"})

    return AdminLoginDataDTO(
        accessToken=access_token,
        admin=AdminInfoDTO(
            adminId=admin.admin_id,
            adminEmail=admin.admin_email,
            adminName=admin.admin_name,
            roleCode=admin.role_code,
        ),
    )


async def admin_logout(token: str) -> None:
    redis = get_redis()
    # 토큰을 블랙리스트에 추가 (1시간 TTL)
    await redis.set(f"{_TOKEN_BLACKLIST_PREFIX}{token}", "1", ex=3600)


async def is_token_blacklisted(token: str) -> bool:
    redis = get_redis()
    return bool(await redis.exists(f"{_TOKEN_BLACKLIST_PREFIX}{token}"))


# ============================================================
# Dashboard
# ============================================================


async def get_dashboard_summary() -> DashboardSummaryDTO:
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = await User.filter(deleted_at=None).count()

    # 오늘 활성 사용자: last_active_at 기준
    today_active_users = await User.filter(deleted_at=None, last_active_at__gte=today_start).count()

    # 오늘 의료문서 사용률 (오늘 분석 요청 건수)
    from app.models.medical_doc import DocAnalysisJob

    ocr_usage_count = await DocAnalysisJob.filter(created_at__gte=today_start, is_deleted=False).count()

    # 오늘 챗봇 문의 (USER 메시지 기준)
    today_chat_count = await ChatMessage.filter(created_at__gte=today_start, sender_type_code="USER").count()

    # 오늘 필터 차단
    domain_blocked = await ChatMessage.filter(created_at__gte=today_start, filter_result="DOMAIN").count()
    emergency_blocked = await ChatMessage.filter(created_at__gte=today_start, filter_result="EMERGENCY").count()

    # 알약 분석
    from app.models.pill_analysis import PillAnalysisHistory

    today_pill = await PillAnalysisHistory.filter(created_at__gte=today_start).count()
    total_pill = await PillAnalysisHistory.all().count()

    return DashboardSummaryDTO(
        totalUsers=total_users,
        todayActiveUsers=today_active_users,
        ocrUsageCount=ocr_usage_count,
        todayChatCount=today_chat_count,
        todayFilterBlockedCount=FilterBlockedCountDTO(
            domainBlocked=domain_blocked,
            emergencyBlocked=emergency_blocked,
            total=domain_blocked + emergency_blocked,
        ),
        todayPillAnalysisCount=today_pill,
        totalPillAnalysisCount=total_pill,
    )


async def get_dashboard_chart(
    chart_type: str,
    period: str,
    start_date: date | None,
    end_date: date | None,
) -> DashboardChartDTO:
    # 기본 날짜 범위
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        if period == "DAILY":
            start_date = end_date - timedelta(days=29)
        elif period == "MONTHLY":
            start_date = date(end_date.year - 1, end_date.month, 1)
        else:  # YEARLY
            start_date = date(end_date.year - 4, 1, 1)

    labels = _generate_labels(period, start_date, end_date)

    if chart_type == "SIGNUP":
        datasets = await _chart_signup(period, start_date, end_date, labels)
    elif chart_type == "OCR_SUCCESS":
        datasets = await _chart_ocr(period, start_date, end_date, labels)
    elif chart_type == "CHAT_USAGE":
        datasets = await _chart_chat(period, start_date, end_date, labels)
    elif chart_type == "FILTER_BLOCKED":
        datasets = await _chart_filter(period, start_date, end_date, labels)
    elif chart_type == "PILL_ANALYSIS":
        datasets = await _chart_pill(period, start_date, end_date, labels)
    else:
        raise HTTPException(status_code=400, detail="유효하지 않은 type 파라미터입니다.")

    return DashboardChartDTO(type=chart_type, period=period, labels=labels, datasets=datasets)


def _generate_labels(period: str, start: date, end: date) -> list[str]:
    labels = []
    cur = start
    while cur <= end:
        if period == "DAILY":
            labels.append(cur.strftime("%Y-%m-%d"))
            cur += timedelta(days=1)
        elif period == "MONTHLY":
            labels.append(cur.strftime("%Y-%m"))
            # 다음 달 1일
            if cur.month == 12:
                cur = date(cur.year + 1, 1, 1)
            else:
                cur = date(cur.year, cur.month + 1, 1)
        else:  # YEARLY
            labels.append(str(cur.year))
            cur = date(cur.year + 1, 1, 1)
    return labels


def _trunc_expr(period: str) -> str:
    mapping = {"DAILY": "day", "MONTHLY": "month", "YEARLY": "year"}
    return mapping.get(period, "day")


def _fmt_key(label_date: object, period: str) -> str:
    """DATE_TRUNC 결과(date 객체 또는 str)를 _generate_labels 형식으로 변환.

    DAILY   → YYYY-MM-DD  (str 그대로)
    MONTHLY → YYYY-MM     (YYYY-MM-01 에서 앞 7자)
    YEARLY  → YYYY        (YYYY-01-01 에서 앞 4자)
    """
    s = str(label_date)  # datetime.date → "YYYY-MM-DD"
    if period == "MONTHLY":
        return s[:7]  # "2026-04-01" → "2026-04"
    if period == "YEARLY":
        return s[:4]  # "2026-01-01" → "2026"
    return s  # DAILY: "2026-04-13" 그대로


async def _chart_signup(period, start, end, labels) -> list[ChartDatasetDTO]:
    from tortoise.expressions import RawSQL
    from tortoise.functions import Count

    trunc = _trunc_expr(period)
    rows = (
        await User.filter(created_at__gte=start, created_at__lt=end + timedelta(days=1), deleted_at=None)
        .annotate(label=RawSQL(f"DATE_TRUNC('{trunc}', created_at)::date"), cnt=Count("user_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    data_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in rows}
    data = [data_map.get(lbl, 0) for lbl in labels]
    return [ChartDatasetDTO(label="신규 가입자", data=data)]


async def _chart_ocr(period, start, end, labels) -> list[ChartDatasetDTO]:
    from tortoise.expressions import RawSQL
    from tortoise.functions import Count

    from app.models.medical_doc import DocAnalysisJob

    trunc = _trunc_expr(period)
    rows = (
        await DocAnalysisJob.filter(created_at__gte=start, created_at__lt=end + timedelta(days=1), is_deleted=False)
        .annotate(label=RawSQL(f"DATE_TRUNC('{trunc}', created_at)::date"), cnt=Count("job_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    data_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in rows}
    data = [data_map.get(lbl, 0) for lbl in labels]
    return [ChartDatasetDTO(label="의료문서 사용", data=data)]


async def _chart_chat(period, start, end, labels) -> list[ChartDatasetDTO]:
    from tortoise.expressions import RawSQL
    from tortoise.functions import Count

    trunc = _trunc_expr(period)
    rows = (
        await ChatMessage.filter(created_at__gte=start, created_at__lt=end + timedelta(days=1), sender_type_code="USER")
        .annotate(label=RawSQL(f"DATE_TRUNC('{trunc}', created_at)::date"), cnt=Count("message_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    data_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in rows}
    data = [data_map.get(lbl, 0) for lbl in labels]
    return [ChartDatasetDTO(label="챗봇 이용량", data=data)]


async def _chart_pill(period, start, end, labels) -> list[ChartDatasetDTO]:
    from tortoise.expressions import RawSQL
    from tortoise.functions import Count

    from app.models.pill_analysis import PillAnalysisHistory

    trunc = _trunc_expr(period)
    rows = (
        await PillAnalysisHistory.filter(created_at__gte=start, created_at__lt=end + timedelta(days=1))
        .annotate(label=RawSQL(f"DATE_TRUNC('{trunc}', created_at)::date"), cnt=Count("analysis_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    data_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in rows}
    data = [data_map.get(lbl, 0) for lbl in labels]
    return [ChartDatasetDTO(label="알약 분석 이용", data=data)]


async def _chart_filter(period, start, end, labels) -> list[ChartDatasetDTO]:
    from tortoise.expressions import RawSQL
    from tortoise.functions import Count

    trunc = _trunc_expr(period)
    base_qs = ChatMessage.filter(
        created_at__gte=start,
        created_at__lt=end + timedelta(days=1),
        filter_result__in=["DOMAIN", "EMERGENCY"],
    ).annotate(label=RawSQL(f"DATE_TRUNC('{trunc}', created_at)::date"))

    domain_rows = (
        await base_qs.filter(filter_result="DOMAIN")
        .annotate(cnt=Count("message_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    emergency_rows = (
        await base_qs.filter(filter_result="EMERGENCY")
        .annotate(cnt=Count("message_id"))
        .group_by("label")
        .order_by("label")
        .values("label", "cnt")
    )
    domain_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in domain_rows}
    emergency_map = {_fmt_key(r["label"], period): int(r["cnt"]) for r in emergency_rows}
    return [
        ChartDatasetDTO(label="도메인 차단", data=[domain_map.get(lbl, 0) for lbl in labels]),
        ChartDatasetDTO(label="응급 차단", data=[emergency_map.get(lbl, 0) for lbl in labels]),
    ]


# ============================================================
# Users
# ============================================================

_PROVIDER_NAME_MAP = {
    "LOCAL": "이메일",
    "GOOGLE": "Google",
    "KAKAO": "카카오",
    "NAVER": "네이버",
}


async def get_admin_user_list(page: int, size: int, keyword: str | None, status_filter: str) -> AdminUserListDTO:
    qs = User.filter(deleted_at=None)

    if keyword:
        qs = qs.filter(Q(name__icontains=keyword) | Q(email__icontains=keyword))

    if status_filter == "ACTIVE":
        qs = qs.filter(is_suspended=False)
    elif status_filter == "SUSPENDED":
        qs = qs.filter(is_suspended=True)

    total = await qs.count()
    users = await qs.offset((page - 1) * size).limit(size)

    items = [
        AdminUserItemDTO(
            userId=u.user_id,
            name=u.name,
            email=u.email,
            createdAt=u.created_at.isoformat(),
            providerCode=u.provider_code,
            providerName=_PROVIDER_NAME_MAP.get(u.provider_code, u.provider_code),
            isSuspended=u.is_suspended,
            status="SUSPENDED" if u.is_suspended else "ACTIVE",
        )
        for u in users
    ]

    return AdminUserListDTO(totalCount=total, page=page, size=size, items=items)


async def suspend_user(user_id: int) -> UserSuspendResultDTO:
    user = await User.get_or_none(user_id=user_id, deleted_at=None)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if user.is_suspended:
        raise HTTPException(status_code=409, detail="이미 정지된 사용자입니다.")

    user.is_suspended = True
    await user.save(update_fields=["is_suspended"])
    return UserSuspendResultDTO(userId=user_id, isSuspended=True, status="SUSPENDED")


async def unsuspend_user(user_id: int) -> UserSuspendResultDTO:
    user = await User.get_or_none(user_id=user_id, deleted_at=None)
    if user is None:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    if not user.is_suspended:
        raise HTTPException(status_code=409, detail="정지 상태가 아닌 사용자입니다.")

    user.is_suspended = False
    await user.save(update_fields=["is_suspended"])
    return UserSuspendResultDTO(userId=user_id, isSuspended=False, status="ACTIVE")


# ============================================================
# System Settings
# ============================================================

_FILTER_NOTE = "분류용 모델 — Temperature 0.0 고정, Max Tokens 10 고정"


async def get_system_settings() -> SystemSettingsDTO:
    answer = await AISettings.get_or_none(config_name="chat", is_active=True)
    if answer is None:
        raise HTTPException(status_code=404, detail="시스템 설정이 초기화되지 않았습니다.")

    # filter 설정은 filter_model config_name으로 관리, 없으면 기본값 사용
    filter_ = await AISettings.get_or_none(config_name="filter")
    filter_model = filter_.api_model if filter_ else "gpt-4o-mini"

    return SystemSettingsDTO(
        answerModel=AnswerModelConfigDTO(
            apiModel=answer.api_model,
            temperature=float(answer.temperature),
            maxTokens=answer.max_tokens,
        ),
        filterModel=FilterModelConfigDTO(
            apiModel=filter_model,
            temperature=0.0,
            maxTokens=10,
            note=_FILTER_NOTE,
        ),
        updatedAt=answer.updated_at.isoformat(),
    )


async def update_system_settings(req: SystemSettingsUpdateRequestDTO) -> SystemSettingsDTO:
    # answerModel → config_name='chat' 행 업데이트
    answer, _ = await AISettings.get_or_create(
        config_name="chat",
        defaults={"system_prompt": "", "is_active": True},
    )
    answer.api_model = req.answerModel.apiModel
    answer.temperature = req.answerModel.temperature
    answer.max_tokens = req.answerModel.maxTokens
    await answer.save(update_fields=["api_model", "temperature", "max_tokens", "updated_at"])

    # filterModel → config_name='filter' 행 업데이트 (temperature/max_tokens 고정)
    filter_, _ = await AISettings.get_or_create(
        config_name="filter",
        defaults={"system_prompt": "", "is_active": True},
    )
    filter_.api_model = req.filterModel.apiModel
    filter_.temperature = 0.0
    filter_.max_tokens = 10
    await filter_.save(update_fields=["api_model", "temperature", "max_tokens", "updated_at"])

    return SystemSettingsDTO(
        answerModel=AnswerModelConfigDTO(
            apiModel=answer.api_model,
            temperature=float(answer.temperature),
            maxTokens=answer.max_tokens,
        ),
        filterModel=FilterModelConfigDTO(
            apiModel=filter_.api_model,
            temperature=0.0,
            maxTokens=10,
        ),
        updatedAt=answer.updated_at.isoformat(),
    )


async def test_llm(api_model: str, temperature: float, max_tokens: int) -> LLMTestResultDTO:
    import openai

    from app.core.config import get_settings
    from app.core.openai_utils import build_create_kwargs

    settings = get_settings()
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    start = time.time()
    try:
        response = await client.chat.completions.create(
            **build_create_kwargs(
                model=api_model,
                max_tokens=max_tokens,
                temperature=temperature,
            ),
            messages=[{"role": "user", "content": "Say 'test ok' in one word."}],
        )
        elapsed = int((time.time() - start) * 1000)
        return LLMTestResultDTO(
            success=True,
            responseTime=elapsed,
            testResponse=response.choices[0].message.content,
            errorMessage=None,
        )
    except Exception as e:
        return LLMTestResultDTO(
            success=False,
            responseTime=None,
            testResponse=None,
            errorMessage=str(e),
        )
