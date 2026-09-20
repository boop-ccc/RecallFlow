import asyncio
from datetime import (
    datetime,
    timezone,
)

from app.agents.verifier_agent import (
    VerifierAgent,
)
from app.runtime.harness import (
    AgentHarness,
)
from app.schemas.agent import (
    MemorySource,
)


async def main() -> None:
    verifier = VerifierAgent()

    harness = AgentHarness(
        timeout_seconds=5,
        max_steps=10,
        max_llm_calls=1,
        max_tool_calls=1,
        max_retrievals=1,
        max_subagents=1,
    )

    source = MemorySource(
        session_id="session-001",
        session_title=(
            "Agent Memory 研究"
        ),
        title=(
            "LangGraph Memory"
        ),
        locator=(
            "https://example.com/"
            "langgraph-memory"
        ),
        observed_at=datetime.now(
            timezone.utc
        ),
    )

    # ==================================
    # Case 1
    # 有证据的 Memory Answer
    # 应通过
    # ==================================

    async def valid_case():
        return verifier.verify(
            answer=(
                "你之前研究了 "
                "Agent Memory。"
            ),
            route="memory_only",
            agents_used=[
                "memory_agent"
            ],
            memory_sources=[
                source
            ],
            research_sources=[],
        )

    result, _ = await harness.run(
        user_query="valid verifier case",
        operation=valid_case,
    )

    print(
        "\nCASE 1:"
        " Evidence-backed Answer"
    )

    print(
        result.status,
        result.passed,
    )

    # ==================================
    # Case 2
    # 声称回答，但没有 Evidence
    # 应拒绝
    # ==================================

    async def invalid_case():
        return verifier.verify(
            answer=(
                "你之前研究了某个框架。"
            ),
            route="memory_only",
            agents_used=[
                "memory_agent"
            ],
            memory_sources=[],
            research_sources=[],
        )

    result, _ = await harness.run(
        user_query="invalid verifier case",
        operation=invalid_case,
    )

    print(
        "\nCASE 2:"
        " Answer Without Evidence"
    )

    print(
        result.status,
        result.passed,
    )

    for issue in result.issues:
        print(
            issue.severity,
            issue.code,
            issue.message,
        )

    # ==================================
    # Case 3
    # 没证据，但明确 Abstain
    # 不应视为 hallucination
    # ==================================

    async def abstain_case():
        return verifier.verify(
            answer=(
                "当前没有足够证据"
                "回答这个问题。"
            ),
            route="memory_only",
            agents_used=[
                "memory_agent"
            ],
            memory_sources=[],
            research_sources=[],
        )

    result, _ = await harness.run(
        user_query="abstain verifier case",
        operation=abstain_case,
    )

    print(
        "\nCASE 3:"
        " Explicit Abstention"
    )

    print(
        result.status,
        result.passed,
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
