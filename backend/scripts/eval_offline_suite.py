import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from app.agents.supervisor import (
    SupervisorAgent,
)
from app.evaluation.metrics import (
    mean_reciprocal_rank,
    ndcg_at_k,
    recall_at_k,
)
from app.evaluation.offline_cases import (
    OFFLINE_DOCUMENTS,
    OFFLINE_RETRIEVAL_CASES,
    OFFLINE_ROUTING_CASES,
    OFFLINE_RESOLUTION_CASES,
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
from app.services.query_resolution_service import (
    QueryResolutionService,
)


ARTIFACT_PATH = Path(
    "artifacts/evaluation/offline_latest.json"
)


@dataclass
class FakeTurn:
    role: str
    content: str


def evaluate_routing() -> dict:
    correct = 0

    failures = []

    for case in OFFLINE_ROUTING_CASES:
        decision = (
            SupervisorAgent
            ._rule_based_route(
                case.query
            )
        )

        actual = (
            decision.route
            if decision is not None
            else None
        )

        passed = (
            actual
            == case.expected_route
        )

        if passed:
            correct += 1
        else:
            failures.append(
                {
                    "query":
                        case.query,
                    "expected":
                        case.expected_route,
                    "actual":
                        actual,
                }
            )

    total = len(
        OFFLINE_ROUTING_CASES
    )

    return {
        "cases": total,
        "accuracy": (
            correct / total
            if total
            else 0.0
        ),
        "failures": failures,
    }


def evaluate_resolution() -> dict:
    resolver = (
        QueryResolutionService()
    )

    correct = 0

    failures = []

    for case in (
        OFFLINE_RESOLUTION_CASES
    ):
        turns = []

        if case.previous_user:
            turns.append(
                FakeTurn(
                    role="user",
                    content=(
                        case.previous_user
                    ),
                )
            )

        if case.previous_assistant:
            turns.append(
                FakeTurn(
                    role="assistant",
                    content=(
                        case.previous_assistant
                    ),
                )
            )

        result = resolver.resolve(
            turns=turns,
            message=case.message,
        )

        contains_ok = all(
            expected.lower()
            in result.standalone_query.lower()
            for expected
            in case.expected_contains
        )

        passed = (
            result.used_history
            == case.expected_used_history
            and contains_ok
        )

        if passed:
            correct += 1
        else:
            failures.append(
                {
                    "message":
                        case.message,
                    "expected_used_history":
                        case.expected_used_history,
                    "actual_used_history":
                        result.used_history,
                    "standalone_query":
                        result.standalone_query,
                    "expected_contains":
                        list(
                            case.expected_contains
                        ),
                }
            )

    total = len(
        OFFLINE_RESOLUTION_CASES
    )

    return {
        "cases": total,
        "accuracy": (
            correct / total
            if total
            else 0.0
        ),
        "failures": failures,
    }


def _evaluate_retriever(
    name: str,
    search_fn,
) -> dict:
    recall1 = []
    recall3 = []
    ndcg3 = []
    rr_cases = []

    failures = []

    for case in (
        OFFLINE_RETRIEVAL_CASES
    ):
        ranked_ids = search_fn(
            case.query
        )

        relevant = set(
            case.relevant_doc_ids
        )

        r1 = recall_at_k(
            ranked_ids,
            relevant,
            1,
        )

        r3 = recall_at_k(
            ranked_ids,
            relevant,
            3,
        )

        n3 = ndcg_at_k(
            ranked_ids,
            relevant,
            3,
        )

        recall1.append(r1)
        recall3.append(r3)
        ndcg3.append(n3)
        rr_cases.append(
            (
                ranked_ids,
                relevant,
            )
        )

        if r1 < 1.0:
            failures.append(
                {
                    "query":
                        case.query,
                    "expected":
                        list(relevant),
                    "top3":
                        ranked_ids[:3],
                }
            )

    return {
        "name": name,
        "cases": len(
            OFFLINE_RETRIEVAL_CASES
        ),
        "recall_at_1":
            mean(recall1),
        "recall_at_3":
            mean(recall3),
        "mrr":
            mean_reciprocal_rank(
                rr_cases
            ),
        "ndcg_at_3":
            mean(ndcg3),
        "top1_failures":
            failures,
    }


def evaluate_retrieval() -> dict:
    documents = [
        RetrievalDocument(
            session_id=item.doc_id,
            title=item.title,
            text=item.text,
        )
        for item in OFFLINE_DOCUMENTS
    ]

    bm25 = BM25Searcher(
        documents
    )

    dense = DenseSearcher(
        documents
    )

    hybrid = HybridSearcher(
        documents
    )

    return {
        "bm25": _evaluate_retriever(
            "BM25",
            lambda query: [
                doc.session_id
                for doc, _
                in bm25.search(
                    query,
                    top_k=3,
                )
            ],
        ),
        "dense": _evaluate_retriever(
            "Dense",
            lambda query: [
                doc.session_id
                for doc, _
                in dense.search(
                    query,
                    top_k=3,
                )
            ],
        ),
        "hybrid": _evaluate_retriever(
            "Hybrid",
            lambda query: [
                result.document.session_id
                for result
                in hybrid.search(
                    query,
                    top_k=3,
                )
            ],
        ),
    }


def main() -> None:
    routing = evaluate_routing()
    resolution = evaluate_resolution()
    retrieval = evaluate_retrieval()

    total_cases = (
        routing["cases"]
        + resolution["cases"]
        + retrieval["bm25"]["cases"]
    )

    report = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "dataset_type":
            "controlled_offline_benchmark",
        "total_unique_cases":
            total_cases,
        "routing":
            routing,
        "query_resolution":
            resolution,
        "retrieval":
            retrieval,
        "note": (
            "这是可复现的离线控制评测，"
            "不是用户真实浏览历史上的生产指标。"
        ),
    }

    ARTIFACT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ARTIFACT_PATH.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "\n"
        "================================"
    )
    print("OFFLINE EVALUATION SUITE")
    print("================================")

    print(
        "Unique Cases:",
        total_cases,
    )

    print(
        "\nRouting Accuracy:",
        f"{routing['accuracy']:.2%}",
        f"({routing['cases']} cases)",
    )

    print(
        "Query Resolution Accuracy:",
        f"{resolution['accuracy']:.2%}",
        f"({resolution['cases']} cases)",
    )

    for key in (
        "bm25",
        "dense",
        "hybrid",
    ):
        item = retrieval[key]

        print(
            f"\n{item['name']}:"
        )
        print(
            "  Recall@1:",
            f"{item['recall_at_1']:.4f}",
        )
        print(
            "  Recall@3:",
            f"{item['recall_at_3']:.4f}",
        )
        print(
            "  MRR:",
            f"{item['mrr']:.4f}",
        )
        print(
            "  nDCG@3:",
            f"{item['ndcg_at_3']:.4f}",
        )

    print(
        "\nReport:",
        ARTIFACT_PATH,
    )

    print(
        "\n注意："
        "这套 75-case suite 是 Controlled Offline Benchmark。"
        "简历中的真实用户数据指标需要继续使用"
        " Chrome Capture 后的 WorkSession 数据单独评测。"
    )


if __name__ == "__main__":
    main()
