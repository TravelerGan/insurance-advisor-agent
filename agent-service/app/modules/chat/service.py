from fastapi.sse import ServerSentEvent
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.stream import CustomTransformer
from langgraph.types import Command
from sqlalchemy.ext.asyncio import AsyncSession
from aiostream import stream as astream
from app.agents.schemas import InsuranceAgentContext, AdditionalInfo
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_threads.exceptions import ChatThreadNotFoundError
from app.modules.chat_threads.repository import ChatThreadRepository
from app.core.logging import get_logger
logger = get_logger(__name__)

class ChatService:
    def __init__(self, agent: CompiledStateGraph, session: AsyncSession):
        self.agent = agent
        self.repository = ChatThreadRepository(session)

    async def chat_stream(self, request: ChatRequest, user_id: int):
        # 校验当前会话是否属于当前用户
        thread = await self.repository.find_owned(user_id, request.thread_id)
        if not thread:
            raise ChatThreadNotFoundError

        if request.decision:
            _input = Command(resume=request.decision)
        else:
            _input = {"messages": [HumanMessage(content=request.message)]}
        config: RunnableConfig = {"configurable": {"thread_id": str(request.thread_id)}}
        context = InsuranceAgentContext(user_id=user_id)
        stream = await self.agent.astream_events(
            _input, config, context = context, version="v3",
            transformers=[CustomTransformer]
        )

        # 2.2.1.记录AIMessage的ID和引用信息
        final_message_id: str | None = None
        additional_info: AdditionalInfo = {}

        async for event in stream:
            # logger.info(event)
            method = event['method']
            # 判断事件类型，可以是messages、interrupts等等
            if method == 'messages':
                data = event['params']['data'][0]
                if isinstance(data, AIMessage):
                    yield ServerSentEvent(data=data.content, event="message")
                elif data.get('delta') and data['delta'].get('text'):
                    yield ServerSentEvent(data=data['delta'].get('text'), event="message")
                elif data.get('event') == 'message-start' and data.get('id'):
                    # 第一个消息片段会传递Message的id
                    final_message_id = data.get('id')

            if method == 'custom':
                data = event["params"]["data"]
                if isinstance(data, dict) and data.get("type") == "additional_info":
                    additional_info = data.get("data", {})
                    yield ServerSentEvent(data=additional_info, event="additional_info")

        interrupts = await stream.interrupts()
        for item in interrupts:
            yield ServerSentEvent(data=item.value, event="interrupt")

        if final_message_id and additional_info:
            # 将additional_info更新到state中
            await self.agent.aupdate_state(
                config,
                {"additional_info": {final_message_id: additional_info}}
            )
        yield ServerSentEvent(data="[DONE]", event="done")
