import json
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from statistics import mean


TRACE_DIR = Path(
    "artifacts/traces"
)

OUTPUT_PATH = Path(
    "artifacts/evaluation/trace_latest.json"
)


def percentile(
    values: list[float],
    p: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)

    index = int(
        round(
            (len(ordered) - 1)
            * p
        )
    )

    return ordered[index]


def main() -> None:
    paths = sorted(
        TRACE_DIR.glob("*.jsonl")
    )

    if not paths:
        print(
            "No trace files found in "
            "artifacts/traces."
        )
        return

    run_latencies = []

    successful_runs = 0
    failed_runs = 0

    llm_calls = 0
    tool_calls = 0
    rate_limits = 0
    degraded_events = 0
    total_tokens = 0

    for path in paths:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                event = json.loads(
                    line
                )

                component = (
                    event.get(
                        "component"
                    )
                )

                action = event.get(
                    "action"
                )

                status = event.get(
                    "status"
                )

                detail = (
                    event.get(
                        "detail"
                    )
                    or {}
                )

                if (
                    component
                    == "harness"
                    and action == "run"
                ):
                    if (
                        status
                        == "success"
                    ):
                        successful_runs += 1

                    elif status in {
                        "error",
                        "timeout",
                    }:
                        failed_runs += 1

                    if (
                        status
                        in {
                            "success",
                            "error",
                            "timeout",
                        }
                        and event.get(
                            "latency_ms"
                        )
                        is not None
                    ):
                        run_latencies.append(
                            float(
                                event[
                                    "latency_ms"
                                ]
                            )
                        )

                if (
                    component == "llm"
                    and action
                    == "generate_json"
                    and status
                    == "started"
                ):
                    llm_calls += 1

                if (
                    isinstance(
                        action,
                        str,
                    )
                    and action.startswith(
                        "tool:"
                    )
                    and status
                    == "started"
                ):
                    tool_calls += 1

                if (
                    status
                    == "rate_limited"
                ):
                    rate_limits += 1

                if (
                    status
                    == "degraded"
                ):
                    degraded_events += 1

                if (
                    component == "llm"
                    and action
                    == "generate_json"
                    and status
                    == "success"
                ):
                    value = detail.get(
                        "total_tokens"
                    )

                    if isinstance(
                        value,
                        int,
                    ):
                        total_tokens += value

    completed_runs = (
        successful_runs
        + failed_runs
    )

    report = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),
        "trace_files":
            len(paths),
        "completed_runs":
            completed_runs,
        "successful_runs":
            successful_runs,
        "failed_runs":
            failed_runs,
        "run_success_rate":
            (
                successful_runs
                / completed_runs
                if completed_runs
                else 0.0
            ),
        "mean_latency_ms":
            (
                mean(run_latencies)
                if run_latencies
                else 0.0
            ),
        "p50_latency_ms":
            percentile(
                run_latencies,
                0.50,
            ),
        "p95_latency_ms":
            percentile(
                run_latencies,
                0.95,
            ),
        "logical_llm_calls":
            llm_calls,
        "tool_calls":
            tool_calls,
        "rate_limit_events":
            rate_limits,
        "degraded_events":
            degraded_events,
        "recorded_llm_tokens":
            total_tokens,
        "avg_llm_calls_per_run":
            (
                llm_calls
                / completed_runs
                if completed_runs
                else 0.0
            ),
        "avg_tool_calls_per_run":
            (
                tool_calls
                / completed_runs
                if completed_runs
                else 0.0
            ),
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
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
    print("TRACE EVALUATION")
    print("================================")

    for key, value in (
        report.items()
    ):
        if key == "generated_at":
            continue

        print(
            f"{key}: {value}"
        )

    print(
        "\nReport:",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()
