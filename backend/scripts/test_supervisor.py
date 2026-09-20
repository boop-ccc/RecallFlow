import asyncio
import sys
from pathlib import Path

from app.agents.supervisor import (
    SupervisorAgent,
)
from app.db.session import (
    AsyncSessionFactory,
)
from app.runtime.harness import (
    AgentHarness,
)


async def main() -> None:
    # 可以：
    #
    # python -m scripts.test_supervisor
    #
    # 也可以：
    #
    # python -m scripts.test_supervisor "现在 Agent Memory 有哪些新方案？"

    if len(sys.argv) > 1:
        query = " ".join(
            sys.argv[1:]
        )
    else:
        query = (
            "我之前研究 Agent "
            "长期记忆的时候看了什么？"
        )

    async with (
        AsyncSessionFactory()
        as db
    ):
        supervisor = (
            SupervisorAgent(db)
        )

        harness = AgentHarness(
            timeout_seconds=90,

            # 一个混合任务可能同时跑两个Agent，
            # 所以这里给足正常执行预算，
            # 但仍然不是无限。
            max_steps=30,
            max_llm_calls=8,
            max_tool_calls=12,
            max_retrievals=4,
            max_subagents=3,
        )

        result, context = (
            await harness.run(
                user_query=query,
                operation=lambda:
                    supervisor.run(
                        query
                    ),
            )
        )

        print(
            "\n"
            "=============================="
        )
        print("FINAL ANSWER")
        print("==============================")
        print(result.answer)

        print(
            "\nRoute:",
            result.route,
        )

        print(
            "Agents:",
            result.agents_used,
        )

        print(
            "Memory Sources:",
            len(
                result.memory_sources
            ),
        )

        print(
            "Research Sources:",
            len(
                result.research_sources
            ),
        )


        print(
            "\n"
            "=============================="
        )
        print("VERIFICATION")
        print("==============================")

        if result.verification is None:
            print(
                "Verification: None"
            )
        else:
            print(
                "Status:",
                result.verification.status,
            )

            print(
                "Passed:",
                result.verification.passed,
            )

            print(
                "Memory Session IDs:",
                result.verification
                .memory_session_ids,
            )

            print(
                "Research URLs:",
                result.verification
                .research_urls,
            )

            if result.verification.issues:
                print("Issues:")

                for issue in (
                    result.verification.issues
                ):
                    print(
                        f"- [{issue.severity}] "
                        f"{issue.code}: "
                        f"{issue.message}"
                    )

        print(
            "\n"
            "=============================="
        )
        print("RUN BUDGET")
        print("==============================")

        print(
            context.budget.snapshot()
        )

        print(
            "\n"
            "=============================="
        )
        print("TRACE")
        print("==============================")

        for event in (
            context.trace.events
        ):
            print(
                event.component,
                "->",
                event.action,
                "|",
                event.status,
                "|",
                (
                    f"{event.latency_ms:.1f} ms"
                    if event.latency_ms
                    is not None
                    else "-"
                ),
            )

            if event.detail:
                print(
                    "   ",
                    event.detail,
                )

        trace_path = (
            Path("artifacts")
            / "traces"
            / f"{context.run_id}.jsonl"
        )

        context.trace.write_jsonl(
            trace_path
        )

        print(
            "\nTrace saved:",
            trace_path,
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
