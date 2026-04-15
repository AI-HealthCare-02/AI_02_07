# app/models/chat.py
# chat_rooms / chat_messages / chat_bookmarks 테이블 매핑

from tortoise import fields
from tortoise.models import Model


class ChatRoom(Model):
    room_id = fields.BigIntField(pk=True, generated=True)
    user_id = fields.BigIntField(description="users.user_id")
    title = fields.CharField(max_length=200, default="새로운 대화")
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "chat_rooms"
        ordering = ["-updated_at"]


class ChatMessage(Model):
    message_id = fields.BigIntField(pk=True, generated=True)
    room_id = fields.BigIntField(description="chat_rooms.room_id")
    sender_type_grp = fields.CharField(max_length=20, default="SENDER_TYPE")
    sender_type_code = fields.CharField(max_length=20)  # USER | ASSISTANT
    content = fields.TextField()
    filter_result = fields.CharField(max_length=20, null=True)  # PASS | DOMAIN | EMERGENCY
    prompt_tokens = fields.IntField(null=True)      # 입력 토큰 합산
    completion_tokens = fields.IntField(null=True)   # 출력 토큰 합산
    latency_ms = fields.IntField(null=True)          # 첫 토큰까지 응답시간(ms)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_messages"
        ordering = ["created_at"]


class ChatBookmark(Model):
    bookmark_id = fields.BigIntField(pk=True, generated=True)
    user_id = fields.BigIntField()
    question_message_id = fields.BigIntField(null=True)
    answer_message_id = fields.BigIntField(null=True)
    question_content = fields.TextField()
    answer_content = fields.TextField()
    memo = fields.TextField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "chat_bookmarks"
        ordering = ["-created_at"]
