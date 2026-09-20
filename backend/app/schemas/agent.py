from datetime import datetime

from pydantic import BaseModel, Field


class MemorySource(BaseModel):
    """
    Memory Source = 记忆来源。

    用于告诉用户：
    这条历史记忆来自哪个 WorkSession / 网页。
    """

    session_id: str
    session_title: str

    title: str | None = None
    locator: str

    observed_at: datetime


class MemorySearchHit(BaseModel):
    """
    Memory Search Hit = 一条检索命中的历史记忆。
    """

    session_id: str
    title: str

    summary: str | None = None

    keywords: list[str] = Field(
        default_factory=list
    )

    score: float

    started_at: datetime
    ended_at: datetime

    # 这个 Session 的真实来源
    sources: list[MemorySource] = Field(
        default_factory=list
    )

    # 给 Agent 阅读的证据文本
    evidence_text: str


class MemoryEvidenceGrade(BaseModel):
    """
    Evidence Grade = 证据评估结果。

    Agent 判断：
    当前检索结果是否足够回答用户。
    """

    is_sufficient: bool

    # 为什么够 / 不够
    reason: str

    # 如果证据不足，
    # LLM 可以给出更适合检索的新 Query。
    rewrite_query: str | None = None


class MemoryAnswerDraft(BaseModel):
    """
    LLM 最终生成的回答。
    """

    answer: str

    # 回答使用了哪些 WorkSession。
    used_session_ids: list[str] = Field(
        default_factory=list
    )


class MemoryAgentResponse(BaseModel):
    """
    Memory Agent 最终返回给系统的结果。
    """

    answer: str

    sources: list[MemorySource] = Field(
        default_factory=list
    )

    # 最终实际使用的检索 Query
    search_query: str

    # 一共检索了几轮
    retrieval_rounds: int

    # Abstain = 拒答 / 不强行回答
    #
    # True 表示证据不足，
    # Agent 选择不编造答案。
    abstained: bool = False