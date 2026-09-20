from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.model_utils import new_uuid, utc_now


class Resource(Base):
    """
    Resource = 资源身份

    解决：
    “这个东西是谁？”

    例如：
    - 一个网页
    - 一个 GitHub Repo
    - 一个本地文件
    """

    __tablename__ = "resources"

    # source_type + locator 不能重复。
    # 例如 web + https://xxx.com 唯一表示一个网页。
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "locator",
            name="uq_resource_source_locator",
        ),
    )

    # Primary Key = 主键
    # 系统内部唯一 ID。
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    # Resource Type = 资源类型
    # web / file / github / chat
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    # Locator = 资源定位符
    # 网页就是 URL。
    locator: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    # 最近一次看到这个资源的时间。
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )


class ResourceSnapshot(Base):
    """
    Snapshot = 内容快照 / 内容版本

    解决：
    “这个资源某个时间点的内容是什么？”
    """

    __tablename__ = "resource_snapshots"

    # 同一个 Resource，
    # 相同 content_hash 不重复保存。
    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "content_hash",
            name="uq_snapshot_resource_hash",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    # Foreign Key = 外键
    # 表示这个 Snapshot 属于哪个 Resource。
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id"),
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content_text: Mapped[str] = mapped_column(
        Text,
        default="",
    )

    # Content Hash = 内容指纹
    # 内容没变，hash 就不变。
    content_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        index=True,
    )


class ActivityEvent(Base):
    """
    Activity Event = 用户行为事件

    解决：
    “用户什么时候访问了哪个资源？”
    """

    __tablename__ = "activity_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )

    # Idempotency Key = 幂等键
    # 同一次浏览器事件重试时不能重复写入。
    client_event_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )

    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id"),
        index=True,
    )

    # 正文抓取失败时，
    # 用户访问行为仍然可以存在，
    # 所以 snapshot_id 可以为空。
    snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("resource_snapshots.id"),
        nullable=True,
        index=True,
    )

    # web_visit / file_open ...
    event_type: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )

    # Event Time = 事件发生时间
    # 用户真正什么时候访问。
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )

    # Processing Time = 系统处理时间
    # RecallFlow 什么时候收到。
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    # 扩展信息。
    # 例如 tab_id / referrer / dwell_time。
    context_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )