# app/services/chat_service.py
# 채팅 비즈니스 로직 + SSE 스트리밍

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import HTTPException, status
from openai import AsyncOpenAI
from tortoise import Tortoise

from app.core.config import get_settings
from app.core.openai_utils import build_create_kwargs
from app.core.redis import get_redis
from app.dtos.chat_dto import (
    BookmarkResponseDTO,
    ChatMessageItemDTO,
    ChatRoomCreateResponseDTO,
    ChatRoomItemDTO,
    ChatRoomListDataDTO,
    ChatRoomMessagesDataDTO,
)
from app.models.chat import ChatMessage, ChatRoom
from app.models.user import User
from app.models.user_allergy import UserAllergy
from app.models.user_disease import UserDisease
from app.models.user_lifestyle import UserLifestyle
from app.repositories.chat_repository import ChatRepository

logger = logging.getLogger(__name__)


# ── 세션 ──────────────────────────────────────────────────────────────────────


async def create_session(user: User) -> ChatRoomCreateResponseDTO:
    room = await _get_repo().create_room(user.user_id)
    return ChatRoomCreateResponseDTO(
        roomId=room.room_id,
        title=room.title,
        createdAt=room.created_at.isoformat(),
    )


async def list_sessions(user: User, page: int, size: int) -> ChatRoomListDataDTO:
    total, rooms = await _get_repo().list_rooms(user.user_id, page, size)
    return ChatRoomListDataDTO(
        totalCount=total,
        items=[
            ChatRoomItemDTO(
                roomId=r.room_id,
                title=r.title,
                createdAt=r.created_at.isoformat(),
                updatedAt=r.updated_at.isoformat(),
            )
            for r in rooms
        ],
    )


async def delete_session(user: User, room_id: int) -> None:
    room = await _get_repo().get_room(room_id, user.user_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")
    await _get_repo().soft_delete_room(room)


# ── 메시지 ────────────────────────────────────────────────────────────────────


async def list_messages(user: User, room_id: int, page: int, size: int) -> ChatRoomMessagesDataDTO:
    room = await _get_repo().get_room(room_id, user.user_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")

    total, messages = await _get_repo().list_messages(room_id, page, size)
    bookmarked_ids = await _get_repo().get_bookmarked_message_ids(room_id)

    return ChatRoomMessagesDataDTO(
        roomId=room.room_id,
        title=room.title,
        totalCount=total,
        messages=[
            ChatMessageItemDTO(
                messageId=m.message_id,
                senderTypeCode=m.sender_type_code,
                content=m.content,
                filterResult=m.filter_result,
                isBookmarked=m.message_id in bookmarked_ids,
                createdAt=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )


# ── SSE 스트리밍 ──────────────────────────────────────────────────────────────


async def validate_session(user: User, session_id: int) -> ChatRoom:
    room = await _get_repo().get_room(session_id, user.user_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    return room


async def stream_chat(room: ChatRoom, user: User, message: str) -> AsyncGenerator[str]:
    """2단계 GPT 호출 — 1단계 분류 후 2단계 스트리밍."""
    session_id = room.room_id

    repo = _get_repo()
    await repo.create_message(session_id, "USER", message, filter_result="PASS")
    if await ChatMessage.filter(room_id=session_id).count() <= 1:
        await repo.update_room_title(room, message[:50])

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    ai_cfg = await _get_ai_settings()
    _, history = await repo.list_messages(session_id, page=1, size=10)
    history_ctx = _build_messages(history[:-1])
    health_ctx = await _build_health_context(user)

    assistant_msg = await repo.create_message(session_id, "ASSISTANT", "", filter_result="PASS")
    yield _sse("message_id", {"messageId": assistant_msg.message_id})

    try:
        # 1단계: 분류
        category = await _classify(client, ai_cfg, message)
        logger.info(
            "[분류] model=%s | input=%.80s | category=%s",
            ai_cfg.model,
            message,
            category,
        )

        # 차단 처리
        if category in ("EMERGENCY", "OTHER"):
            fixed = (
                "🚨 상황이 응급의심됩니다. 즉시 119에 전화하세요."
                if category == "EMERGENCY"
                else "🚫 죄송합니다. 헬스가이드 상담은 건강·의료 관련 질문에만 답변드릴 수 있습니다."
            )
            yield _sse("filter_blocked", {"type": category, "message": fixed})
            assistant_msg.content = fixed
            assistant_msg.filter_result = category
            await assistant_msg.save(
                update_fields=[
                    "content",
                    "filter_result",
                    "prompt_tokens",
                    "completion_tokens",
                ]
            )
            yield _sse("done", "[DONE]")
            return

        # 2단계: 스트리밍 답변
        system_prompt = ai_cfg.system_prompt
        if health_ctx:
            system_prompt += f"\n\n[사용자 건강 정보]\n{health_ctx}"
        if category == "GREETING":
            system_prompt += "\n사용자가 인사를 건넸습니다. 친절하게 인사하고 HealthGuide 서비스를 간략히 소개하세요."
        system_prompt += (
            "\n\n답변은 반드시 300자 이내로 작성하세요."
            "\n반드시 2~3줄로 나누어 작성하세요."
            "\n각 줄은 한 문장씩만 작성하세요."
            "\n불필요한 서론/결론 없이 핵심만 답변하세요."
        )

        async for chunk_sse in _stream_answer(
            client,
            ai_cfg,
            system_prompt,
            history_ctx,
            message,
            assistant_msg.message_id,
            category,
        ):
            yield chunk_sse

    except Exception as e:
        logger.error("스트리밍 오류: %s", e)
        yield _sse("error", {"message": "시스템 점검 중입니다. 잠시 후 다시 시도해주세요."})

    yield _sse("done", "[DONE]")


# ── 1단계: 분류 ───────────────────────────────────────────────────────────────

_ROUTER_PROMPT = (
    "당신은 질문 분류기입니다. 아래 질문을 읽고 카테고리 하나만 출력하세요.\n"
    "EMERGENCY: 즉각적인 응급 처치가 필요한 상황(심정지, 뇌졸중, 심한 출혈, 자살 위기 등), 심장이 아파 라고 하면 EMERGENCY로 반환해.\n"
    "GREETING: 인사, 감사, 안부, 자기소개 요청 등 순수 인사성 메시지\n"
    "DOMAIN: 건강·의료·복약·증상·질병·영양·운동·정신건강 관련 질문\n"
    "OTHER: 그 외 일반 비의료 질문/잡담\n"
    "반드시 EMERGENCY / GREETING / DOMAIN / OTHER 중 하나만 출력하세요."
)

_VALID_CATEGORIES = {"EMERGENCY", "GREETING", "DOMAIN", "OTHER"}


async def _classify(client: AsyncOpenAI, ai_cfg: "AiConfig", message: str) -> str:
    messages = [
        {"role": "system", "content": _ROUTER_PROMPT},
        {"role": "user", "content": message},
    ]
    resp = await client.chat.completions.create(
        **build_create_kwargs(model=ai_cfg.model, max_tokens=200, name="classify"),
        messages=messages,
    )
    result = (resp.choices[0].message.content or "").strip().upper()
    return result if result in _VALID_CATEGORIES else "DOMAIN"


# ── 2단계: 스트리밍 답변 ──────────────────────────────────────────────────────


async def _stream_answer(
    client: AsyncOpenAI,
    ai_cfg: "AiConfig",
    system_prompt: str,
    history_ctx: list[dict],
    message: str,
    message_id: int,
    filter_result: str,
) -> AsyncGenerator[str]:
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _run() -> None:
        redis = get_redis()
        full_content = ""
        prompt_tokens = comp_tokens = 0
        latency_ms: int | None = None
        start_at = time.monotonic()
        input_messages = [
            {"role": "system", "content": system_prompt},
            *history_ctx,
            {"role": "user", "content": message},
        ]
        try:
            stream = await client.chat.completions.create(
                **build_create_kwargs(
                    model=ai_cfg.model,
                    max_tokens=ai_cfg.max_tokens,
                    temperature=ai_cfg.temperature,
                    stream=True,
                    stream_options={"include_usage": True},
                    name="stream_answer",
                ),
                messages=input_messages,
            )
            async for chunk in stream:
                if await redis.exists(f"chat:cancel:{message_id}"):
                    await redis.delete(f"chat:cancel:{message_id}")
                    break
                if chunk.usage:
                    prompt_tokens += chunk.usage.prompt_tokens or 0
                    comp_tokens += chunk.usage.completion_tokens or 0
                if not chunk.choices:
                    continue
                token = chunk.choices[0].delta.content or ""
                if not token:
                    continue
                if latency_ms is None:
                    latency_ms = int((time.monotonic() - start_at) * 1000)
                full_content += token
                await queue.put(_sse("token", {"token": token}))
        except Exception as e:
            logger.error("[_stream_answer] OpenAI 오류: %s", e)
        finally:
            await queue.put(None)
            msg = await ChatMessage.get_or_none(message_id=message_id)
            if msg:
                msg.content = full_content.strip()
                msg.filter_result = filter_result
                msg.prompt_tokens = prompt_tokens
                msg.completion_tokens = comp_tokens
                msg.latency_ms = latency_ms
                msg.model_name = ai_cfg.model
                await msg.save(
                    update_fields=[
                        "content",
                        "filter_result",
                        "prompt_tokens",
                        "completion_tokens",
                        "latency_ms",
                        "model_name",
                    ]
                )
            logger.info(
                "[2단계 완료] model=%s | 응답=%.80s | prompt=%s | completion=%s | latency=%sms",
                ai_cfg.model,
                full_content,
                prompt_tokens,
                comp_tokens,
                latency_ms,
            )

    asyncio.create_task(_run())

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


# ── 취소 ──────────────────────────────────────────────────────────────────────


async def cancel_stream(user: User, message_id: int) -> None:
    msg = await _get_repo().get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 메시지를 찾을 수 없습니다.")
    if msg.content:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 완료된 응답입니다.")
    await get_redis().set(f"chat:cancel:{message_id}", "1", ex=30)


# ── 북마크 ────────────────────────────────────────────────────────────────────


async def add_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    answer_msg = await _get_repo().get_message(message_id)
    if answer_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="메시지를 찾을 수 없습니다.")

    existing = await _get_repo().get_bookmark_by_answer(message_id, user.user_id)
    if existing:
        return BookmarkResponseDTO(bookmarkId=existing.bookmark_id, isBookmarked=True)

    question_msg = (
        await ChatMessage.filter(
            room_id=answer_msg.room_id,
            message_id__lt=message_id,
            sender_type_code="USER",
        )
        .order_by("-message_id")
        .first()
    ) or answer_msg

    bookmark = await _get_repo().create_bookmark(user.user_id, question_msg, answer_msg)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=True)


async def remove_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    bookmark = await _get_repo().get_bookmark_by_answer(message_id, user.user_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="북마크를 찾을 수 없습니다.")
    await _get_repo().delete_bookmark(bookmark)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=False)


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────


@dataclass
class AiConfig:
    model: str
    system_prompt: str
    temperature: float
    max_tokens: int


_DEFAULT_AI_CONFIG = AiConfig(
    model="gpt-4o-mini",
    system_prompt=(
        "당신은 HealthGuide AI 건강 상담 도우미입니다. "
        "사용자의 건강·의료·복약·증상·질병·영양·운동·정신건강 관련 질문에 친절하고 정확하게 답변하세요. "
        "전문 의료 행위를 대체하지 않으며, 심각한 증상은 의사 상담을 권유하세요."
    ),
    temperature=0.7,
    max_tokens=1000,
)

_AI_CONFIG_CACHE: AiConfig | None = None
_AI_CONFIG_CACHE_AT: float = 0.0
_AI_CONFIG_CACHE_TTL: float = 60.0


def _get_repo() -> ChatRepository:
    return ChatRepository()


async def _get_ai_settings() -> AiConfig:
    global _AI_CONFIG_CACHE, _AI_CONFIG_CACHE_AT
    now = time.monotonic()
    if _AI_CONFIG_CACHE is not None and now - _AI_CONFIG_CACHE_AT < _AI_CONFIG_CACHE_TTL:
        return _AI_CONFIG_CACHE
    try:
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            "SELECT api_model, system_prompt, temperature, max_tokens "
            "FROM ai_settings WHERE config_name = $1 AND is_active = TRUE LIMIT 1",
            ["chat"],
        )
        if rows:
            r = rows[0]
            cfg = AiConfig(
                model=r["api_model"],
                system_prompt=r["system_prompt"],
                temperature=float(r["temperature"]),
                max_tokens=int(r["max_tokens"]),
            )
            _AI_CONFIG_CACHE = cfg
            _AI_CONFIG_CACHE_AT = now
            logger.info(
                "[AI설정] model=%s | temperature=%s | max_tokens=%s",
                cfg.model,
                cfg.temperature,
                cfg.max_tokens,
            )
            return cfg
    except Exception as e:
        logger.warning("ai_settings 조회 실패, 기본값 사용: %s", e)
    return _DEFAULT_AI_CONFIG


async def _build_health_context(user: User) -> str:
    parts: list[str] = []
    lifestyle = await UserLifestyle.get_or_none(user_id=user.user_id)
    if lifestyle:
        for attr, label in [
            ("height", "키"),
            ("weight", "몸무게"),
            ("smoking_code", "흡연"),
            ("drinking_code", "음주"),
            ("exercise_code", "운동"),
            ("sleep_time_code", "수면"),
        ]:
            val = getattr(lifestyle, attr, None)
            if val:
                unit = "cm" if attr == "height" else "kg" if attr == "weight" else ""
                parts.append(f"{label}: {val}{unit}")
        if lifestyle.pregnancy_code and lifestyle.pregnancy_code != "NONE":
            parts.append(f"임신/수유: {lifestyle.pregnancy_code}")

    diseases = await UserDisease.filter(user_id=user.user_id).values_list("disease_name", flat=True)
    allergies = await UserAllergy.filter(user_id=user.user_id).values_list("allergy_name", flat=True)
    if diseases:
        parts.append(f"기저질환: {', '.join(diseases)}")
    if allergies:
        parts.append(f"알레르기: {', '.join(allergies)}")
    if user.birth_date:
        parts.append(f"생년월일: {user.birth_date}")
    if user.gender_code:
        parts.append(f"성별: {user.gender_code}")
    return " / ".join(parts)


def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _estimate_tokens(text: str) -> int:
    korean = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
    return korean + (len(text) - korean) // 4 + 1


def _build_messages(history: list[ChatMessage], max_tokens: int = 2000, keep_last: int = 10) -> list[dict]:
    recent = history[-keep_last:]
    if not recent:
        return []
    protected = recent[-2:]
    candidates = recent[:-2]
    token_sum = sum(_estimate_tokens(m.content) for m in candidates)

    if token_sum > max_tokens:
        while candidates and token_sum > max_tokens:
            token_sum -= _estimate_tokens(candidates.pop(0).content)
        result = [
            {
                "role": "system",
                "content": "[이전 대화 요약: 건강 관련 상담이 있었습니다.]",
            }
        ]
        for m in [*candidates, *protected]:
            result.append(
                {
                    "role": "user" if m.sender_type_code == "USER" else "assistant",
                    "content": m.content,
                }
            )
        return result

    return [
        {
            "role": "user" if m.sender_type_code == "USER" else "assistant",
            "content": m.content,
        }
        for m in [*candidates, *protected]
    ]
