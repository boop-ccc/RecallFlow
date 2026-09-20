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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_utils import new_uuid, utc_now


class WorkSession(Base):
    """
    WorkSession = 工作会话

    表示一段连续、有共同目标的工作过程。

    例如：
    09:00 - 09:40
    用户一直在研究 Agent Memory。
    """

    __tablename__ = "work_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    # Session 开始时间
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Session 结束时间
    ended_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # 后面由 LLM / Memory 模块生成。
    # 例如：“Agent Memory 架构研究”
    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 后面生成这次工作做了什么、得到什么结论。
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        
    )
        # Keywords = 关键词
    # 后面 Retrieval 检索会用。
    keywords: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )

    # Open Tasks = 未完成任务
    # 用于之后恢复工作。
    open_tasks: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class WorkSessionItem(Base):
    """
    WorkSessionItem = 工作会话成员

    用来记录：
    哪一个 Activity 属于哪一个 WorkSession。
    """

    __tablename__ = "work_session_items"

    __table_args__ = (
        # 同一个 Activity 只能属于一个 WorkSession。
        UniqueConstraint(
            "activity_id",
            name="uq_work_session_activity",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    # Foreign Key = 外键
    # 表示属于哪个 WorkSession。
    session_id: Mapped[str] = mapped_column(
        ForeignKey("work_sessions.id"),
        nullable=False,
        index=True,
    )

    # 对应原始 ActivityEvent。
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("activity_events.id"),
        nullable=False,
        index=True,
    )

    # Activity 在 Session 中的顺序。
    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )