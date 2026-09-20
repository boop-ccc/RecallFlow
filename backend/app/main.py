from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.routes.capture import (
    router as capture_router,
)
from app.api.routes.conversation import (
    router as conversation_router,
)
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "RecallFlow — Personal Work "
        "Recovery Multi-Agent System"
    ),
)


# Demo 阶段允许 Chrome Extension
# 从 chrome-extension:// origin 调用 localhost。
#
# 生产环境应该限制 allow_origins，
# 不应长期使用 "*"。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """
    Health Check
    = 服务健康检查。
    """

    return {
        "status": "ok",
        "service":
            settings.app_name,
        "version": "0.2.0",
    }


app.include_router(
    capture_router
)

app.include_router(
    conversation_router
)
