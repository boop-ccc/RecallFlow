from dataclasses import dataclass


@dataclass(frozen=True)
class OfflineDocument:
    doc_id: str
    title: str
    text: str


@dataclass(frozen=True)
class OfflineRetrievalCase:
    query: str
    relevant_doc_ids: tuple[str, ...]


@dataclass(frozen=True)
class OfflineRoutingCase:
    query: str
    expected_route: str


@dataclass(frozen=True)
class OfflineResolutionCase:
    previous_user: str | None
    previous_assistant: str | None
    message: str
    expected_used_history: bool
    expected_contains: tuple[str, ...]


OFFLINE_DOCUMENTS = [
    OfflineDocument(
        "agent_memory",
        "Agent Memory Architecture",
        (
            "Agent long-term memory, episodic memory, "
            "stateful agents, memory retrieval, "
            "cross-thread memory, work-session memory."
        ),
    ),
    OfflineDocument(
        "fastapi_async",
        "FastAPI Async Database",
        (
            "FastAPI dependency injection with SQLAlchemy "
            "AsyncSession, async_sessionmaker, request scoped "
            "database sessions and asynchronous API design."
        ),
    ),
    OfflineDocument(
        "langgraph_checkpoint",
        "LangGraph Checkpoint Recovery",
        (
            "LangGraph checkpoint, thread state, graph state, "
            "resume interrupted execution, checkpointer and "
            "conversation state recovery."
        ),
    ),
    OfflineDocument(
        "postgres_sqlalchemy",
        "PostgreSQL with SQLAlchemy",
        (
            "PostgreSQL, asyncpg, SQLAlchemy ORM, transaction "
            "boundary, rollback, commit and database migration."
        ),
    ),
    OfflineDocument(
        "hybrid_retrieval",
        "Hybrid Retrieval BM25 Dense RRF",
        (
            "Hybrid retrieval combines BM25 keyword retrieval "
            "and dense semantic embeddings. Reciprocal Rank "
            "Fusion RRF merges rankings without comparing raw "
            "score scales."
        ),
    ),
    OfflineDocument(
        "agent_evaluation",
        "LLM Agent Evaluation",
        (
            "Agent evaluation with routing accuracy, Recall@K, "
            "MRR, nDCG, evidence validity, abstention accuracy, "
            "latency, token usage and tool-call metrics."
        ),
    ),
    OfflineDocument(
        "tool_permission",
        "Agent Tool Permission",
        (
            "Capability-based tool permission, ToolRegistry, "
            "hard authorization boundary, private memory tools "
            "and public web tools isolated by agent."
        ),
    ),
    OfflineDocument(
        "runtime_retry",
        "Agent Runtime Reliability",
        (
            "Agent runtime harness with step budget, tool budget, "
            "LLM call budget, timeout, retry, exponential backoff, "
            "rate-limit handling and graceful degradation."
        ),
    ),
    OfflineDocument(
        "chrome_capture",
        "Chrome Activity Capture",
        (
            "Chrome extension captures current URL, title, page "
            "text, timestamp and client_event_id, then posts the "
            "activity to a FastAPI capture endpoint."
        ),
    ),
    OfflineDocument(
        "multi_agent",
        "Supervisor Multi-Agent Routing",
        (
            "Supervisor routes between Memory Agent and Research "
            "Agent. Independent sub-agents run concurrently with "
            "asyncio gather and results pass through a Verifier."
        ),
    ),
]


OFFLINE_RETRIEVAL_CASES = [
    # Agent Memory
    OfflineRetrievalCase(
        "Agent 怎么长期记住用户过去做过的工作？",
        ("agent_memory",),
    ),
    OfflineRetrievalCase(
        "episodic memory 和跨会话记忆",
        ("agent_memory",),
    ),
    OfflineRetrievalCase(
        "stateful agent 的历史工作恢复",
        ("agent_memory",),
    ),

    # FastAPI async
    OfflineRetrievalCase(
        "FastAPI 里面 AsyncSession 应该怎么管理？",
        ("fastapi_async",),
    ),
    OfflineRetrievalCase(
        "async_sessionmaker 和 request scoped session",
        ("fastapi_async",),
    ),
    OfflineRetrievalCase(
        "异步 API 的数据库依赖注入",
        ("fastapi_async",),
    ),

    # Checkpoint
    OfflineRetrievalCase(
        "LangGraph 如何恢复中断的图执行？",
        ("langgraph_checkpoint",),
    ),
    OfflineRetrievalCase(
        "checkpointer 和 thread state",
        ("langgraph_checkpoint",),
    ),
    OfflineRetrievalCase(
        "对话执行中断后从状态恢复",
        ("langgraph_checkpoint",),
    ),

    # Postgres / transaction
    OfflineRetrievalCase(
        "SQLAlchemy transaction rollback 怎么处理？",
        ("postgres_sqlalchemy",),
    ),
    OfflineRetrievalCase(
        "PostgreSQL asyncpg 配置",
        ("postgres_sqlalchemy",),
    ),
    OfflineRetrievalCase(
        "数据库 commit rollback transaction boundary",
        ("postgres_sqlalchemy",),
    ),

    # Hybrid Retrieval
    OfflineRetrievalCase(
        "BM25 和向量检索怎么融合？",
        ("hybrid_retrieval",),
    ),
    OfflineRetrievalCase(
        "RRF 为什么不用原始 score 相加？",
        ("hybrid_retrieval",),
    ),
    OfflineRetrievalCase(
        "关键词召回加语义召回",
        ("hybrid_retrieval",),
    ),

    # Evaluation
    OfflineRetrievalCase(
        "Agent 怎么评估 Recall MRR nDCG？",
        ("agent_evaluation",),
    ),
    OfflineRetrievalCase(
        "路由准确率和证据有效性怎么测？",
        ("agent_evaluation",),
    ),
    OfflineRetrievalCase(
        "如何统计 Agent latency token tool call？",
        ("agent_evaluation",),
    ),

    # Permission
    OfflineRetrievalCase(
        "为什么不同 Agent 不能共用所有 Tool？",
        ("tool_permission",),
    ),
    OfflineRetrievalCase(
        "ToolRegistry 怎么做硬权限控制？",
        ("tool_permission",),
    ),
    OfflineRetrievalCase(
        "private memory tool 和 web tool 隔离",
        ("tool_permission",),
    ),

    # Runtime
    OfflineRetrievalCase(
        "Groq 429 以后 Agent 怎么优雅降级？",
        ("runtime_retry",),
    ),
    OfflineRetrievalCase(
        "step budget tool budget timeout retry",
        ("runtime_retry",),
    ),
    OfflineRetrievalCase(
        "指数退避和 rate limit handling",
        ("runtime_retry",),
    ),

    # Chrome
    OfflineRetrievalCase(
        "浏览器插件怎么采集当前网页？",
        ("chrome_capture",),
    ),
    OfflineRetrievalCase(
        "client_event_id URL title page text capture",
        ("chrome_capture",),
    ),
    OfflineRetrievalCase(
        "Chrome extension 把访问行为发给 FastAPI",
        ("chrome_capture",),
    ),

    # Multi-Agent
    OfflineRetrievalCase(
        "Supervisor 怎么同时调用 Memory 和 Research？",
        ("multi_agent",),
    ),
    OfflineRetrievalCase(
        "asyncio gather 并发执行 sub-agent",
        ("multi_agent",),
    ),
    OfflineRetrievalCase(
        "Memory Agent Research Agent Verifier 的关系",
        ("multi_agent",),
    ),
]


OFFLINE_ROUTING_CASES = [
    OfflineRoutingCase(
        "我之前研究 Agent Memory 看了什么？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "昨天看的 LangGraph 文档在哪？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "上次 SQLAlchemy 做到哪里了？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "继续之前的工作。",
        "memory_only",
    ),
    OfflineRoutingCase(
        "我过去看过哪些 FastAPI 资料？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "我研究过 episodic memory 吗？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "接着上次做到的地方。",
        "memory_only",
    ),
    OfflineRoutingCase(
        "历史记录里有没有 async_sessionmaker？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "我以前在哪看过 RRF？",
        "memory_only",
    ),
    OfflineRoutingCase(
        "昨天的 Agent Runtime 研究内容是什么？",
        "memory_only",
    ),

    OfflineRoutingCase(
        "现在 Agent Memory 有哪些新方案？",
        "research_only",
    ),
    OfflineRoutingCase(
        "帮我搜索一下最新 LangGraph Memory 资料。",
        "research_only",
    ),
    OfflineRoutingCase(
        "当前公开资料里有什么 Agent Memory 方案？",
        "research_only",
    ),
    OfflineRoutingCase(
        "网上查一下目前常见的 Memory 架构。",
        "research_only",
    ),
    OfflineRoutingCase(
        "最近有没有新的 Agent 长期记忆方法？",
        "research_only",
    ),
    OfflineRoutingCase(
        "搜索一下最新 FastAPI 版本变化。",
        "research_only",
    ),
    OfflineRoutingCase(
        "现在公开网络上对 RRF 有什么新讨论？",
        "research_only",
    ),
    OfflineRoutingCase(
        "当前有哪些新的 Agent Evaluation 框架？",
        "research_only",
    ),
    OfflineRoutingCase(
        "互联网查一下最近的 LangGraph 更新。",
        "research_only",
    ),
    OfflineRoutingCase(
        "目前有哪些公开的 Multi-Agent 方案？",
        "research_only",
    ),

    OfflineRoutingCase(
        "继续我之前的 Agent Memory 研究，再看看现在有什么新方案。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "昨天研究的 LangGraph Memory，帮我查一下最新进展。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "结合我之前看的资料和当前公开资料继续研究。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "接着上次的工作，同时搜索一下现在有没有新的方案。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "我以前研究过 episodic memory，再看看目前有什么新方法。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "把我昨天的 RRF 研究和最新公开方案一起整理。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "从历史里恢复 Agent Evaluation，再查一下现在的新框架。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "继续之前的 LangGraph Checkpoint 工作，并搜索最新文档。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "我上次看的 Tool Permission 资料和当前方案对比一下。",
        "memory_and_research",
    ),
    OfflineRoutingCase(
        "找到我过去的 Multi-Agent 研究，再看看最近有什么变化。",
        "memory_and_research",
    ),
]


OFFLINE_RESOLUTION_CASES = [
    OfflineResolutionCase(
        None,
        None,
        "现在 Agent Memory 有什么新方案？",
        False,
        ("现在", "Agent Memory"),
    ),
    OfflineResolutionCase(
        "我之前研究 Agent Memory 看了什么？",
        "找到了相关记录。",
        "继续这个方向",
        True,
        ("Agent Memory", "继续这个方向"),
    ),
    OfflineResolutionCase(
        "我昨天在研究 SQLAlchemy。",
        "你看了异步 Session。",
        "接着讲",
        True,
        ("SQLAlchemy", "接着讲"),
    ),
    OfflineResolutionCase(
        "我在看 LangGraph Checkpoint。",
        "主要是状态恢复。",
        "这个怎么用？",
        True,
        ("LangGraph", "这个怎么用"),
    ),
    OfflineResolutionCase(
        "我之前在比较 BM25 和 Dense。",
        "两者召回方式不同。",
        "再详细说",
        True,
        ("BM25", "再详细说"),
    ),
    OfflineResolutionCase(
        "我在研究 Verifier。",
        "它负责证据验证。",
        "为什么？",
        True,
        ("Verifier", "为什么"),
    ),
    OfflineResolutionCase(
        "我在做 Chrome Capture。",
        "已经能采集 URL。",
        "然后呢？",
        True,
        ("Chrome Capture", "然后呢"),
    ),
    OfflineResolutionCase(
        "我之前处理过 Groq 429。",
        "使用了 Retry。",
        "这个方案还有什么问题？",
        True,
        ("Groq 429", "这个方案"),
    ),
    OfflineResolutionCase(
        "我昨天研究 Multi-Agent。",
        "用了 Supervisor。",
        "继续，再看看现在有什么新方案",
        True,
        ("Multi-Agent", "现在"),
    ),
    OfflineResolutionCase(
        "我在研究 FastAPI。",
        "刚才讲了 API。",
        "最新 LangGraph Memory 有哪些方案？",
        False,
        ("最新", "LangGraph Memory"),
    ),
    OfflineResolutionCase(
        "我昨天看了 PostgreSQL。",
        "讲了 asyncpg。",
        "当前公开资料有哪些变化？",
        False,
        ("当前", "公开资料"),
    ),
    OfflineResolutionCase(
        "我在研究 Agent Eval。",
        "讲到了 MRR。",
        "MRR 的公式是什么？",
        False,
        ("MRR",),
    ),
    OfflineResolutionCase(
        "我在研究 Permission。",
        "讲了 ToolRegistry。",
        "ToolRegistry 为什么比 Prompt 权限可靠？",
        False,
        ("ToolRegistry", "Prompt"),
    ),
    OfflineResolutionCase(
        "我昨天看了 Checkpointer。",
        "已经理解 thread state。",
        "展开这个部分",
        True,
        ("Checkpointer", "展开"),
    ),
    OfflineResolutionCase(
        "我之前在做 Runtime Harness。",
        "讲到了 Budget。",
        "前面那个预算怎么统计？",
        True,
        ("Runtime Harness", "预算"),
    ),
]
