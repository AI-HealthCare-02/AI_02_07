# app/repositories/chat_repository.py

from app.models.chat import ChatBookmark, ChatMessage, ChatRoom


class ChatRepository:

    # ── 세션 ──────────────────────────────────

    async def create_room(self, user_id: int) -> ChatRoom:
        return await ChatRoom.create(user_id=user_id)

    async def get_room(self, room_id: int, user_id: int) -> ChatRoom | None:
        return await ChatRoom.get_or_none(room_id=room_id, user_id=user_id, is_active=True)

    async def list_rooms(self, user_id: int, page: int, size: int) -> tuple[int, list[ChatRoom]]:
        qs = ChatRoom.filter(user_id=user_id, is_active=True)
        total = await qs.count()
        items = await qs.offset((page - 1) * size).limit(size)
        return total, items

    async def soft_delete_room(self, room: ChatRoom) -> None:
        room.is_active = False
        await room.save(update_fields=["is_active"])

    async def update_room_title(self, room: ChatRoom, title: str) -> None:
        room.title = title
        await room.save(update_fields=["title", "updated_at"])

    # ── 메시지 ────────────────────────────────

    async def create_message(
        self,
        room_id: int,
        sender_type_code: str,
        content: str,
        filter_result: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> ChatMessage:
        return await ChatMessage.create(
            room_id=room_id,
            sender_type_code=sender_type_code,
            content=content,
            filter_result=filter_result,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def get_message(self, message_id: int) -> ChatMessage | None:
        return await ChatMessage.get_or_none(message_id=message_id)

    async def list_messages(
        self, room_id: int, page: int, size: int
    ) -> tuple[int, list[ChatMessage]]:
        qs = ChatMessage.filter(room_id=room_id)
        total = await qs.count()
        items = await qs.order_by("message_id").offset((page - 1) * size).limit(size)
        return total, items

    async def get_bookmarked_message_ids(self, room_id: int) -> set[int]:
        bookmarks = await ChatBookmark.filter(answer_message_id__in=(
            await ChatMessage.filter(room_id=room_id).values_list("message_id", flat=True)
        ))
        ids: set[int] = set()
        for b in bookmarks:
            if b.question_message_id:
                ids.add(b.question_message_id)
            if b.answer_message_id:
                ids.add(b.answer_message_id)
        return ids

    # ── 북마크 ────────────────────────────────

    async def get_bookmark_by_answer(self, answer_message_id: int, user_id: int) -> ChatBookmark | None:
        return await ChatBookmark.get_or_none(answer_message_id=answer_message_id, user_id=user_id)

    async def create_bookmark(
        self,
        user_id: int,
        question_msg: ChatMessage,
        answer_msg: ChatMessage,
    ) -> ChatBookmark:
        return await ChatBookmark.create(
            user_id=user_id,
            question_message_id=question_msg.message_id,
            answer_message_id=answer_msg.message_id,
            question_content=question_msg.content,
            answer_content=answer_msg.content,
        )

    async def delete_bookmark(self, bookmark: ChatBookmark) -> None:
        await bookmark.delete()
