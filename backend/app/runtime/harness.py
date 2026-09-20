import asyncio
import time
from typing import Awaitable, Callable, TypeVar

from app.runtime.budget import RunBudget
from app.runtime.context import (
    RunContext,
    create_run_context,
    reset_run_context,
    set_run_context,
)


T = TypeVar("T")


class AgentHarness:
    """
    Agent Harness
    = Agent 的统一运行控制层。

    它不负责业务推理。

    它负责回答这些工程问题：

    - 一次 Run 最多执行多久？
    - 一共允许多少 Step？
    - LLM 最多调用多少次？
    - Tool 最多调用多少次？
    - 子 Agent 最多启动多少个？
    - 出错以后如何留下 Trace？
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 90.0,
        max_steps: int = 20,
        max_llm_calls: int = 8,
        max_tool_calls: int = 10,
        max_retrievals: int = 4,
        max_subagents: int = 3,
    ) -> None:
        self.timeout_seconds = (
            timeout_seconds
        )

        self.budget_template = {
            "max_steps":
                max_steps,
            "max_llm_calls":
                max_llm_calls,
            "max_tool_calls":
                max_tool_calls,
            "max_retrievals":
                max_retrievals,
            "max_subagents":
                max_subagents,
        }

    def _new_budget(
        self,
    ) -> RunBudget:
        return RunBudget(
            **self.budget_template
        )

    async def run(
        self,
        *,
        user_query: str,
        operation: Callable[
            [],
            Awaitable[T],
        ],
    ) -> tuple[
        T,
        RunContext,
    ]:
        """
        运行一次完整 Agent 请求。

        Example:

        result, context = await harness.run(
            user_query=query,
            operation=lambda:
                supervisor.run(query),
        )
        """

        context = create_run_context(
            user_query=user_query,
            budget=self._new_budget(),
        )

        token = set_run_context(
            context
        )

        started = time.perf_counter()

        context.trace.record(
            component="harness",
            action="run",
            status="started",
            detail={
                "budget":
                    context.budget.snapshot()
            },
        )

        try:
            result = await asyncio.wait_for(
                operation(),
                timeout=(
                    self.timeout_seconds
                ),
            )

        except asyncio.TimeoutError as exc:
            latency_ms = (
                time.perf_counter()
                - started
            ) * 1000

            context.trace.record(
                component="harness",
                action="run",
                status="timeout",
                latency_ms=latency_ms,
                detail={
                    "timeout_seconds":
                        self.timeout_seconds,
                    "budget":
                        context.budget.snapshot(),
                },
            )

            raise RuntimeError(
                "Agent Run 总超时："
                f"{self.timeout_seconds}s"
            ) from exc

        except Exception as exc:
            latency_ms = (
                time.perf_counter()
                - started
            ) * 1000

            context.trace.record(
                component="harness",
                action="run",
                status="error",
                latency_ms=latency_ms,
                detail={
                    "error_type":
                        type(exc).__name__,
                    "message":
                        str(exc)[:500],
                    "budget":
                        context.budget.snapshot(),
                },
            )

            raise

        else:
            latency_ms = (
                time.perf_counter()
                - started
            ) * 1000

            context.trace.record(
                component="harness",
                action="run",
                status="success",
                latency_ms=latency_ms,
                detail={
                    "budget":
                        context.budget.snapshot()
                },
            )

            return (
                result,
                context,
            )

        finally:
            reset_run_context(
                token
            )
