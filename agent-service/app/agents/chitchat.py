from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agents.schemas import InsuranceAgentState
from app.core.config import settings
from app.core.logging import get_logger
logger = get_logger(__name__)
# 定义state
class ChitchatState(InsuranceAgentState):
    chitchat_count: int

SYSTEM_MESSAGE = """
你是保险智能客服，负责处理与保险业务无关的普通聊天。

要求：
1. 回复友好、自然，最多两句话。
2. 不假装有个人经历、情感、实时信息或外部能力。
3. 不回答医疗、法律、投资等高风险专业建议。
4. 每次回复都自然引导用户回到保险产品、投保或理赔业务。
5. 超出能力范围时，如实说明无法提供。
""".strip()

MAX_COUNT = 2 # 最大闲聊次数
class ChitchatAgent:
    def __init__(self):
        self.model = init_chat_model(
            "deepseek-v4-flash",
            api_key = settings.llm.api_key,
            extra_body={"thinking":{"type":"disabled"}}
        )

    def chitchat(self, state: ChitchatState):
        count = state.get("chitchat_count", 0) + 1
        if count >= MAX_COUNT:
            logger.info("闲聊次数超过最大值 直接返回固定结果")
            return {"messages": [AIMessage("我主要协助处理保险产品、投保和理赔咨询，请告诉我想办理或了解的事项。")]}

        response = self.model.invoke([
            SystemMessage(content=SYSTEM_MESSAGE),
            *state["messages"]
        ])
        return {
            "messages":[response],
            "chitchat_count": count + 1
        }
    def build(self):
        builder = StateGraph(ChitchatState)
        builder.add_node("chitchat", self.chitchat)

        builder.add_edge(START, "chitchat")
        builder.add_edge("chitchat", END)
        return builder.compile(checkpointer=True)

def init_chitchat_agent():
    return ChitchatAgent().build()
