# app/services/chat_service.py
# 채팅 비즈니스 로직 + SSE 스트리밍

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import HTTPException, status
from openai import AsyncOpenAI
from tortoise import Tortoise

from app.core.config import get_settings
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
repo = ChatRepository()


# ── 세션 ──────────────────────────────────────────────────────────────────────


async def create_session(user: User) -> ChatRoomCreateResponseDTO:
    room = await repo.create_room(user.user_id)
    return ChatRoomCreateResponseDTO(
        roomId=room.room_id,
        title=room.title,
        createdAt=room.created_at.isoformat(),
    )


async def list_sessions(user: User, page: int, size: int) -> ChatRoomListDataDTO:
    total, rooms = await repo.list_rooms(user.user_id, page, size)
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
    room = await repo.get_room(room_id, user.user_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다."
        )
    await repo.soft_delete_room(room)


# ── 메시지 ────────────────────────────────────────────────────────────────────


async def list_messages(
    user: User, room_id: int, page: int, size: int
) -> ChatRoomMessagesDataDTO:
    room = await repo.get_room(room_id, user.user_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다."
        )

    total, messages = await repo.list_messages(room_id, page, size)
    bookmarked_ids = await repo.get_bookmarked_message_ids(room_id)

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
    """SSE generator 진입 전 세션 검증 — HTTPException은 generator 밖에서 raise해야 함."""
    room = await repo.get_room(session_id, user.user_id)
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다."
        )
    return room


async def stream_chat(
    room: ChatRoom,
    user: User,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    1회 GPT 호출로 분류(GREETING/DOMAIN/EMERGENCY/OTHER) + 답변 생성.
    세션 검증은 validate_session()에서 미리 수행 후 room을 전달받음.
    yields: SSE 형식 문자열
    """
    session_id = room.room_id

    # 사용자 메시지 저장
    await repo.create_message(session_id, "USER", message, filter_result="PASS")

    # 첫 메시지면 제목 업데이트
    msg_count = await ChatMessage.filter(room_id=session_id).count()
    if msg_count <= 1:
        await repo.update_room_title(room, message[:50])

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # ai_settings DB 조회
    ai_cfg = await _get_ai_settings()

    # 이전 대화 컨텍스트 (최근 10개) + 사용자 헬스 정보
    _, history = await repo.list_messages(session_id, page=1, size=50)
    history_ctx = _build_messages(history[:-1])  # 방금 저장한 user_msg 제외
    health_ctx = await _build_health_context(user)

    system_prompt = (
        f"{ai_cfg.system_prompt}\n\n"
        "[분류 규칙]\n"
        "응답 첫 줄에 반드시 다음 중 하나만 출력하세요: CATEGORY:GREETING / CATEGORY:DOMAIN / CATEGORY:EMERGENCY / CATEGORY:OTHER\n"
        "- EMERGENCY: 즉각적인 응급 처치가 필요한 상황(심정지, 뇌졸중, 심한 출혈, 자살 위기 등) — 다른 분류보다 무조건 우선\n"
        "- GREETING: 인사, 감사, 안부, 자기소개 요청 등 순수 인사성 메시지\n"
        "- DOMAIN: 건강·의료·복약·증상·질병·영양·운동·정신건강 관련 질문\n"
        "- OTHER: 그 외 일반 비의료 질문/잡담\n\n"
        "[분류별 응답 방식]\n"
        "- EMERGENCY: 분류 출력 후 응급 안내만 출력 (추가 답변 없음)\n"
        "- GREETING: 분류 출력 후 친절한 인사와 서비스 소개 출력\n"
        "- DOMAIN: 분류 출력 후 건강 상담 답변 출력\n"
        "- OTHER: 분류 출력 후 건강·의료 질문만 답변 가능하다는 안내 출력\n"
        + (f"\n[사용자 건강 정보]\n{health_ctx}" if health_ctx else "")
    )

    full_content = ""
    assistant_msg = await repo.create_message(
        session_id, "ASSISTANT", "", filter_result="PASS"
    )
    redis = get_redis()

    yield _sse("message_id", {"messageId": assistant_msg.message_id})

    try:
        stream = await client.chat.completions.create(
            model=ai_cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                *history_ctx,
                {"role": "user", "content": message},
            ],
            stream=True,
            max_tokens=ai_cfg.max_tokens,
            temperature=ai_cfg.temperature,
        )

        category: str | None = None
        first_line_buf = ""
        category_parsed = False

        async for chunk in stream:
            cancel_key = f"chat:cancel:{assistant_msg.message_id}"
            if await redis.exists(cancel_key):
                await redis.delete(cancel_key)
                break

            token = chunk.choices[0].delta.content or ""
            if not token:
                continue

            full_content += token

            # 첫 줄에서 CATEGORY 파싱
            if not category_parsed:
                first_line_buf += token
                if "\n" in first_line_buf:
                    first_line = first_line_buf.split("\n")[0].strip()
                    if first_line.startswith("CATEGORY:"):
                        category = first_line.split(":", 1)[1].strip()
                    category_parsed = True

                    # EMERGENCY / OTHER 는 고정 메시지로 교체
                    if category == "EMERGENCY":
                        fixed = "🚨 상황이 응급의심됩니다. 즉시 119에 전화하세요."
                        yield _sse(
                            "filter_blocked", {"type": "EMERGENCY", "message": fixed}
                        )
                        # 스트림 나머지 소비 후 종료
                        async for _ in stream:
                            pass
                        full_content = fixed
                        assistant_msg.filter_result = "EMERGENCY"
                        break
                    elif category == "OTHER":
                        fixed = "🚫 죄송합니다. 헬스가이드 상담은 건강·의료 관련 질문에만 답변드릴 수 있습니다."
                        yield _sse(
                            "filter_blocked", {"type": "OTHER", "message": fixed}
                        )
                        async for _ in stream:
                            pass
                        full_content = fixed
                        assistant_msg.filter_result = "OTHER"
                        break
                    else:
                        # GREETING / DOMAIN: CATEGORY 줄 제외하고 나머지 토큰 스트리밍
                        remainder = first_line_buf[first_line_buf.index("\n") + 1 :]
                        if remainder:
                            yield _sse("token", {"token": remainder})
                else:
                    continue  # 아직 첫 줄 미완성
            else:
                yield _sse("token", {"token": token})

    except Exception as e:
        logger.error("스트리밍 오류: %s", e)
        yield _sse(
            "error", {"message": "⏳ 시스템 점검 중입니다. 잠시 후 다시 시도해주세요."}
        )
    finally:
        # CATEGORY 줄 제거 후 저장
        clean = full_content
        if clean.startswith("CATEGORY:"):
            clean = clean[clean.index("\n") + 1 :] if "\n" in clean else ""
        assistant_msg.content = clean.strip()
        await assistant_msg.save(update_fields=["content", "filter_result"])

    yield _sse("done", "[DONE]")


async def cancel_stream(user: User, message_id: int) -> None:
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="해당 메시지를 찾을 수 없습니다.",
        )
    if msg.content:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="이미 완료된 응답입니다."
        )

    redis = get_redis()
    await redis.set(f"chat:cancel:{message_id}", "1", ex=30)


# ── 북마크 ────────────────────────────────────────────────────────────────────


async def add_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    answer_msg = await repo.get_message(message_id)
    if answer_msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="메시지를 찾을 수 없습니다."
        )

    # 이미 북마크된 경우 기존 반환
    existing = await repo.get_bookmark_by_answer(message_id, user.user_id)
    if existing:
        return BookmarkResponseDTO(bookmarkId=existing.bookmark_id, isBookmarked=True)

    # 직전 USER 메시지 찾기
    question_msg = (
        await ChatMessage.filter(
            room_id=answer_msg.room_id,
            message_id__lt=message_id,
            sender_type_code="USER",
        )
        .order_by("-message_id")
        .first()
    )

    if question_msg is None:
        question_msg = answer_msg  # fallback

    bookmark = await repo.create_bookmark(user.user_id, question_msg, answer_msg)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=True)


async def remove_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    bookmark = await repo.get_bookmark_by_answer(message_id, user.user_id)
    if bookmark is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="북마크를 찾을 수 없습니다."
        )

    await repo.delete_bookmark(bookmark)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=False)


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────


@dataclass
class _AiConfig:
    model: str
    system_prompt: str
    temperature: float
    max_tokens: int


_DEFAULT_AI_CONFIG = _AiConfig(
    model="gpt-4o-mini",
    system_prompt=(
        "당신은 HealthGuide AI 건강 상담 도우미입니다. "
        "사용자의 건강·의료·복약·증상·질병·영양·운동·정신건강 관련 질문에 친절하고 정확하게 답변하세요. "
        "전문 의료 행위를 대체하지 않으며, 심각한 증상은 의사 상담을 권유하세요."
    ),
    temperature=0.7,
    max_tokens=1000,
)


async def _get_ai_settings() -> _AiConfig:
    """ai_settings 테이블에서 config_name='chat' 설정 조회. 없으면 기본값 반환."""
    try:
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            "SELECT api_model, system_prompt, temperature, max_tokens "
            "FROM ai_settings WHERE config_name = $1 AND is_active = TRUE LIMIT 1",
            ["chat"],
        )
        if rows:
            r = rows[0]
            return _AiConfig(
                model=r["api_model"],
                system_prompt=r["system_prompt"],
                temperature=float(r["temperature"]),
                max_tokens=int(r["max_tokens"]),
            )
    except Exception as e:
        logger.warning("ai_settings 조회 실패, 기본값 사용: %s", e)
    return _DEFAULT_AI_CONFIG


async def _build_health_context(user: User) -> str:
    """사용자 헬스 정보를 텍스트로 변환. 정보 없으면 빈 문자열 반환."""
    parts: list[str] = []

    lifestyle = await UserLifestyle.get_or_none(user_id=user.user_id)
    if lifestyle:
        if lifestyle.height:
            parts.append(f"키: {lifestyle.height}cm")
        if lifestyle.weight:
            parts.append(f"몸무게: {lifestyle.weight}kg")
        if lifestyle.smoking_code:
            parts.append(f"흡연: {lifestyle.smoking_code}")
        if lifestyle.drinking_code:
            parts.append(f"음주: {lifestyle.drinking_code}")
        if lifestyle.exercise_code:
            parts.append(f"운동: {lifestyle.exercise_code}")
        if lifestyle.sleep_time_code:
            parts.append(f"수면: {lifestyle.sleep_time_code}")
        if lifestyle.pregnancy_code and lifestyle.pregnancy_code != "NONE":
            parts.append(f"임신/수유: {lifestyle.pregnancy_code}")

    diseases = await UserDisease.filter(user_id=user.user_id).values_list(
        "disease_name", flat=True
    )
    if diseases:
        parts.append(f"기저질환: {', '.join(diseases)}")

    allergies = await UserAllergy.filter(user_id=user.user_id).values_list(
        "allergy_name", flat=True
    )
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


def _build_messages(history: list[ChatMessage]) -> list[dict]:
    """ChatMessage 목록을 OpenAI messages 형식으로 변환 (최근 10개)."""
    result = []
    for msg in history[-10:]:
        role = "user" if msg.sender_type_code == "USER" else "assistant"
        result.append({"role": role, "content": msg.content})
    return result
