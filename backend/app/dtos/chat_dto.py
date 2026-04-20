# app/dtos/chat_dto.py

from pydantic import BaseModel, Field

# ── 세션 ──────────────────────────────────────


class ChatRoomCreateResponseDTO(BaseModel):
    roomId: int
    title: str
    createdAt: str


class ChatRoomItemDTO(BaseModel):
    roomId: int
    title: str
    createdAt: str
    updatedAt: str


class ChatRoomListDataDTO(BaseModel):
    totalCount: int
    items: list[ChatRoomItemDTO]


# ── 메시지 ────────────────────────────────────


class ChatMessageItemDTO(BaseModel):
    messageId: int
    senderTypeCode: str
    content: str
    filterResult: str | None
    isBookmarked: bool
    createdAt: str


class ChatRoomMessagesDataDTO(BaseModel):
    roomId: int
    title: str
    totalCount: int
    messages: list[ChatMessageItemDTO]


# ── 전송 ──────────────────────────────────────


class ChatSendRequestDTO(BaseModel):
    sessionId: int = Field(..., description="대화 세션 roomId")
    message: str = Field(..., min_length=1, max_length=2000)


# ── 북마크 ────────────────────────────────────


class BookmarkResponseDTO(BaseModel):
    bookmarkId: int
    isBookmarked: bool
