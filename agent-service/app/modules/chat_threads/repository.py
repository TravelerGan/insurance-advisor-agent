from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chat_threads.models import ChatThread


class ChatThreadRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, chat_thread: ChatThread) -> None:
        self.session.add(chat_thread)

    async def list_by_user(
            self, user_id: int, *, page: int = 1, page_size: int = 6,
    ) -> tuple[list[ChatThread], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(ChatThread)
            .where(ChatThread.user_id == user_id)
        )
        result = await self.session.scalars(
            select(ChatThread)
            .where(ChatThread.user_id == user_id)
            .order_by(
                ChatThread.updated_at.desc(),
                ChatThread.created_at.desc(),
                ChatThread.id.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.all()), total or 0

    # 在做会话名称更新之前得先找到对应的用户id 和 会话id是否能够在数据库中找到数据
    # 不然这个请求就是非法的 不能进行更新
    async def find_owned(
            self,
            user_id: int,
            thread_id: UUID
    ) -> ChatThread | None:
        result = await self.session.scalar(
            select(ChatThread)
            .where(
                ChatThread.user_id == user_id,
                ChatThread.id == thread_id
            )
        )
        return result
    async def delete(self, thread: ChatThread) -> None:
        await self.session.delete(thread)
