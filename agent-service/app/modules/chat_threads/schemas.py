from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, field_validator

from app.common.schemas import BaseSchema


class ChatThreadCreate(BaseSchema):
    title: str = Field(default="新会话", min_length=1, max_length=200)
    # 在创建会话时，对标题进行预处理，去除首尾空格
    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

class ChatThreadResponse(BaseSchema):
    """会话响应"""
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

from typing import Any, Literal

from pydantic import BaseModel


class ChatMessageResponse(BaseModel):
    """历史消息"""

    role: Literal["user", "assistant"]
    content: str


class ChatHistoryResponse(BaseModel):
    """会话历史响应"""

    thread_id: UUID
    messages: list[ChatMessageResponse]
