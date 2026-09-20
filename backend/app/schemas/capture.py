from datetime import datetime

from pydantic import BaseModel, Field


class CaptureRequest(BaseModel):
    """
    CaptureRequest = 采集请求

    浏览器以后会把一次访问事件发送到这里。
    """

    # Idempotency Key = 幂等键
    # 同一次事件重试时保持相同 ID。
    client_event_id: str

    # Resource Type = 资源类型
    # 第一版主要使用 web。
    source_type: str = "web"

    # Locator = 资源地址
    # web 场景就是 URL。
    locator: str

    title: str | None = None

    # 抓取到的网页正文。
    # 允许为空，因为正文抓取可能失败。
    content_text: str | None = None

    event_type: str = "web_visit"

    # Event Time = 事件真正发生时间
    observed_at: datetime

    # 额外信息，例如 tab_id。
    context: dict = Field(default_factory=dict)


class CaptureResponse(BaseModel):
    resource_id: str
    snapshot_id: str | None
    activity_id: str

    # true 表示这次请求是重复重试，
    # 数据库没有再创建 Activity。
    duplicate: bool
    