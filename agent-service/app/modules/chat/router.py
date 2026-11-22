from typing import Annotated

from fastapi import APIRouter, Request, Depends, Header
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.database import get_session
from app.modules.chat.schemas import ChatRequest
from app.modules.chat.service import ChatService
from fastapi.sse import EventSourceResponse, ServerSentEvent
from app.modules.chat_threads.service import ChatThreadService
router = APIRouter(prefix = "/api/v1/chat", tags=["chat"])

def get_agent(request: Request):
    return request.app.state.agent
def get_chat_service(
        session: AsyncSession = Depends(get_session),
        agent: CompiledStateGraph = Depends(get_agent)
):
    return ChatService(agent, session)
@router.post("", response_class=EventSourceResponse)
async def chat(
        request: ChatRequest,
        user_id: Annotated[int, Header(alias="x-user-id")],
        service: ChatService = Depends(get_chat_service)

):
    # 利用sse返回
    # generator 用yield不断生成内容
    async for sse in service.chat_stream(user_id=user_id, request=request):
        yield sse
    # for i in range(10):
    #     yield ServerSentEvent(data=f"message_{i}", event="message")
    # yield ServerSentEvent(data="[DONE]", event="done")

    # return await service.chat_stream(request, user_id)
