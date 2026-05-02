"""
app/services/alarm_scheduler.py
────────────────────────────────────
복약 알림 스케줄러 (APScheduler 기반)

[동작 방식]
- 매 1분마다 med_reminder 테이블을 조회
- 현재 시각(분 단위)과 reminder_time이 일치하는 활성 알림 대상 추출
- is_kakao_noti=True → 카카오 나에게 보내기 발송
- is_email_noti=True → 이메일 발송 (추후 구현)
- is_browser_noti=True → 프론트 SSE 또는 Web Push (수호 담당)

[설치]
pip install apscheduler
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.kakao_alarm_service import KakaoAlarmService

logger = logging.getLogger(__name__)

# 싱글턴 스케줄러 인스턴스
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """스케줄러 싱글턴 반환."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    return _scheduler


async def _run_alarm_job() -> None:
    """
    매 1분마다 실행 — 현재 시각에 맞는 복약 알림 발송.

    흐름:
    1. 현재 시각(HH:MM) 기준 활성 알림 조회
    2. repeat_type에 따라 오늘 요일 필터
    3. is_kakao_noti=True인 경우 카카오 발송
    4. is_email_noti=True인 경우 이메일 발송 (추후 구현)
    """
    try:
        from app.models.guide import Guide, GuideMedication, GuideReminder
        from app.models.user import User

        now = datetime.now(tz=timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Seoul"))
        now_time_str = now.strftime("%H:%M")  # "08:00" 형태
        weekday = now.weekday()  # 0=월 ~ 6=일

        reminders = await GuideReminder.filter(is_active=True)

        kakao_svc = KakaoAlarmService()

        for reminder in reminders:
            # ── 시간 일치 여부 확인 ──
            r_time_str = reminder.reminder_time.strftime("%H:%M")
            if r_time_str != now_time_str:
                continue

            logger.info(f"[AlarmScheduler] 알림 시각 일치 — reminder_id={reminder.reminder_id}, time={r_time_str}")

            # ── 요일 필터 ──
            repeat = reminder.repeat_type
            logger.info(f"[AlarmScheduler] repeat_type={repeat}, weekday={weekday} (0=월~6=일)")

            if repeat == "RPT_WEEKDAY" and weekday >= 5:
                # 평일만 — 주말(5=토, 6=일) 스킵
                logger.info(f"[AlarmScheduler] 주말 스킵 — reminder_id={reminder.reminder_id}")
                continue

            if repeat == "RPT_CUSTOM":
                custom = reminder.custom_days or []
                # ✅ 수정: custom_days가 NULL이면 매일 발송으로 폴백
                if not custom:
                    logger.warning(
                        f"[AlarmScheduler] RPT_CUSTOM인데 custom_days 없음 → 매일 발송으로 폴백 "
                        f"— reminder_id={reminder.reminder_id}"
                    )
                elif weekday not in custom:
                    logger.info(f"[AlarmScheduler] 요일 불일치 스킵 — weekday={weekday}, custom={custom}")
                    continue

            # ✅ 수정: pk= 로 직접 조회
            guide_pk = reminder.guide_id
            logger.info(f"[AlarmScheduler] guide_pk 조회 시도 — guide_pk={guide_pk}")
            guide = await Guide.get_or_none(pk=guide_pk)
            if not guide or guide.is_deleted:
                logger.warning(f"[AlarmScheduler] 가이드 없음 또는 삭제됨 — guide_pk={guide_pk}, guide={guide}")
                continue

            logger.info(f"[AlarmScheduler] 가이드 조회 성공 — guide_id={guide.guide_id}, user_id={guide.user_id}")

            # ── 약물 목록 조회 ──
            medications = await GuideMedication.filter(guide_id=guide.guide_id)
            med_names = [m.medication_name for m in medications]
            if not med_names:
                logger.warning(f"[AlarmScheduler] 약물 없음 — guide_id={guide.guide_id}")
                continue

            guide_title = guide.title or "복약 가이드"

            # ── 카카오 알림 발송 ──
            if reminder.is_kakao_noti:
                user = await User.get_or_none(user_id=guide.user_id)
                if user and user.provider_code == "KAKAO" and getattr(user, "kakao_access_token", None):
                    logger.info(
                        f"[AlarmScheduler] 카카오 발송 시도 — guide_id={guide.guide_id}, user_id={guide.user_id}"
                    )
                    success = await kakao_svc.send_medication_alarm(
                        kakao_access_token=user.kakao_access_token,
                        guide_title=guide_title,
                        medication_names=med_names,
                        reminder_time=r_time_str,
                        user_id=guide.user_id,  # 토큰 만료 시 자동 갱신용
                    )
                    if not success:
                        logger.warning(
                            f"[AlarmScheduler] 카카오 발송 실패 — guide_id={guide.guide_id}, user_id={guide.user_id}"
                        )
                else:
                    logger.warning(f"[AlarmScheduler] 카카오 토큰 없음 — user_id={guide.user_id}")

            # ── 이메일 알림 발송 (추후 구현) ──
            if reminder.is_email_noti:
                # TODO: EmailAlarmService 구현 후 연동
                logger.info(f"[AlarmScheduler] 이메일 발송 예정 — guide_id={guide.guide_id} (미구현)")

            # ── 브라우저 알림은 프론트(수호) 담당 ──
            # is_browser_noti=True인 경우 프론트가 주기적으로
            # GET /guides/{id}/reminder 폴링하거나 Web Push 사용

    except Exception as e:
        logger.error(f"[AlarmScheduler] 알림 잡 실행 오류: {e}")


def start_scheduler() -> None:
    """스케줄러 시작 — app startup에서 호출."""
    scheduler = get_scheduler()
    if scheduler.running:
        logger.warning("[AlarmScheduler] 이미 실행 중")
        return

    # 매 1분마다 실행
    scheduler.add_job(
        _run_alarm_job,
        trigger="cron",
        minute="*",  # 매 분 0초에 실행
        id="med_alarm_job",
        replace_existing=True,
        max_instances=1,  # 동시 실행 방지
    )

    scheduler.start()
    logger.info("✅ [AlarmScheduler] 복약 알림 스케줄러 시작 (매 1분 실행)")


def stop_scheduler() -> None:
    """스케줄러 종료 — app shutdown에서 호출."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 [AlarmScheduler] 복약 알림 스케줄러 종료")
