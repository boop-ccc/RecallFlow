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


class MemorySearchService:
    """
    Memory Search Service = 记忆检索服务。

    负责：
    WorkSession
        ↓
    RetrievalDocument
        ↓
    BM25 + Dense + RRF
        ↓
    MemorySearchHit
    """

    def __init__(self, db: AsyncSession):
        self.db = db

        self.memory_service = SessionMemoryService(db)

        # 第一轮搜索时才真正创建 Retrieval Index。
        self.searcher: HybridSearcher | None = None

        # 保存 session_id -> WorkSession
        self.sessions: dict[str, WorkSession] = {}

    async def _build_index(self) -> None:
        """
        Index = 检索索引。

        Demo 阶段：
        第一次搜索时把所有 WorkSession
        建成内存检索索引。

        同一个 Memory Agent Run 内重复搜索时，
        不需要重新加载 Embedding Model。
        """

        stmt = (
            select(WorkSession)
            .order_by(WorkSession.started_at)
        )

        work_sessions = list(
            (await self.db.scalars(stmt)).all()
        )

        documents: list[RetrievalDocument] = []

        for session in work_sessions:

            retrieval_text = (
                await self.memory_service
                .build_retrieval_text(
                    session.id
                )
            )

            if not retrieval_text:
                continue

            self.sessions[session.id] = session

            documents.append(
                RetrievalDocument(
                    session_id=session.id,
                    title=(
                        session.title
                        or "Untitled Session"
                    ),
                    text=retrieval_text,
                )
            )

        if not documents:
            return

        self.searcher = HybridSearcher(
            documents
        )

    async def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[MemorySearchHit]:
        """
        搜索和 Query 最相关的 WorkSession。
        """

        # Lazy Initialization = 延迟初始化
        #
        # 第一次需要搜索时才建立索引。
        if self.searcher is None:
            await self._build_index()

        if self.searcher is None:
            return []

        results = self.searcher.search(
            query,
            top_k=top_k,
        )

        hits: list[MemorySearchHit] = []

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

            sources: list[MemorySource] = []

            for item in context.items:

                sources.append(
                    MemorySource(
                        session_id=session.id,
                        session_title=(
                            session.title
                            or "Untitled Session"
                        ),
                        title=item.title,
                        locator=item.locator,
                        observed_at=item.observed_at,
                    )
                )

            evidence_text = (
                self.memory_service.to_prompt_text(
                    context
                )
            )

            hits.append(
                MemorySearchHit(
                    session_id=session.id,
                    title=(
                        session.title
                        or "Untitled Session"
                    ),
                    summary=session.summary,
                    keywords=(
                        session.keywords or []
                    ),
                    score=result.score,
                    started_at=session.started_at,
                    ended_at=session.ended_at,
                    sources=sources,
                    evidence_text=evidence_text,
                )
            )

        return hits