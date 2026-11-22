from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, Request
from fastapi.params import Header
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status


from app.common.schemas import PageResult
from app.infra.database import get_session
from app.modules.chat_threads.schemas import ChatThreadResponse, ChatThreadCreate, ChatHistoryResponse
from app.modules.chat_threads.service import ChatThreadService

router = APIRouter(prefix = "/api/v1/chat-threads", tags=["chat_threads"])

def get_chat_threads_service(request: Request, session: AsyncSession=Depends(get_session)):
    return ChatThreadService(session, request.app.state.agent)


@router.post("", response_model=ChatThreadResponse)
async def create_chat_thread(
    request: ChatThreadCreate,
    user_id: Annotated[int, Header(alias="x-user-id")],
    service: ChatThreadService = Depends(get_chat_threads_service)
):
    return await service.add(user_id, request.title)

@router.get("", response_model=PageResult[ChatThreadResponse])
async def list_by_user(
    user_id: Annotated[int, Header(alias="x-user-id")],
    page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(default=6, ge=1, le=100, description="每页条数"),
    service: ChatThreadService = Depends(get_chat_threads_service)
) -> PageResult[ChatThreadResponse]:
    return await service.list_by_user(user_id, page=page, page_size=page_size)

@router.patch("/{thread_id}", response_model=ChatThreadResponse)
async def rename_chat_thread(
    request: ChatThreadCreate,
    user_id: Annotated[int, Header(alias="x-user-id")],
    thread_id: UUID,
    service: ChatThreadService = Depends(get_chat_threads_service)
):
    return await service.rename(user_id, thread_id, request.title)

@router.delete("/{thread_id}")
async def delete_thread(
    user_id: Annotated[int, Header(alias="x-user-id")],
    thread_id: UUID,
    service: ChatThreadService = Depends(get_chat_threads_service)
) -> Response:
    await service.delete(user_id, thread_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{thread_id}/messages", response_model=ChatHistoryResponse)
async def get_messages(
    thread_id: UUID,
    user_id: Annotated[int, Header(alias="x-user-id")],
    service: ChatThreadService = Depends(get_chat_threads_service)
):
    return await service.get_history_message(thread_id, user_id)
