from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.runtime.budget import RunBudget
from app.runtime.trace import TraceRecorder


@dataclass
class RunContext:
    """
    一次用户请求的运行时上下文。

    Supervisor、Memory Agent、Research Agent、
    LLMClient 和 Tool Runtime 在同一次请求中
    共享同一个 RunContext。
    """

    run_id: str
    user_query: str

    budget: RunBudget
    trace: TraceRecorder

    started_at: str

    # 当前路由，例如：
    # memory_only / research_only / memory_and_research
    route: str | None = None

    # 存放少量运行级元信息。
    # 不建议把完整私人历史塞进这里。
    metadata: dict[str, Any] = field(
        default_factory=dict
    )


_current_run_context: ContextVar[
    RunContext | None
] = ContextVar(
    "recallflow_run_context",
    default=None,
)


def create_run_context(
    *,
    user_query: str,
    budget: RunBudget | None = None,
) -> RunContext:
    run_id = str(uuid4())

    return RunContext(
        run_id=run_id,
        user_query=user_query,
        budget=budget or RunBudget(),
        trace=TraceRecorder(
            run_id=run_id
        ),
        started_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )


def get_run_context(
) -> RunContext | None:
    """
    获取当前请求的 RunContext。

    如果当前代码不是在 AgentHarness 内执行，
    返回 None。
    """
    return _current_run_context.get()


def set_run_context(
    context: RunContext,
) -> Token:
    return _current_run_context.set(
        context
    )


def reset_run_context(
    token: Token,
) -> None:
    _current_run_context.reset(
        token
    )
