import pytest

from app.evaluation.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
)


def test_recall_at_k():
    ranked = [
        "a",
        "b",
        "c",
    ]

    relevant = {"b"}

    assert (
        recall_at_k(
            ranked,
            relevant,
            1,
        )
        == 0.0
    )

    assert (
        recall_at_k(
            ranked,
            relevant,
            2,
        )
        == 1.0
    )


def test_mrr():
    cases = [
        (
            ["a", "b"],
            {"a"},
        ),
        (
            ["x", "b"],
            {"b"},
        ),
    ]

    assert (
        mean_reciprocal_rank(
            cases
        )
        == pytest.approx(
            0.75
        )
    )


def test_ndcg():
    score = ndcg_at_k(
        ["a", "b", "c"],
        {"a"},
        3,
    )

    assert score == pytest.approx(
        1.0
    )
