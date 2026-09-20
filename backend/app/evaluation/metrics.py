import math
from statistics import mean


def recall_at_k(
    ranked_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """
    Recall@K

    在 Top-K 结果中找回了多少 relevant item。

    当前 Demo 每个 query 通常只有一个
    relevant WorkSession，所以它也等价于 Hit@K。
    """

    if not relevant_ids:
        return 0.0

    retrieved = set(
        ranked_ids[:k]
    )

    return (
        len(
            retrieved
            & relevant_ids
        )
        / len(relevant_ids)
    )


def reciprocal_rank(
    ranked_ids: list[str],
    relevant_ids: set[str],
) -> float:
    """
    Reciprocal Rank

    第一个正确结果：
    rank=1 -> 1.0
    rank=2 -> 0.5
    rank=3 -> 0.333...
    """

    for rank, item_id in enumerate(
        ranked_ids,
        start=1,
    ):
        if item_id in relevant_ids:
            return 1.0 / rank

    return 0.0


def mean_reciprocal_rank(
    cases: list[
        tuple[
            list[str],
            set[str],
        ]
    ],
) -> float:
    if not cases:
        return 0.0

    return mean(
        reciprocal_rank(
            ranked_ids,
            relevant_ids,
        )
        for (
            ranked_ids,
            relevant_ids,
        )
        in cases
    )


def ndcg_at_k(
    ranked_ids: list[str],
    relevant_ids: set[str],
    k: int,
) -> float:
    """
    binary relevance 的 nDCG@K。

    对当前 Retrieval Evaluation 足够。
    """

    if not relevant_ids:
        return 0.0

    dcg = 0.0

    for rank, item_id in enumerate(
        ranked_ids[:k],
        start=1,
    ):
        relevance = (
            1.0
            if item_id
            in relevant_ids
            else 0.0
        )

        if relevance:
            dcg += (
                relevance
                / math.log2(
                    rank + 1
                )
            )

    ideal_hits = min(
        len(relevant_ids),
        k,
    )

    idcg = sum(
        1.0
        / math.log2(
            rank + 1
        )
        for rank in range(
            1,
            ideal_hits + 1,
        )
    )

    if idcg == 0:
        return 0.0

    return dcg / idcg
