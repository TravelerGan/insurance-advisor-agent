import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

from app.agents.orchestrator import init_insurance_orchestrator
from app.core.exceptions import ApplicationError
from app.core.logging import configure_logging, get_logger
from app.core.config import settings
from app.modules.chat_threads.exceptions import ChatThreadNotFoundError

configure_logging(settings.logging.level)
logger = get_logger(__name__)

#初始化生命周期钩子
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("项目启动中， 正在初始化...")
    from app.infra.database import check_database, close_database
    from app.infra.checkpointer import init_checkpointer, close_checkpointer
    from app.agents.insurance_advisor import init_insurance_advisor
    from app.rag import close_rag  # 导入模块就会初始化
    try:
        await check_database()
        checkpointer = await init_checkpointer()
        app.state.agent = await init_insurance_orchestrator(checkpointer)
        yield
    finally:
        logger.info("应用关闭中... ")
        close_rag()
        await close_database()
        await close_checkpointer()


# 初始化fastapi
app = FastAPI(
    title=settings.app.name,
    debug=settings.app.debug,
    lifespan=lifespan
)

from app.modules.product.router import router as product_router
from app.modules.chat_threads.router import router as chat_threads_router
from app.modules.chat.router import router as chat_router

app.include_router(product_router)
app.include_router(chat_threads_router)
app.include_router(chat_router)


@app.get("/healthy", summary="检查健康服务是否正常")
async def healthy() -> dict[str, str]:
    logger.info("执行接口健康检查")
    return {"status": "ok"}

# 统一处理异常信息，发现是ChatThreadNotFoundError，返回对应的错误状态码和错误信息
@app.exception_handler(ApplicationError)
def handle_exception(request: Request, exc: ApplicationError):
    logger.error(f"处理异常, 请求路径: {request.url}, 异常信息: {exc}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        loop = "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
    )
