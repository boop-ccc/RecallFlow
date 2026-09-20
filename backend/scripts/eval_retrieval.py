import asyncio
from statistics import mean

from sqlalchemy import select

from app.db.models.work_session import (
    WorkSession,
)
from app.db.session import (
    AsyncSessionFactory,
)
from app.evaluation.datasets import (
    RETRIEVAL_CASES,
)
from app.evaluation.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
)
from app.memory.session_memory import (
    SessionMemoryService,
)
from app.retrieval.document import (
    RetrievalDocument,
)
from app.retrieval.search.bm25_search import (
    BM25Searcher,
)
from app.retrieval.search.dense_search import (
    DenseSearcher,
)
from app.retrieval.search.hybrid_search import (
    HybridSearcher,
)


def _is_relevant(
    *,
    title: str,
    keywords: tuple[
        str,
        ...
    ],
) -> bool:
    normalized = title.lower()

    # Demo 数据只有两个主题。
    # 允许 expected keywords 命中其一，
    # 同时通过组合词避免过于脆弱。
    return any(
        keyword.lower()
        in normalized
        for keyword in keywords
    )


def _ranked_ids_from_pairs(
    results,
) -> list[str]:
    return [
        doc.session_id
        for doc, _
        in results
    ]


def _ranked_ids_from_hybrid(
    results,
) -> list[str]:
    return [
        item.document.session_id
        for item in results
    ]


async def main() -> None:
    async with (
        AsyncSessionFactory()
        as db
    ):
        sessions = list(
            (
                await db.scalars(
                    select(
                        WorkSession
                    )
                    .order_by(
                        WorkSession
                        .started_at
                    )
                )
            ).all()
        )

        if not sessions:
            print(
                "No WorkSessions found."
            )
            return

        memory = (
            SessionMemoryService(db)
        )

        documents: list[
            RetrievalDocument
        ] = []

        for session in sessions:
            text = await (
                memory
                .build_retrieval_text(
                    session.id
                )
            )

            if not text:
                continue

            documents.append(
                RetrievalDocument(
                    session_id=(
                        session.id
                    ),
                    title=(
                        session.title
                        or "Untitled Session"
                    ),
                    text=text,
                )
            )

        if not documents:
            print(
                "No retrieval documents "
                "available."
            )
            return

        print(
            f"Loaded {len(documents)} "
            "WorkSessions."
        )

        bm25 = BM25Searcher(
            documents
        )

        dense = DenseSearcher(
            documents
        )

        hybrid = HybridSearcher(
            documents
        )

        systems = {
            "BM25":
                lambda q: (
                    _ranked_ids_from_pairs(
                        bm25.search(
                            q,
                            top_k=3,
                        )
                    )
                ),
            "Dense":
                lambda q: (
                    _ranked_ids_from_pairs(
                        dense.search(
                            q,
                            top_k=3,
                        )
                    )
                ),
            "Hybrid":
                lambda q: (
                    _ranked_ids_from_hybrid(
                        hybrid.search(
                            q,
                            top_k=3,
                        )
                    )
                ),
        }

        document_by_id = {
            doc.session_id: doc
            for doc in documents
        }

        for system_name, search in (
            systems.items()
        ):
            recall1 = []
            recall3 = []
            ndcg3 = []
            rr_cases = []

            print(
                "\n"
                "================================"
            )
            print(
                f"{system_name} EVALUATION"
            )
            print(
                "================================"
            )

            for index, case in enumerate(
                RETRIEVAL_CASES,
                start=1,
            ):
                relevant_ids = {
                    doc.session_id
                    for doc in documents
                    if _is_relevant(
                        title=doc.title,
                        keywords=(
                            case
                            .expected_title_keywords
                        ),
                    )
                }

                if not relevant_ids:
                    print(
                        f"{index:02d}. SKIP "
                        "| no matching "
                        "expected session title"
                    )
                    print(
                        "    Query:",
                        case.query,
                    )
                    continue

                ranked_ids = search(
                    case.query
                )

                r1 = recall_at_k(
                    ranked_ids,
                    relevant_ids,
                    1,
                )

                r3 = recall_at_k(
                    ranked_ids,
                    relevant_ids,
                    3,
                )

                n3 = ndcg_at_k(
                    ranked_ids,
                    relevant_ids,
                    3,
                )

                recall1.append(r1)
                recall3.append(r3)
                ndcg3.append(n3)

                rr_cases.append(
                    (
                        ranked_ids,
                        relevant_ids,
                    )
                )

                top_title = (
                    document_by_id[
                        ranked_ids[0]
                    ].title
                    if ranked_ids
                    else "NONE"
                )

                print(
                    f"{index:02d}. "
                    f"R@1={r1:.0f} "
                    f"| Top1={top_title}"
                )

            if not rr_cases:
                print(
                    "No evaluable cases."
                )
                continue

            print(
                "\n--------------------------------"
            )

            print(
                "Recall@1:",
                f"{mean(recall1):.4f}",
            )

            print(
                "Recall@3:",
                f"{mean(recall3):.4f}",
            )

            print(
                "MRR:",
                f"{mean_reciprocal_rank(rr_cases):.4f}",
            )

            print(
                "nDCG@3:",
                f"{mean(ndcg3):.4f}",
            )

            print(
                "--------------------------------"
            )

        print(
            "\n注意："
            "当前 Demo WorkSession 数量较少，"
            "这轮结果属于 Retrieval Smoke Evaluation。"
            "等真实 Chrome 数据进入后，"
            "再扩成 30–50 个 query 的正式评测集。"
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
