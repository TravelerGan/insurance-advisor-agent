from typing import Any
from uuid import UUID

from pydantic import Field

from app.common.schemas import BaseSchema

class ChatRequest(BaseSchema):
    """基础chat接口的请求体"""
    thread_id: UUID
    message: str | None = Field(default=None, min_length=1)
    decision: dict[str, Any] | None = None
