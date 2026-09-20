from datetime import datetime

from pydantic import BaseModel


class EvidenceItem(BaseModel):
    """
    Evidence = 证据

    一条 WorkSession 中，
    Agent 可以使用的一条真实来源。
    """

    activity_id: str

    # 用户什么时候看到这个内容
    observed_at: datetime

    resource_id: str

    # 来源地址，例如 URL
    locator: str

    title: str | None = None

    # 当时抓取到的正文
    content_text: str | None = None


class SessionEvidence(BaseModel):
    """
    一个 WorkSession 的完整证据上下文。
    """

    session_id: str

    started_at: datetime
    ended_at: datetime

    items: list[EvidenceItem]
    
from pydantic import Field


class WorkSessionEnrichment(BaseModel):
    """
    LLM 对 WorkSession 的语义理解结果。

    Structured Output = 结构化输出：
    不允许模型随便返回一大段文字，
    而是固定返回下面几个字段。
    """

    # 这次工作在做什么
    title: str

    # 这次工作的简短总结
    summary: str

    # 关键词
    keywords: list[str] = Field(
        default_factory=list,
        max_length=8,
    )

    # 明确能从证据中看出的未完成任务
    # 没有证据就返回 []
    open_tasks: list[str] = Field(
        default_factory=list,
        max_length=5,
    )