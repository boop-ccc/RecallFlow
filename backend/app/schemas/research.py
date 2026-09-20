from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """
    Web Search Result = 网页搜索结果。
    """

    title: str

    # 网页 URL
    url: str

    # 搜索引擎返回的简短摘要
    snippet: str = ""


class WebPageEvidence(BaseModel):
    """
    Web Page Evidence = 网页证据。

    Research Agent 最终使用的真实外部来源。
    """

    title: str
    url: str

    # 搜索摘要
    snippet: str = ""

    # 实际抓取到的网页正文
    content: str = ""


class ResearchEvidenceGrade(BaseModel):
    """
    Evidence Grade = 外部证据评估。

    判断当前搜索结果能不能回答用户问题。
    """

    is_sufficient: bool

    # 中文说明为什么够 / 不够
    reason: str

    # 证据不足时建议的新搜索 Query
    rewrite_query: str | None = None


class ResearchAnswerDraft(BaseModel):
    """
    Research Agent 的 LLM 输出。
    """

    answer: str

    # LLM 声称使用了哪些网页
    used_urls: list[str] = Field(
        default_factory=list
    )


class ResearchAgentResponse(BaseModel):
    """
    Research Agent 最终输出。
    """

    answer: str

    sources: list[WebPageEvidence] = Field(
        default_factory=list
    )

    search_query: str

    search_rounds: int

    # True = 外部证据不足，不强行回答
    abstained: bool = False