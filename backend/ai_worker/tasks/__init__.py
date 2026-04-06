# ai_worker/tasks/__init__.py
# ──────────────────────────────────────────────
# 작업 핸들러 레지스트리
# 새로운 작업 유형을 추가할 때:
#   1. 이 파일의 TASK_HANDLERS에 등록
#   2. tasks/ 폴더에 핸들러 모듈 작성
# ──────────────────────────────────────────────

from collections.abc import Callable, Coroutine
from typing import Any

# 작업 핸들러 타입 정의
# 각 핸들러는 payload(dict)를 받아서 결과(dict)를 반환하는 비동기 함수
TaskHandler = Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]]

# ──────────────────────────────────────────────
# 작업 유형 → 핸들러 함수 매핑
# 팀원이 새 작업을 추가할 때 이 딕셔너리에 등록하세요!
#
# 예시:
#   from ai_worker.tasks.medical_doc import handle_medical_doc_analysis
#   TASK_HANDLERS["medical_doc_analysis"] = handle_medical_doc_analysis
# ──────────────────────────────────────────────
TASK_HANDLERS: dict[str, TaskHandler] = {}


def register_task(task_type: str):
    """
    작업 핸들러 등록 데코레이터.

    사용 예시:
        @register_task("medical_doc_analysis")
        async def handle_medical_doc_analysis(payload: dict) -> dict:
            ...

    이 데코레이터를 사용하면 TASK_HANDLERS에 자동 등록됩니다.
    """

    def decorator(func: TaskHandler) -> TaskHandler:
        TASK_HANDLERS[task_type] = func
        return func

    return decorator
