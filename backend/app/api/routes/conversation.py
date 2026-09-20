from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.db.session import get_db
from app.schemas.conversation import (
    ConversationAskRequest,
    ConversationAskResponse,
)
from app.services.conversation_service import (
    ConversationService,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["conversation"],
)


@router.post(
    "/ask",
    response_model=(
        ConversationAskResponse
    ),
)
async def ask(
    payload: ConversationAskRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> ConversationAskResponse:
    """
    Ask API
    = RecallFlow 对外 Agent 入口。

    thread_id 为空：
    创建新 Conversation Thread。

    thread_id 已存在：
    继续同一长对话。
    """

    service = ConversationService(
        db
    )

    try:
        return await service.ask(
            thread_id=(
                payload.thread_id
            ),
            message=payload.message,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.post(
    "/threads/{thread_id}/retry",
    response_model=(
        ConversationAskResponse
    ),
)
async def retry_failed_run(
    thread_id: str,
    db: AsyncSession = Depends(
        get_db
    ),
) -> ConversationAskResponse:
    """
    Retry API
    = 失败 Checkpoint 的请求级恢复入口。
    """

    service = ConversationService(
        db
    )

    try:
        return await (
            service.retry_latest_failed(
                thread_id=thread_id
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
