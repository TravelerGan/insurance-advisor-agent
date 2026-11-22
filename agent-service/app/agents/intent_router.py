import re
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.schemas import RouteResult
from app.core.config import settings
from app.core.logging import get_logger
logger = get_logger(__name__)

SYSTEM_PROMPT = """
你是保险商城智能客服的意图识别节点，请判断用户消息应该交给哪个工作流。

intent只能从以下选项中选择：
- recommendation_plan：保险产品咨询、产品条款、保险推荐、方案管理和投保咨询
- claim：报案、理赔责任、理赔材料、理赔流程和理赔进度
- human_handoff：投诉、高风险问题或用户明确要求人工服务
- chitchat：与保险业务无关的普通聊天
- fallback：无法判断用户意图
""".strip()

class IntentRouter:
    def __init__(self):
        model = init_chat_model(
            "deepseek-v4-flash",
            api_key = settings.llm.api_key,
            extra_body={"thinking":{"type":"disabled"}}
        )
        self.route_model = model.with_structured_output(RouteResult)

    def route(
        self,
        query: str,
        context: str
    ) -> RouteResult | str:
        try:
            # 寒暄识别
            intent = match_social_intent(query)
            if intent:
                return response_by_social_intent(intent)
            # 基于模型的意图识别
            result: RouteResult = self.route_model.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=f"用户问题:{query}\n 历史上下文:{context}\n")
            ])
        except:
            result = RouteResult(intent = "fallback", reason = "意图识别失败")
        logger.info(f"意图识别成功, intent:{result.intent}, reason:{result.reason}")
        return result

# 基于规则的识别是否为寒暄

# 寒暄类型枚举
SocialIntent = Literal["greeting", "thanks", "goodbye"]
# 寒暄的匹配规则
SOCIAL_PATTERNS = {
    "greeting": (
        r"(你|您)?好(呀|啊|哦)?",
        r"嗨",
        r"哈喽",
        r"hello",
        r"hi",
        r"在吗",
    ),
    "thanks": (
        r"谢谢(你|您)?",
        r"多谢(你|您)?",
        r"感谢(你|您)?",
        r"辛苦了",
    ),
    "goodbye": (
        r"再见",
        r"拜拜",
        r"先这样",
        r"没事了",
    ),
}
# 寒暄的固定回复
SOCIAL_RESPONSES = {
    "greeting": "您好，我是您的保险顾问，可以帮您咨询产品、推荐方案或办理理赔。",
    "thanks": "不客气，后续有保险问题可以随时问我。",
    "goodbye": "好的，后续需要帮助时随时联系我。",
}

def normalize_message(message: str) -> str:
    """格式化消息，去掉无效字符"""

    return re.sub(r"[\s，。！？、,.!?~～]", "", message).lower()


def match_social_intent(message: str) -> SocialIntent | None:
    """基于规则匹配的路由"""

    normalized = normalize_message(message)
    for intent, patterns in SOCIAL_PATTERNS.items():
        if any(re.fullmatch(pattern, normalized) for pattern in patterns):
            return intent
    return None

def response_by_social_intent(intent: SocialIntent):
    """根据规则识别出的意图返回固定回复"""

    return SOCIAL_RESPONSES.get(intent)


router = IntentRouter()
