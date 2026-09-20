from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> datetime:
    """
    UTC = Coordinated Universal Time
    世界统一时间。

    数据库统一使用 UTC，
    避免不同时区混乱。
    """
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """
    UUID = Universally Unique Identifier
    全局唯一标识符。

    给 Resource / Snapshot / Activity
    生成唯一 ID。
    """
    return str(uuid4())