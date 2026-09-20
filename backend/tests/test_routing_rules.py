import pytest

from app.agents.supervisor import (
    SupervisorAgent,
)


@pytest.mark.parametrize(
    (
        "query",
        "expected",
    ),
    [
        (
            "我之前研究 Agent Memory 看了什么？",
            "memory_only",
        ),
        (
            "现在 Agent Memory 有哪些新方案？",
            "research_only",
        ),
        (
            "继续我之前的研究，再看看现在有什么新方案。",
            "memory_and_research",
        ),
    ],
)
def test_high_confidence_routes(
    query,
    expected,
):
    decision = (
        SupervisorAgent
        ._rule_based_route(
            query
        )
    )

    assert decision is not None
    assert decision.route == expected
