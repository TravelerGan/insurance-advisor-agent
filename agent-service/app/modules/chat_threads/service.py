from uuid import UUID

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.schemas import PageResult
from app.modules.chat_threads.schemas import ChatThreadResponse, ChatHistoryResponse, ChatMessageResponse
from app.modules.chat_threads.exceptions import ChatThreadNotFoundError
from app.modules.chat_threads.models import ChatThread
from app.modules.chat_threads.repository import ChatThreadRepository


class ChatThreadService:
    def __init__(self, session: AsyncSession, agent: CompiledStateGraph):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def add(self, user_id: int, title: str) -> ChatThread:
        # 用上下文管理器管理事务 若执行成功则直接commit 执行失败抛出异常自动rollback
        async with self.repository.session.begin():
            # 创建对象映射到数据库的一条数据
            chat_thread = ChatThread(user_id = user_id, title = title)
            await self.repository.add(chat_thread)
            return chat_thread

    async def list_by_user(
            self, user_id: int, *, page: int = 1, page_size: int = 6,
    ) -> PageResult[ChatThreadResponse]:
        items, total = await self.repository.list_by_user(
            user_id, page=page, page_size=page_size,
        )
        return PageResult[ChatThreadResponse](
            items=items, page=page, page_size=page_size, total=total,
        )

    async def rename(self, user_id: int, thread_id: UUID, title: str) -> ChatThread | None:
        async with self.repository.session.begin():
            chat_thread = await self.repository.find_owned(user_id, thread_id)
            if not chat_thread:
                raise ChatThreadNotFoundError

            chat_thread.title = title
            # 获取更新后的会话数据进行返回
            await self.repository.session.flush()
            await self.repository.session.refresh(chat_thread)
            return chat_thread

    async def delete(
            self,
            user_id: int,
            thread_id: UUID
    ) -> None:
        async with self.repository.session.begin():
            thread = await self.repository.find_owned(user_id = user_id, thread_id = thread_id)
            if thread is None:
                raise ChatThreadNotFoundError
            await self.agent.checkpointer.adelete_thread(str(thread_id))
            await self.repository.delete(thread)

    async def get_history_message(
            self,
            thread_id: UUID,
            user_id: int
    ) -> ChatHistoryResponse:
        thread = await self.repository.find_owned(user_id, thread_id)
        if thread is None:
            raise ChatThreadNotFoundError

        # 读取agent的最新状态
        config: RunnableConfig = {"configurable":{"thread_id": str(thread_id)}}
        snapshot = await self.agent.aget_state(config)
        additional_infos = snapshot.values.get("additional_infos", {})

        messages = []
        # 用get是因为当一个会话刚开始的时候是空的 是无法取出messages的
        for message in snapshot.values.get("messages", []):
            if isinstance(message, HumanMessage):
                role = "user"
            elif isinstance(message, AIMessage):
                role = "assistant"
            else:
                continue

            if message.text:
                messages.append(
                    ChatMessageResponse(
                        role = role,
                        content = message.text,
                        additional_infos=additional_infos.get(message.id)
                    ))

        # 5.处理interrupt
        interrupts = None
        if hasattr(snapshot, 'interrupts') and snapshot.interrupts:
            interrupts = snapshot.interrupts
        elif hasattr(snapshot, 'tasks') and snapshot.tasks:
            for task in snapshot.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    interrupts = task.interrupts
                    break

        return ChatHistoryResponse(
            thread_id=thread_id,
            messages=messages,
            interrupt=interrupts[0].value if interrupts else None
        )
