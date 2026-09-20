import pytest

from app.retrieval.document import (
    RetrievalDocument,
)
from app.retrieval.search.hybrid_search import (
    HybridSearcher,
)


def _documents():
    return [
        RetrievalDocument(
            session_id="a",
            title="A",
            text=(
                "Agent memory "
                "episodic memory"
            ),
        ),
        RetrievalDocument(
            session_id="b",
            title="B",
            text=(
                "FastAPI SQLAlchemy "
                "AsyncSession"
            ),
        ),
    ]


def test_invalid_weight_rejected():
    with pytest.raises(
        ValueError
    ):
        HybridSearcher(
            _documents(),
            bm25_weight=0,
        )


def test_default_weights():
    searcher = HybridSearcher(
        _documents()
    )

    assert (
        searcher.bm25_weight
        == 1.0
    )

    assert (
        searcher.dense_weight
        == 2.0
    )
