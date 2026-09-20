import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.work_session import WorkSession
from app.memory.session_memory import SessionMemoryService
from app.retrieval.document import RetrievalDocument
from app.retrieval.search.hybrid_search import HybridSearcher
from app.schemas.agent import (
    MemorySearchHit,
    MemorySource,
)
from app.services.session_enrichment_service import (
    SessionEnrichmentService,
)


logger = logging.getLogger(__name__)


# “刚才”第一版定义：
# 以最新 Activity 为终点，
# 向前取最近 30 分钟。
RECENT_WINDOW = timedelta(minutes=30)

# 防止最近半小时页面太多，
# 最多给 Agent 8 条 Activity。
RECENT_MAX_ITEMS = 8


def is_recent_memory_query(
    query: str,
) -> bool:
    """
    判断用户是不是在问“刚才发生了什么”。

    Query Resolution 可能会把上一轮用户问题拼到当前 Query 前面。
    因此只要最终 Query 中明确出现“刚才 / 刚刚 / 刚做”等近期意图，
    就优先进入 Recent Activity Fast Path。

    “昨天 / 上周 / 最近几天”等较大时间范围，
    如果没有近期意图，则继续走普通 Hybrid Retrieval。
    """

    text = query.strip()

    recent_terms = (
        "刚才",
        "刚刚",
        "刚做",
        "刚看",
        "刚研究",
        "刚访问",
        "最近在做",
        "最近做了",
        "最近看了",
        "最近研究了",
    )

    if any(
        term in text
        for term in recent_terms
    ):
        return True

    broad_time_terms = (
        "昨天",
        "前天",
        "上周",
        "上个月",
        "最近一周",
        "最近几天",
        "近一周",
        "近几天",
        "这个月",
        "本月",
    )

    if any(
        term in text
        for term in broad_time_terms
    ):
        return False

    return False


class MemorySearchService:
    """
    Memory Search Service = 记忆检索服务。

    两种检索模式：

    1. Recent Activity Retrieval
       “我刚才做了什么？”
       → 按时间找最新 Activity。

    2. Hybrid Retrieval
       “我之前研究过 LangGraph Memory 吗？”
       → BM25 + Dense + RRF。
    """

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

        self.memory_service = (
            SessionMemoryService(db)
        )

        self.enrichment_service = (
            SessionEnrichmentService(db)
        )

        # 普通历史搜索第一次执行时，
        # 才建立 Hybrid Index。
        self.searcher: HybridSearcher | None = None

        self.sessions: dict[
            str,
            WorkSession,
        ] = {}

    async def _ensure_enriched(
        self,
        session: WorkSession,
    ) -> None:
        """
        Lazy Enrichment = 按需语义增强。

        Session 已经有 title / summary，
        就不重复调用 LLM。
        """

        if (
            session.title
            and session.summary
        ):
            return

        try:
            await self.enrichment_service.enrich(
                session.id
            )

        except Exception:
            # Enrichment 失败不应该导致
            # 整个 Memory Retrieval 失败。
            logger.warning(
                "WorkSession enrichment failed: %s",
                session.id,
                exc_info=True,
            )

    async def _search_recent(
        self,
    ) -> list[MemorySearchHit]:
        """
        Recent Activity Retrieval
        = 最近行为检索。

        不调用 BM25。
        不调用 Dense。
        不调用 LLM Enrichment。

        直接：

        最新 WorkSession
            ↓
        最新 Activity
            ↓
        向前 30 分钟
            ↓
        Recent Evidence
        """

        stmt = (
            select(WorkSession)
            .order_by(
                WorkSession.ended_at.desc()
            )
            .limit(1)
        )

        session = await self.db.scalar(stmt)

        if session is None:
            return []

        context = (
            await self.memory_service
            .build_context(
                session.id
            )
        )

        if (
            context is None
            or not context.items
        ):
            return []

        # WorkSessionItem 已经按照真实时间排序。
        latest_item = context.items[-1]

        latest_time = (
            latest_item.observed_at
        )

        cutoff = (
            latest_time
            - RECENT_WINDOW
        )

        recent_items = [
            item
            for item in context.items
            if item.observed_at >= cutoff
        ]

        # 只保留最近若干条，
        # 防止频繁网页跳转产生过多上下文。
        recent_items = recent_items[
            -RECENT_MAX_ITEMS:
        ]

        if not recent_items:
            return []

        # 创建一个只包含“最近 Activity”
        # 的临时 Evidence Context。
        #
        # 不修改数据库里的完整 WorkSession。
        recent_context = (
            context.model_copy(
                update={
                    "started_at":
                        recent_items[0]
                        .observed_at,
                    "ended_at":
                        recent_items[-1]
                        .observed_at,
                    "items":
                        recent_items,
                }
            )
        )

        sources: list[
            MemorySource
        ] = []

        for item in recent_items:

            sources.append(
                MemorySource(
                    session_id=session.id,
                    session_title=(
                        session.title
                        or "最近工作记录"
                    ),
                    title=item.title,
                    locator=item.locator,
                    observed_at=(
                        item.observed_at
                    ),
                )
            )

        evidence_text = (
            self.memory_service
            .to_prompt_text(
                recent_context
            )
        )

        return [
            MemorySearchHit(
                session_id=session.id,
                title=(
                    session.title
                    or "最近工作记录"
                ),

                # Recent 查询不依赖旧 Summary。
                #
                # 因为旧 Summary 可能是在
                # 新 Activity 加入之前生成的。
                summary=None,

                keywords=[],

                # Recent 查询不存在传统
                # Hybrid score，
                # 用固定值即可。
                score=1.0,

                started_at=(
                    recent_items[0]
                    .observed_at
                ),

                ended_at=(
                    recent_items[-1]
                    .observed_at
                ),

                sources=sources,

                evidence_text=(
                    evidence_text
                ),
            )
        ]

    async def _build_index(
        self,
    ) -> None:
        """
        给普通历史问题建立
        Hybrid Retrieval Index。
        """

        stmt = (
            select(WorkSession)
            .order_by(
                WorkSession.started_at
            )
        )

        work_sessions = list(
            (
                await self.db.scalars(stmt)
            ).all()
        )

        documents: list[
            RetrievalDocument
        ] = []

        for session in work_sessions:

            await self._ensure_enriched(
                session
            )

            retrieval_text = (
                await self.memory_service
                .build_retrieval_text(
                    session.id
                )
            )

            if not retrieval_text:
                continue

            self.sessions[
                session.id
            ] = session

            documents.append(
                RetrievalDocument(
                    session_id=(
                        session.id
                    ),
                    title=(
                        session.title
                        or "Untitled Session"
                    ),
                    text=(
                        retrieval_text
                    ),
                )
            )

        if not documents:
            return

        self.searcher = (
            HybridSearcher(
                documents
            )
        )

    async def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[MemorySearchHit]:
        """
        Memory Search 统一入口。
        """

        # ---------------------------------
        # A. “刚才”类问题
        # ---------------------------------
        if is_recent_memory_query(
            query
        ):
            return (
                await self._search_recent()
            )

        # ---------------------------------
        # B. 普通历史问题
        # ---------------------------------
        if self.searcher is None:
            await self._build_index()

        if self.searcher is None:
            return []

        results = self.searcher.search(
            query,
            top_k=top_k,
        )

        hits: list[
            MemorySearchHit
        ] = []

        for result in results:

            session_id = (
                result.document.session_id
            )

            session = self.sessions[
                session_id
            ]

            context = (
                await self.memory_service
                .build_context(
                    session_id
                )
            )

            if context is None:
                continue

            sources: list[
                MemorySource
            ] = []

            for item in context.items:

                sources.append(
                    MemorySource(
                        session_id=(
                            session.id
                        ),
                        session_title=(
                            session.title
                            or "Untitled Session"
                        ),
                        title=item.title,
                        locator=item.locator,
                        observed_at=(
                            item.observed_at
                        ),
                    )
                )

            evidence_text = (
                self.memory_service
                .to_prompt_text(
                    context
                )
            )

            hits.append(
                MemorySearchHit(
                    session_id=(
                        session.id
                    ),
                    title=(
                        session.title
                        or "Untitled Session"
                    ),
                    summary=(
                        session.summary
                    ),
                    keywords=(
                        session.keywords
                        or []
                    ),
                    score=(
                        result.score
                    ),
                    started_at=(
                        session.started_at
                    ),
                    ended_at=(
                        session.ended_at
                    ),
                    sources=sources,
                    evidence_text=(
                        evidence_text
                    ),
                )
            )

        return hits