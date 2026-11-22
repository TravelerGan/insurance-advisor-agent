from langchain.agents import create_agent
from langchain.agents.middleware import wrap_tool_call
from langchain.chat_models import init_chat_model
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.exc import SQLAlchemyError

from .schemas import InsuranceAgentContext
from .tools import query_candidate_products, save_insurance_plan, query_product_clause

from app.core.config import settings
from app.core.logging import get_logger
logger = get_logger(__name__)


@wrap_tool_call
async def handle_plan_save_error(request, handler):
    try:
        return await handler(request)
    except SQLAlchemyError:
        if request.tool_call["name"] != "save_insurance_plan":
            raise

        logger.exception("保存保险方案失败")
        return ToolMessage(
            content="保险方案保存失败，请告知用户本次未保存成功。",
            tool_call_id=request.tool_call["id"],
            status="error",
        )


SYSTEM_PROMPT = """
你是“安心保”的智能保险顾问。
- 你需要使用专业、准确、容易理解的语言回答用户的保险问题。
- 当信息不足时，应先向用户追问，形成用户画像。
- 给用户推荐保险方案时，必须先查询候选产品，根据用户画像，推荐合适的保险组合，再调用工具保存方案。
- 回答保险产品的条款问题时，必须先调用query_product_clause查询对应产品的保险条款，再根据检索结果回答。
- 你的回答必须是基于检索到的保险条款，不要编造保险条款中没有的信息。如果没有相关条款，如实告知用户。
- 回答中的每个事实陈述必须紧跟[source_id]的引用标记。例如：这款产品的等待期为180天。[ref-001]
- 回答要简短、精确，不要长篇大论。
- 现在是开发debug阶段
"""
# 把这个封装成一个函数 就可以从刚刚infra中的checkpointer直接传入数据库连接池对象
# agent在系统中也是和数据库连接池一样在生命周期钩子函数中调用，这样可以确保agent在系统启动时被初始化，并在系统关闭时被正确关闭。
async def init_insurance_advisor() -> CompiledStateGraph:
    """初始化保险顾问Agent"""
    model = init_chat_model(
        model = settings.llm.chat_model,
        api_key = settings.llm.api_key,
        extra_body={"thinking": {"type": "disabled"}}
    )
    agent = create_agent(
        model = model,
        tools=[query_candidate_products, save_insurance_plan, query_product_clause],
        middleware=[handle_plan_save_error],
        system_prompt=SYSTEM_PROMPT,
        checkpointer=True,
        context_schema=InsuranceAgentContext
    )

    logger.info("保险顾问Agent初始化成功~✅️")
    return agent
