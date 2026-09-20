import asyncio
import inspect
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.runtime.context import (
    get_run_context,
)
from app.runtime.permissions import (
    PermissionPolicy,
)


class ToolNotFound(KeyError):
    """
    调用了没有注册的 Tool。
    """

    def __init__(
        self,
        tool_name: str,
    ) -> None:
        super().__init__(
            f"Tool 未注册：{tool_name}"
        )


@dataclass
class RegisteredTool:
    """
    Tool Registry 中的一条工具定义。
    """

    name: str
    handler: Callable[..., Any]
    description: str = ""
    timeout_seconds: float = 20.0

    # Web Search / Memory Search
    # 这类“召回候选”的工具记为 retrieval。
    retrieval: bool = False


class ToolRegistry:
    """
    Tool Registry = 工具统一执行入口。

    所有 Tool Call 在这里统一经过：

    Permission
        ↓
    Tool Budget
        ↓
    Retrieval Budget（如果需要）
        ↓
    Timeout
        ↓
    Trace
        ↓
    真正的 Tool
    """

    def __init__(
        self,
        *,
        permission_policy:
        PermissionPolicy | None = None,
    ) -> None:
        self.permission_policy = (
            permission_policy
            or PermissionPolicy()
        )

        self._tools: dict[
            str,
            RegisteredTool,
        ] = {}

    def register(
        self,
        tool: RegisteredTool,
    ) -> None:
        if tool.name in self._tools:
            raise ValueError(
                f"Tool 重复注册："
                f"{tool.name}"
            )

        self._tools[tool.name] = tool

    def get(
        self,
        tool_name: str,
    ) -> RegisteredTool:
        try:
            return self._tools[
                tool_name
            ]

        except KeyError as exc:
            raise ToolNotFound(
                tool_name
            ) from exc

    def list_tools(
        self,
    ) -> list[str]:
        return sorted(
            self._tools.keys()
        )

    async def execute(
        self,
        *,
        agent_name: str,
        tool_name: str,
        **kwargs: Any,
    ) -> Any:
        tool = self.get(
            tool_name
        )

        # 1. Hard Permission Check
        self.permission_policy.require(
            agent_name=agent_name,
            tool_name=tool_name,
        )

        context = get_run_context()

        if context is None:
            raise RuntimeError(
                "Tool 必须在 AgentHarness "
                "创建的 RunContext 中执行"
            )

        # 2. Tool / Retrieval Budget
        #
        # Step Budget 由 Agent Node 自己消耗，
        # Tool Registry 不重复计算 Step。
        context.budget.consume_tool_call()

        if tool.retrieval:
            context.budget.consume_retrieval()

        context.trace.record(
            component=agent_name,
            action=f"tool:{tool_name}",
            status="started",
            detail={
                # 避免把私人正文写进 Trace。
                "input_keys":
                    sorted(kwargs.keys()),
                "budget":
                    context.budget.snapshot(),
            },
        )

        started = time.perf_counter()

        try:
            result = await asyncio.wait_for(
                self._invoke(
                    tool.handler,
                    **kwargs,
                ),
                timeout=(
                    tool.timeout_seconds
                ),
            )

        except asyncio.TimeoutError as exc:
            latency_ms = (
                time.perf_counter()
                - started
            ) * 1000

            context.trace.record(
                component=agent_name,
                action=f"tool:{tool_name}",
                status="timeout",
                latency_ms=latency_ms,
                detail={
                    "timeout_seconds":
                        tool.timeout_seconds,
                },
            )

            raise RuntimeError(
                f"Tool '{tool_name}' "
                f"执行超时："
                f"{tool.timeout_seconds}s"
            ) from exc

        except Exception as exc:
            latency_ms = (
                time.perf_counter()
                - started
            ) * 1000

            context.trace.record(
                component=agent_name,
                action=f"tool:{tool_name}",
                status="error",
                latency_ms=latency_ms,
                detail={
                    "error_type":
                        type(exc).__name__,
                    "message":
                        str(exc)[:300],
                },
            )

            raise

        latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        context.trace.record(
            component=agent_name,
            action=f"tool:{tool_name}",
            status="success",
            latency_ms=latency_ms,
        )

        return result

    @staticmethod
    async def _invoke(
        handler: Callable[..., Any],
        **kwargs: Any,
    ) -> Any:
        """
        async Tool：
        直接 await。

        sync Tool：
        放进 worker thread，
        避免阻塞 asyncio event loop。
        """

        if inspect.iscoroutinefunction(
            handler
        ):
            return await handler(
                **kwargs
            )

        return await asyncio.to_thread(
            handler,
            **kwargs,
        )
