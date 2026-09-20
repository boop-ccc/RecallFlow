import asyncio

from app.runtime.budget import (
    BudgetExceeded,
)
from app.runtime.harness import (
    AgentHarness,
)
from app.runtime.permissions import (
    ToolPermissionDenied,
)
from app.runtime.tool_registry import (
    RegisteredTool,
    ToolRegistry,
)


async def fake_memory_search(
    query: str,
) -> list[str]:
    """
    假 Tool：
    不访问 Groq，
    只用于测试 Runtime。
    """
    await asyncio.sleep(0.05)

    return [
        f"memory hit for: {query}"
    ]


async def main() -> None:
    registry = ToolRegistry()

    registry.register(
        RegisteredTool(
            name="search_memory",
            handler=fake_memory_search,
            description=(
                "Search private "
                "historical memory"
            ),
            timeout_seconds=2,
            retrieval=True,
        )
    )

    harness = AgentHarness(
        timeout_seconds=5,
        max_steps=5,
        max_llm_calls=2,
        max_tool_calls=2,
        max_retrievals=1,
        max_subagents=2,
    )

    query = (
        "我之前研究 Agent Memory "
        "的时候看了什么？"
    )

    async def operation():
        return await registry.execute(
            agent_name="memory_agent",
            tool_name="search_memory",
            query=query,
        )

    result, context = await harness.run(
        user_query=query,
        operation=operation,
    )

    print(
        "\n=== Runtime Basic Test ==="
    )
    print(
        "Result:",
        result,
    )
    print(
        "Budget:",
        context.budget.snapshot(),
    )
    print(
        "Trace Events:",
        len(context.trace.events),
    )

    for event in context.trace.events:
        print(
            event.component,
            event.action,
            event.status,
            event.latency_ms,
        )

    # ---------------------------------
    # Permission Test
    # Research Agent 不应访问私人Memory
    # ---------------------------------

    async def permission_test():
        return await registry.execute(
            agent_name="research_agent",
            tool_name="search_memory",
            query=query,
        )

    try:
        await harness.run(
            user_query=query,
            operation=permission_test,
        )

    except ToolPermissionDenied as exc:
        print(
            "\nPermission Test PASS:"
        )
        print(exc)

    # ---------------------------------
    # Budget Test
    # max_retrievals = 1
    # 第二次 Memory Search 应被拦截
    # ---------------------------------

    async def budget_test():
        await registry.execute(
            agent_name="memory_agent",
            tool_name="search_memory",
            query=query,
        )

        return await registry.execute(
            agent_name="memory_agent",
            tool_name="search_memory",
            query=query,
        )

    try:
        await harness.run(
            user_query=query,
            operation=budget_test,
        )

    except BudgetExceeded as exc:
        print(
            "\nBudget Test PASS:"
        )
        print(exc)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
