# app/tasks/reminder_task.py
"""
복약 알림 발송 Celery Task

Beat 스케줄에 의해 매분 실행됩니다.
현재 분(HH:MM)과 reminder_time이 일치하고 is_active=True인 알림을
조회해 이메일 / 브라우저 알림 / 카카오 알림톡을 발송합니다.

repeat_type:
  RPT_DAILY   : 매일
  RPT_WEEKDAY : 평일(월~금)
  RPT_CUSTOM  : custom_days 에 현재 요일이 포함될 때만 발송
                custom_days 예시: [0, 1, 2, 3, 4]  (0=월, 6=일)
"""

import logging
from datetime import datetime, timezone

from celery import shared_task

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────
# 메인 Task
# ──────────────────────────────────────────
@shared_task(
    name="app.tasks.reminder_task.send_due_reminders",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_due_reminders(self) -> dict:
    """
    현재 시각에 해당하는 활성 알림을 찾아 발송.
    Tortoise ORM은 비동기 전용이므로 asyncio.run()으로 감쌉니다.
    """
    import asyncio

    try:
        result = asyncio.run(_async_send_due_reminders())
        return result
    except Exception as exc:
        logger.exception("send_due_reminders 실패: %s", exc)
        raise self.retry(exc=exc)


async def _async_send_due_reminders() -> dict:
    """비동기 처리 본체 — Tortoise ORM 초기화 포함"""
    from tortoise import Tortoise

    from app.core.config import settings
    from app.models.guide import GuideReminder  # Tortoise 모델

    # Tortoise ORM 초기화 (Celery 워커는 FastAPI lifespan과 별개로 실행됨)
    await Tortoise.init(
        db_url=settings.database_url,
        modules={"models": ["app.models.guide", "app.models.user"]},
    )

    now_kst = datetime.now(timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("Asia/Seoul"))
    current_hhmm = now_kst.strftime("%H:%M")
    weekday = now_kst.weekday()  # 0=월, 6=일

    sent, skipped, failed = 0, 0, 0

    try:
        # 현재 분과 reminder_time이 일치하는 활성 알림 전체 조회
        # reminder_time 은 TimeField (HH:MM:SS) → 앞 5자리만 비교
        reminders = await GuideReminder.filter(is_active=True).select_related("guide")

        for reminder in reminders:
            # 시간 비교: HH:MM
            if reminder.reminder_time.strftime("%H:%M") != current_hhmm:
                skipped += 1
                continue

            # 요일 필터
            if not _should_send_today(reminder, weekday):
                skipped += 1
                continue

            try:
                await _dispatch(reminder, now_kst)
                sent += 1
            except Exception as e:
                logger.error(
                    "알림 발송 실패 [reminder_id=%s]: %s",
                    reminder.reminder_id,
                    e,
                )
                failed += 1

    finally:
        await Tortoise.close_connections()

    logger.info(
        "복약 알림 처리 완료 [%s] — 발송: %d, 건너뜀: %d, 실패: %d",
        current_hhmm,
        sent,
        skipped,
        failed,
    )
    return {"sent": sent, "skipped": skipped, "failed": failed}


def _should_send_today(reminder, weekday: int) -> bool:
    """repeat_type·custom_days 기준으로 오늘 발송 여부 판단"""
    rpt = reminder.repeat_type

    if rpt == "RPT_DAILY":
        return True

    if rpt == "RPT_WEEKDAY":
        return weekday <= 4  # 0(월)~4(금)

    if rpt == "RPT_CUSTOM":
        custom_days = reminder.custom_days or []
        return weekday in custom_days

    logger.warning("알 수 없는 repeat_type: %s", rpt)
    return False


async def _dispatch(reminder, now_kst: datetime) -> None:
    """채널별 알림 발송"""
    guide = reminder.guide

    # 가이드가 삭제되거나 완료된 경우 스킵
    if guide.is_deleted or guide.guide_status != "GS_ACTIVE":
        return

    tasks = []

    if reminder.is_email_noti:
        tasks.append(_send_email(reminder, guide, now_kst))

    if reminder.is_browser_noti:
        tasks.append(_send_browser_push(reminder, guide))

    # 카카오 알림톡은 별도 설정 플래그 or 항상 시도 (현재는 주석)
    # tasks.append(_send_kakao(reminder, guide))

    if tasks:
        import asyncio

        await asyncio.gather(*tasks, return_exceptions=True)


# ──────────────────────────────────────────
# 이메일 발송
# ──────────────────────────────────────────
async def _send_email(reminder, guide, now_kst: datetime) -> None:
    """
    이메일 복약 알림.
    실제 SMTP 연동은 프로젝트의 이메일 유틸로 교체하세요.
    (예: FastMail, SendGrid, SES 등)
    """
    try:
        # guide → user → email 접근
        user = await guide.user
        if not user or not getattr(user, "email", None):
            return

        subject = f"[건강가이드] '{guide.title}' 복약 알림 🔔"
        body = (
            f"안녕하세요, {getattr(user, 'nickname', '회원')}님!\n\n"
            f"'{guide.title}' 가이드의 복약 시간입니다.\n"
            f"• 예정 시간: {reminder.reminder_time.strftime('%H:%M')}\n\n"
            "건강한 하루 되세요!\n— 건강가이드 팀"
        )

        # TODO: 실제 이메일 발송 유틸 호출
        # await send_email_util(to=user.email, subject=subject, body=body)
        logger.info(
            "이메일 알림 [reminder_id=%s] → %s : %s",
            reminder.reminder_id,
            user.email,
            subject,
        )

    except Exception as e:
        logger.error("이메일 발송 실패 [reminder_id=%s]: %s", reminder.reminder_id, e)
        raise


# ──────────────────────────────────────────
# 브라우저 Push 알림
# ──────────────────────────────────────────
async def _send_browser_push(reminder, guide) -> None:
    """
    Web Push (VAPID) 알림.
    pywebpush 라이브러리 사용 권장.
    subscription_info는 User 모델에 저장 필요 (현재 미구현 → 로그만).
    """
    try:
        user = await guide.user
        subscription_info = getattr(user, "push_subscription", None)

        if not subscription_info:
            logger.debug(
                "브라우저 Push 구독 정보 없음 [user_id=%s]",
                getattr(user, "user_id", "?"),
            )
            return

        payload = {
            "title": "복약 알림 🔔",
            "body": f"'{guide.title}' 복약 시간입니다!",
            "icon": "/icons/pill.png",
        }

        # TODO: pywebpush 연동
        # from pywebpush import webpush
        # webpush(
        #     subscription_info=subscription_info,
        #     data=json.dumps(payload),
        #     vapid_private_key=settings.VAPID_PRIVATE_KEY,
        #     vapid_claims={"sub": f"mailto:{settings.VAPID_EMAIL}"},
        # )
        logger.info(
            "브라우저 Push [reminder_id=%s] payload=%s",
            reminder.reminder_id,
            payload,
        )

    except Exception as e:
        logger.error("브라우저 Push 실패 [reminder_id=%s]: %s", reminder.reminder_id, e)
        raise


# ──────────────────────────────────────────
# 카카오 알림톡
# ──────────────────────────────────────────
async def _send_kakao(reminder, guide) -> None:
    """카카오 알림톡 발송 — kakao_notification.py 참조"""
    from app.services.kakao_notification import KakaoAlimtalkClient

    try:
        user = await guide.user
        phone = getattr(user, "phone", None)
        if not phone:
            return

        client = KakaoAlimtalkClient()
        await client.send_medication_reminder(
            to=phone,
            guide_title=guide.title,
            reminder_time=reminder.reminder_time.strftime("%H:%M"),
        )
    except Exception as e:
        logger.error("카카오 알림톡 실패 [reminder_id=%s]: %s", reminder.reminder_id, e)
        raise
