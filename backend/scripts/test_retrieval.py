import asyncio

from sqlalchemy import select

from app.db.models.work_session import WorkSession
from app.db.session import AsyncSessionFactory
from app.memory.session_memory import SessionMemoryService
from app.retrieval.document import RetrievalDocument
from app.retrieval.search.hybrid_search import HybridSearcher


async def main():
    async with AsyncSessionFactory() as db:

        # 1. 读取全部 WorkSession
        stmt = (
            select(WorkSession)
            .order_by(WorkSession.started_at)
        )

        sessions = list(
            (await db.scalars(stmt)).all()
        )

        if not sessions:
            print(
                "No WorkSessions found. "
                "Run seed/rebuild/enrich first."
            )
            return

        memory_service = SessionMemoryService(db)

        documents: list[RetrievalDocument] = []

        # 2. WorkSession
        #    -> RetrievalDocument
        for session in sessions:

            retrieval_text = (
                await memory_service
                .build_retrieval_text(
                    session.id
                )
            )

            if not retrieval_text:
                continue

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
            print(
                "No retrieval documents available."
            )
            return

        print(
            f"Loaded {len(documents)} "
            f"WorkSessions for retrieval."
        )

        # 3. 创建 Hybrid Retrieval
        searcher = HybridSearcher(
            documents
        )

        # 4. 测试两个 Query
        queries = [
            "Agent 的长期记忆怎么设计？",
            "FastAPI 异步数据库怎么做？",
        ]

        for query in queries:

            print(
                "\n"
                "================================"
            )

            print(
                "QUERY:",
                query,
            )

            print(
                "================================"
            )

            results = searcher.search(
                query,
                top_k=2,
            )

            for rank, result in enumerate(
                results,
                start=1,
            ):
                print(
                    f"{rank}. "
                    f"{result.document.title} "
                    f"| RRF Score="
                    f"{result.score:.4f}"
                )


if __name__ == "__main__":
    asyncio.run(main())