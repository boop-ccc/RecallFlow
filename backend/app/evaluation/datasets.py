from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingCase:
    query: str
    expected_route: str


ROUTING_CASES = [
    RoutingCase(
        "我之前研究 Agent Memory 看了什么？",
        "memory_only",
    ),
    RoutingCase(
        "我昨天看的 LangGraph 文档在哪里？",
        "memory_only",
    ),
    RoutingCase(
        "我上次研究 SQLAlchemy 做到哪里了？",
        "memory_only",
    ),
    RoutingCase(
        "继续之前的 Agent Memory 工作。",
        "memory_only",
    ),
    RoutingCase(
        "我过去看过哪些 FastAPI 资料？",
        "memory_only",
    ),

    RoutingCase(
        "现在 Agent Memory 有哪些新方案？",
        "research_only",
    ),
    RoutingCase(
        "帮我搜索一下最新 LangGraph Memory 资料。",
        "research_only",
    ),
    RoutingCase(
        "当前公开资料里有哪些 Agent Memory 方案？",
        "research_only",
    ),
    RoutingCase(
        "网上查一下目前常见的 Memory 架构。",
        "research_only",
    ),
    RoutingCase(
        "最近有没有新的 Agent 长期记忆方法？",
        "research_only",
    ),

    RoutingCase(
        "继续我之前的 Agent Memory 研究，再看看现在有什么新方案。",
        "memory_and_research",
    ),
    RoutingCase(
        "我昨天研究的 LangGraph Memory，帮我查一下最新进展。",
        "memory_and_research",
    ),
    RoutingCase(
        "结合我之前看的资料和当前公开资料继续研究。",
        "memory_and_research",
    ),
    RoutingCase(
        "接着上次的工作，同时搜索一下现在有没有新的方案。",
        "memory_and_research",
    ),
    RoutingCase(
        "我以前研究过 episodic memory，再看看目前有什么新方法。",
        "memory_and_research",
    ),
]


@dataclass(frozen=True)
class RetrievalCase:
    query: str

    # 不使用动态 session_id，
    # 而是根据 Session title 匹配相关文档。
    #
    # 这样 Demo DB 重建后 ID 变化，
    # Evaluation 仍然可以复现。
    expected_title_keywords: tuple[
        str,
        ...
    ]


RETRIEVAL_CASES = [
    RetrievalCase(
        "Agent 的长期记忆怎么设计？",
        ("agent", "memory"),
    ),
    RetrievalCase(
        "LangGraph memory 怎么做？",
        ("agent", "memory"),
    ),
    RetrievalCase(
        "episodic memory 是我之前哪次研究？",
        ("agent", "memory"),
    ),
    RetrievalCase(
        "有状态 Agent 的记忆机制",
        ("agent", "memory"),
    ),

    RetrievalCase(
        "FastAPI 异步数据库怎么做？",
        ("fastapi", "sqlalchemy"),
    ),
    RetrievalCase(
        "SQLAlchemy AsyncSession 怎么使用？",
        ("fastapi", "sqlalchemy"),
    ),
    RetrievalCase(
        "异步数据库 session 的研究记录",
        ("fastapi", "sqlalchemy"),
    ),
    RetrievalCase(
        "FastAPI dependencies 和数据库",
        ("fastapi", "sqlalchemy"),
    ),
]
