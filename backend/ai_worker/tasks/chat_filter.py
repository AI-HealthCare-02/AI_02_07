# ai_worker/tasks/chat_filter.py
# 3단계 질문 필터링 워커 태스크 (비동기 처리용)
# API 서버의 SSE 스트리밍과 별개로, 워커 큐를 통한 처리가 필요할 때 사용


import logging

try:
    from langfuse.openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI  # type: ignore[assignment]

from ai_worker.core.config import get_worker_settings

logger = logging.getLogger(__name__)


def _is_o_series(model: str) -> bool:
    m = model.lower().strip()
    return m.startswith("o1") or m.startswith("o3")


def _build_kwargs(model: str, max_tokens: int, temperature: float | None = None) -> dict:
    kwargs: dict = {"model": model}
    if _is_o_series(model):
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
    return kwargs


async def process_chat_filter(task_data: dict) -> dict:
    """
    3단계 필터링 태스크.

    payload:
        message: str          — 사용자 질문
        session_id: int       — 채팅 세션 ID
        user_id: int          — 사용자 ID

    result:
        filter_result: PASS | DOMAIN | EMERGENCY
        blocked_message: str | None
    """
    payload = task_data["payload"]
    message: str = payload["message"]

    settings = get_worker_settings()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # 1단계: 도메인 필터
    if not await _check_domain(client, message):
        return {
            "filter_result": "DOMAIN",
            "blocked_message": "🚫 죄송합니다. 헬스가이드 챗봇은 건강·의료·복약 관련 질문에만 답변드릴 수 있습니다.",
        }

    # 2단계: 응급 필터
    if await _check_emergency(client, message):
        return {
            "filter_result": "EMERGENCY",
            "blocked_message": "🚨 응급 상황이 의심됩니다. 즉시 119에 전화하세요.",
        }

    return {"filter_result": "PASS", "blocked_message": None}


async def _check_domain(client: AsyncOpenAI, message: str) -> bool:
    resp = await client.chat.completions.create(
        **_build_kwargs("gpt-4o-mini", max_tokens=5, temperature=0),
        messages=[
            {
                "role": "system",
                "content": (
                    "다음 질문이 건강, 의료, 복약, 증상, 질병, 영양, 운동, 정신건강 관련인지 판단하세요. "
                    "관련 있으면 'YES', 없으면 'NO'만 답하세요."
                ),
            },
            {"role": "user", "content": message},
        ],
    )
    return "YES" in (resp.choices[0].message.content or "").upper()


async def _check_emergency(client: AsyncOpenAI, message: str) -> bool:
    resp = await client.chat.completions.create(
        **_build_kwargs("gpt-4o-mini", max_tokens=5, temperature=0),
        messages=[
            {
                "role": "system",
                "content": (
                    "다음 질문에서 즉각적인 응급 처치가 필요한 상황(심정지, 뇌졸중, 심한 출혈, 자살 위기 등)이 "
                    "감지되면 'YES', 아니면 'NO'만 답하세요."
                ),
            },
            {"role": "user", "content": message},
        ],
    )
    return "YES" in (resp.choices[0].message.content or "").upper()
