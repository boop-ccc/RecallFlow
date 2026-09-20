import asyncio
import time

from sqlalchemy import select

from app.db.models.work_session import (
    WorkSession,
)
from app.db.session import (
    AsyncSessionFactory,
)
from app.memory.session_memory import (
    SessionMemoryService,
)
from app.retrieval.document import (
    RetrievalDocument,
)
from app.retrieval.search.hybrid_search import (
    HybridSearcher,
)


async def build_documents(
    db,
) -> list[RetrievalDocument]:
    sessions = list(
        (
            await db.scalars(
                select(
                    WorkSession
                ).order_by(
                    WorkSession.started_at
                )
            )
        ).all()
    )

    memory = (
        SessionMemoryService(db)
    )

    documents = []

    for session in sessions:
        text = await (
            memory.build_retrieval_text(
                session.id
            )
        )

        if not text:
            continue

        documents.append(
            RetrievalDocument(
                session_id=session.id,
                title=(
                    session.title
                    or "Untitled Session"
                ),
                text=text,
            )
        )

    return documents


async def main() -> None:
    async with (
        AsyncSessionFactory()
        as db
    ):
        documents = await (
            build_documents(db)
        )

    if not documents:
        print(
            "No WorkSessions found."
        )
        return

    query = (
        "Agent 的长期记忆怎么设计？"
    )

    started = time.perf_counter()

    first = HybridSearcher(
        documents
    )

    first.search(
        query,
        top_k=2,
    )

    cold_ms = (
        time.perf_counter()
        - started
    ) * 1000

    started = time.perf_counter()

    second = HybridSearcher(
        documents
    )

    second.search(
        query,
        top_k=2,
    )

    warm_ms = (
        time.perf_counter()
        - started
    ) * 1000

    print(
        "\n=============================="
    )
    print("RETRIEVAL CACHE BENCHMARK")
    print("==============================")

    print(
        "Cold Run:",
        f"{cold_ms:.1f} ms",
    )

    print(
        "Warm Run:",
        f"{warm_ms:.1f} ms",
    )

    if cold_ms > 0:
        print(
            "Warm / Cold Ratio:",
            f"{warm_ms / cold_ms:.3f}",
        )

    print(
        "\n说明："
        "Cold Run 包含首次模型加载；"
        "Warm Run 复用 Embedding Model "
        "和 Corpus Embedding。"
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
