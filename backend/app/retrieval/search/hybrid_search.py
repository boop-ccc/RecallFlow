from dataclasses import dataclass

from app.retrieval.document import (
    RetrievalDocument,
)
from app.retrieval.search.bm25_search import (
    BM25Searcher,
)
from app.retrieval.search.dense_search import (
    DenseSearcher,
)


@dataclass
class SearchResult:
    """
    Hybrid Retrieval 最终结果。
    """

    document: RetrievalDocument
    score: float


class HybridSearcher:
    """
    Weighted RRF Hybrid Retrieval
    = 加权倒数排名融合。

    为什么不是 1:1 RRF？

    Controlled Offline Benchmark 中，
    RecallFlow 的查询大量是中文自然语言，
    WorkSession Evidence 又常混有英文技术材料。

    Dense Retrieval 对跨语言 / 语义表达更稳定；
    BM25 仍然保留，用于：
    - LangGraph
    - async_sessionmaker
    - client_event_id
    - ToolRegistry
    等精确术语。

    所以生产默认使用：
        Dense weight = 2.0
        BM25 weight  = 1.0

    这仍然是 RRF：
    比较的是 Rank，而不是把原始 BM25 Score
    和 Cosine Similarity 直接相加。
    """

    def __init__(
        self,
        documents: list[
            RetrievalDocument
        ],
        *,
        bm25_weight: float = 1.0,
        dense_weight: float = 2.0,
        rrf_k: int = 60,
    ):
        if not documents:
            raise ValueError(
                "HybridSearcher requires "
                "at least one document"
            )

        if bm25_weight <= 0:
            raise ValueError(
                "bm25_weight must be > 0"
            )

        if dense_weight <= 0:
            raise ValueError(
                "dense_weight must be > 0"
            )

        if rrf_k < 1:
            raise ValueError(
                "rrf_k must be >= 1"
            )

        self.documents = documents

        self.bm25 = BM25Searcher(
            documents
        )

        self.dense = DenseSearcher(
            documents
        )

        self.bm25_weight = (
            bm25_weight
        )

        self.dense_weight = (
            dense_weight
        )

        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[SearchResult]:
        candidate_k = min(
            10,
            len(self.documents),
        )

        bm25_results = (
            self.bm25.search(
                query,
                top_k=candidate_k,
            )
        )

        dense_results = (
            self.dense.search(
                query,
                top_k=candidate_k,
            )
        )

        scores: dict[
            str,
            float,
        ] = {}

        documents: dict[
            str,
            RetrievalDocument,
        ] = {}

        for rank, (
            document,
            _,
        ) in enumerate(
            bm25_results,
            start=1,
        ):
            session_id = (
                document.session_id
            )

            documents[
                session_id
            ] = document

            scores[
                session_id
            ] = (
                scores.get(
                    session_id,
                    0.0,
                )
                + self.bm25_weight
                / (
                    self.rrf_k
                    + rank
                )
            )

        for rank, (
            document,
            _,
        ) in enumerate(
            dense_results,
            start=1,
        ):
            session_id = (
                document.session_id
            )

            documents[
                session_id
            ] = document

            scores[
                session_id
            ] = (
                scores.get(
                    session_id,
                    0.0,
                )
                + self.dense_weight
                / (
                    self.rrf_k
                    + rank
                )
            )

        ranked = sorted(
            scores.items(),
            key=lambda item:
                item[1],
            reverse=True,
        )

        return [
            SearchResult(
                document=documents[
                    session_id
                ],
                score=score,
            )
            for (
                session_id,
                score,
            ) in ranked[:top_k]
        ]
