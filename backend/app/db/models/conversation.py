from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.base import Base
from app.db.model_utils import (
    new_uuid,
    utc_now,
)


class ConversationThread(Base):
    """
    ConversationThread = 一条对话线程。

    它保存的是“当前聊天”的身份，
    不是长期 WorkSession Memory。
    """

    __tablename__ = (
        "conversation_threads"
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    title: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class ConversationTurn(Base):
    """
    ConversationTurn = 对话中的一轮消息。

    只负责保存 Thread 内的：
    user / assistant message。

    它属于 Short-term Conversation Memory。
    """

    __tablename__ = (
        "conversation_turns"
    )

    __table_args__ = (
        UniqueConstraint(
            "thread_id",
            "sequence",
            name=(
                "uq_conversation_"
                "thread_sequence"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    thread_id: Mapped[
        str
    ] = mapped_column(
        ForeignKey(
            "conversation_threads.id"
        ),
        nullable=False,
        index=True,
    )

    sequence: Mapped[
        int
    ] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 保存 route / verification 等少量元信息。
    metadata_json: Mapped[
        dict
    ] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class RunCheckpoint(Base):
    """
    RunCheckpoint = 一次对话请求的持久化检查点。

    第一版是 request-level checkpoint：
    保存一次 Agent Run 的开始、成功或失败状态。

    它解决：
    - 程序中断后知道哪次请求没完成
    - 可以重新执行失败请求
    - 不让一次长 Agent Run 变成完全黑盒
    """

    __tablename__ = (
        "run_checkpoints"
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    thread_id: Mapped[
        str
    ] = mapped_column(
        ForeignKey(
            "conversation_threads.id"
        ),
        nullable=False,
        index=True,
    )

    # Harness 真正的 run_id
    run_id: Mapped[
        str | None
    ] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    user_message: Mapped[str] = (
        mapped_column(
            Text,
            nullable=False,
        )
    )

    # 实际送进 Supervisor 的 Query。
    # Follow-up 场景下会包含少量 Thread Context。
    effective_query: Mapped[
        str
    ] = mapped_column(
        Text,
        nullable=False,
    )

    response_json: Mapped[
        dict | None
    ] = mapped_column(
        JSON,
        nullable=True,
    )

    error_type: Mapped[
        str | None
    ] = mapped_column(
        String(120),
        nullable=True,
    )

    error_message: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[
        datetime
    ] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
