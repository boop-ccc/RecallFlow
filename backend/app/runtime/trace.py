import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class TraceEvent:
    """
    一条运行轨迹。

    Trace 记录的是“Agent 怎么得到结果”，
    而不是只记录最后答案。
    """

    event_id: str
    run_id: str
    timestamp: str

    component: str
    action: str
    status: str

    latency_ms: float | None = None

    detail: dict[str, Any] | None = None


class TraceRecorder:
    """
    一次 Agent Run 的 Trace 收集器。

    第一版保存在内存中，
    同时支持导出 JSONL。

    后续如果切 PostgreSQL，
    上层 Agent 不需要改。
    """

    def __init__(
        self,
        run_id: str,
    ) -> None:
        self.run_id = run_id
        self.events: list[TraceEvent] = []

    def record(
        self,
        *,
        component: str,
        action: str,
        status: str,
        latency_ms: float | None = None,
        detail: dict[str, Any] | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            event_id=str(uuid4()),
            run_id=self.run_id,
            timestamp=datetime.now(
                timezone.utc
            ).isoformat(),
            component=component,
            action=action,
            status=status,
            latency_ms=latency_ms,
            detail=detail,
        )

        self.events.append(event)

        return event

    def to_dicts(
        self,
    ) -> list[dict[str, Any]]:
        return [
            asdict(event)
            for event in self.events
        ]

    def write_jsonl(
        self,
        path: str | Path,
    ) -> None:
        """
        JSONL 适合后续做：
        - Debug
        - Evaluation
        - Failure Analysis
        - 简单离线统计
        """
        output_path = Path(path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            for event in self.events:
                file.write(
                    json.dumps(
                        asdict(event),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
