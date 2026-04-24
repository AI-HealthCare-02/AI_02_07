# app/apis/v1/chat.py

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user
from app.dtos.chat_dto import (
    BookmarkResponseDTO,
    ChatRoomCreateResponseDTO,
    ChatRoomListDataDTO,
    ChatRoomMessagesDataDTO,
    ChatSendRequestDTO,
)
from app.dtos.common_dto import ResponseDTO
from app.models.user import User
from app.services import chat_service

router = APIRouter()


# ── 세션 ──────────────────────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=ResponseDTO[ChatRoomCreateResponseDTO],
    status_code=status.HTTP_201_CREATED,
    summary="새 대화 세션 생성",
)
async def create_session(user: User = Depends(get_current_user)):
    data = await chat_service.create_session(user)
    return ResponseDTO(success=True, message="새 대화가 시작되었습니다.", data=data)


@router.get(
    "/sessions",
    response_model=ResponseDTO[ChatRoomListDataDTO],
    summary="대화 세션 목록 조회",
)
async def list_sessions(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
):
    data = await chat_service.list_sessions(user, page, size)
    return ResponseDTO(success=True, message="조회 성공", data=data)


@router.get(
    "/sessions/{room_id}/messages",
    response_model=ResponseDTO[ChatRoomMessagesDataDTO],
    summary="대화 메시지 이력 조회",
)
async def list_messages(
    room_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
):
    data = await chat_service.list_messages(user, room_id, page, size)
    return ResponseDTO(success=True, message="조회 성공", data=data)


@router.delete(
    "/sessions/{room_id}",
    response_model=ResponseDTO,
    summary="대화 세션 삭제",
)
async def delete_session(room_id: int, user: User = Depends(get_current_user)):
    await chat_service.delete_session(user, room_id)
    return ResponseDTO(success=True, message="대화가 삭제되었습니다.")


# ── 메시지 전송 (SSE) ─────────────────────────────────────────────────────────


@router.post(
    "/send",
    summary="메시지 전송 (SSE 스트리밍)",
    response_class=StreamingResponse,
)
async def send_message(
    body: ChatSendRequestDTO,
    user: User = Depends(get_current_user),
):
    # generator 진입 전 세션 검증 — HTTPException이 정상적으로 응답됨
    room = await chat_service.validate_session(user, body.sessionId)
    return StreamingResponse(
        chat_service.stream_chat(room, user, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/send/{message_id}/cancel",
    response_model=ResponseDTO,
    summary="스트리밍 응답 취소",
)
async def cancel_stream(message_id: int, user: User = Depends(get_current_user)):
    await chat_service.cancel_stream(user, message_id)
    return ResponseDTO(success=True, message="응답 생성이 중단되었습니다.")


# ── 북마크 ────────────────────────────────────────────────────────────────────


@router.post(
    "/messages/{message_id}/bookmark",
    response_model=ResponseDTO[BookmarkResponseDTO],
    summary="북마크 저장",
)
async def add_bookmark(message_id: int, user: User = Depends(get_current_user)):
    data = await chat_service.add_bookmark(user, message_id)
    return ResponseDTO(success=True, message="북마크가 저장되었습니다.", data=data)


@router.delete(
    "/messages/{message_id}/bookmark",
    response_model=ResponseDTO[BookmarkResponseDTO],
    summary="북마크 해제",
)
async def remove_bookmark(message_id: int, user: User = Depends(get_current_user)):
    data = await chat_service.remove_bookmark(user, message_id)
    return ResponseDTO(success=True, message="북마크가 해제되었습니다.", data=data)
