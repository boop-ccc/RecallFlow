from app.agents.supervisor import (
    SupervisorAgent,
)
from app.evaluation.datasets import (
    ROUTING_CASES,
)


def main() -> None:
    correct = 0
    routed = 0

    print(
        "\n"
        "================================"
    )
    print("ROUTING EVALUATION")
    print("================================")

    for index, case in enumerate(
        ROUTING_CASES,
        start=1,
    ):
        decision = (
            SupervisorAgent
            ._rule_based_route(
                case.query
            )
        )

        actual = (
            decision.route
            if decision
            is not None
            else None
        )

        if actual is not None:
            routed += 1

        passed = (
            actual
            == case.expected_route
        )

        if passed:
            correct += 1

        print(
            f"{index:02d}. "
            f"{'PASS' if passed else 'FAIL'} "
            f"| expected={case.expected_route} "
            f"| actual={actual}"
        )

        if not passed:
            print(
                "    Query:",
                case.query,
            )

    total = len(
        ROUTING_CASES
    )

    accuracy = (
        correct / total
        if total
        else 0.0
    )

    coverage = (
        routed / total
        if total
        else 0.0
    )

    print(
        "\n--------------------------------"
    )
    print(
        "Cases:",
        total,
    )
    print(
        "Rule Coverage:",
        f"{coverage:.2%}",
    )
    print(
        "Rule Accuracy:",
        f"{accuracy:.2%}",
    )
    print(
        "--------------------------------"
    )

    print(
        "\n说明："
        "这里评估的是 Hybrid Router 的"
        "确定性 Rule Layer。"
        "模糊语义请求后续单独做 Online LLM Evaluation。"
    )


if __name__ == "__main__":
    main()
