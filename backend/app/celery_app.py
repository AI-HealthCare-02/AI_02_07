# app/celery_app.py
"""
Celery 애플리케이션 설정
- Broker  : Redis (settings.redis_url)
- Backend : Redis
- Beat    : 복약 알림 스케줄러 (매분 실행 → 알림 시간 해당 reminder만 필터)

실행 방법:
  # Worker
  celery -A app.celery_app worker --loglevel=info -Q reminder_queue

  # Beat (스케줄러)
  celery -A app.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "healthguide",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.reminder_task"],
)

celery_app.conf.update(
    # 직렬화
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    # 큐 라우팅
    task_routes={
        "app.tasks.reminder_task.send_due_reminders": {"queue": "reminder_queue"},
    },
    # Beat 스케줄: 매분 실행 → 해당 분 알림 대상 필터링
    beat_schedule={
        "check-reminders-every-minute": {
            "task": "app.tasks.reminder_task.send_due_reminders",
            "schedule": crontab(minute="*"),  # 매분
        },
    },
    # 재시도 설정
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,
)
