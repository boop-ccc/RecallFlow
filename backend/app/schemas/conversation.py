from pydantic import (
    BaseModel,
    Field,
)

from app.schemas.supervisor import (
    SupervisorResponse,
)


class ConversationAskRequest(
    BaseModel
):
    """
    一次 Thread 内的新用户消息。
    """

    thread_id: str | None = None

    message: str = Field(
        min_length=1,
        max_length=5000,
    )


class ConversationAskResponse(
    BaseModel
):
    """
    Conversation Service 对外结果。
    """

    thread_id: str

    checkpoint_id: str

    result: SupervisorResponse


class ConversationTurnView(
    BaseModel
):
    sequence: int
    role: str
    content: str
    metadata: dict = Field(
        default_factory=dict
    )
