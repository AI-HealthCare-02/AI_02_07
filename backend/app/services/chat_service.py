# app/services/chat_service.py
# 채팅 비즈니스 로직 + SSE 스트리밍

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import HTTPException, status
from openai import AsyncOpenAI

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")
    await repo.soft_delete_room(room)


# ── 메시지 ────────────────────────────────────────────────────────────────────

async def list_messages(user: User, room_id: int, page: int, size: int) -> ChatRoomMessagesDataDTO:
    room = await repo.get_room(room_id, user.user_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="대화를 찾을 수 없습니다.")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="세션을 찾을 수 없습니다.")
    return room


async def stream_chat(
    room: ChatRoom,
    user: User,
    message: str,
) -> AsyncGenerator[str, None]:
    """
    3단계 필터링 → SSE 스트리밍 응답 생성기.
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
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)  # OPENAI_API_KEY from env

    # ── 1단계: 도메인 필터 ──
    domain_result = await _check_domain(client, message)
    if not domain_result:
        blocked_msg = "🚫 죄송합니다. 헬스가이드 챗봇은 건강·의료·복약 관련 질문에만 답변드릴 수 있습니다."
        await repo.create_message(session_id, "ASSISTANT", blocked_msg, filter_result="DOMAIN")
        yield _sse("filter_blocked", {"type": "DOMAIN", "message": blocked_msg})
        yield _sse("done", "[DONE]")
        return

    # ── 2단계: 응급 필터 ──
    emergency_result = await _check_emergency(client, message)
    if emergency_result:
        blocked_msg = "🚨 응급 상황이 의심됩니다. 즉시 119에 전화하세요."
        await repo.create_message(session_id, "ASSISTANT", blocked_msg, filter_result="EMERGENCY")
        yield _sse("filter_blocked", {"type": "EMERGENCY", "message": blocked_msg})
        yield _sse("done", "[DONE]")
        return

    # ── 3단계: 답변 생성 (스트리밍) ──
    # 이전 대화 컨텍스트 (최근 10개)
    _, history = await repo.list_messages(session_id, page=1, size=50)
    messages_ctx = _build_messages(history[:-1])  # 방금 저장한 user_msg 제외 (마지막에 추가)
    messages_ctx.append({"role": "user", "content": message})

    full_content = ""
    # 취소 처리를 위해 먼저 빈 레코드 생성
    assistant_msg = await repo.create_message(session_id, "ASSISTANT", "", filter_result="PASS")
    redis = get_redis()

    # 메시지 ID를 먼저 전송 (프론트에서 북마크 등에 활용)
    yield _sse("message_id", {"messageId": assistant_msg.message_id})

    try:
        stream = await client.chat.completions.create(
            model="gpt-4o-mini",  # OpenAI GPT-4o mini
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 HealthGuide AI 건강 상담 도우미입니다. "
                        "사용자의 건강·의료·복약 관련 질문에 친절하고 정확하게 답변하세요. "
                        "전문 의료 행위를 대체하지 않으며, 심각한 증상은 의사 상담을 권유하세요."
                    ),
                },
                *messages_ctx,
            ],
            stream=True,
            max_tokens=1000,
            temperature=0.7,
        )

        async for chunk in stream:
            # 취소 플래그 확인
            cancel_key = f"chat:cancel:{assistant_msg.message_id}"
            if await redis.exists(cancel_key):
                await redis.delete(cancel_key)
                break

            token = chunk.choices[0].delta.content or ""
            if token:
                full_content += token
                yield _sse("token", {"token": token})

    except Exception as e:
        logger.error("스트리밍 오류: %s", e)
        yield _sse("error", {"message": "⏳ 시스템 점검 중입니다. 잠시 후 다시 시도해주세요."})
    finally:
        # 스트리밍 완료/취소/오류 모두 최종 내용 저장
        assistant_msg.content = full_content
        await assistant_msg.save(update_fields=["content"])

    yield _sse("done", "[DONE]")


async def cancel_stream(user: User, message_id: int) -> None:
    msg = await repo.get_message(message_id)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="해당 메시지를 찾을 수 없습니다.")
    if msg.content:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 완료된 응답입니다.")

    redis = get_redis()
    await redis.set(f"chat:cancel:{message_id}", "1", ex=30)


# ── 북마크 ────────────────────────────────────────────────────────────────────

async def add_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    answer_msg = await repo.get_message(message_id)
    if answer_msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="메시지를 찾을 수 없습니다.")

    # 이미 북마크된 경우 기존 반환
    existing = await repo.get_bookmark_by_answer(message_id, user.user_id)
    if existing:
        return BookmarkResponseDTO(bookmarkId=existing.bookmark_id, isBookmarked=True)

    # 직전 USER 메시지 찾기
    question_msg = await ChatMessage.filter(
        room_id=answer_msg.room_id,
        message_id__lt=message_id,
        sender_type_code="USER",
    ).order_by("-message_id").first()

    if question_msg is None:
        question_msg = answer_msg  # fallback

    bookmark = await repo.create_bookmark(user.user_id, question_msg, answer_msg)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=True)


async def remove_bookmark(user: User, message_id: int) -> BookmarkResponseDTO:
    bookmark = await repo.get_bookmark_by_answer(message_id, user.user_id)
    if bookmark is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="북마크를 찾을 수 없습니다.")

    await repo.delete_bookmark(bookmark)
    return BookmarkResponseDTO(bookmarkId=bookmark.bookmark_id, isBookmarked=False)


# ── 내부 헬퍼 ─────────────────────────────────────────────────────────────────

def _sse(event: str, data: dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _check_domain(client: AsyncOpenAI, message: str) -> bool:
    """건강/의료 도메인 여부 확인. True = 통과."""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
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
        max_tokens=5,
        temperature=0,
    )
    answer = resp.choices[0].message.content or ""
    return "YES" in answer.upper()


async def _check_emergency(client: AsyncOpenAI, message: str) -> bool:
    """응급 상황 여부 확인. True = 응급."""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",
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
        max_tokens=5,
        temperature=0,
    )
    answer = resp.choices[0].message.content or ""
    return "YES" in answer.upper()


def _build_messages(history: list[ChatMessage]) -> list[dict]:
    """ChatMessage 목록을 OpenAI messages 형식으로 변환."""
    result = []
    for msg in history[-10:]:  # 최근 10개만
        role = "user" if msg.sender_type_code == "USER" else "assistant"
        result.append({"role": role, "content": msg.content})
    return result
