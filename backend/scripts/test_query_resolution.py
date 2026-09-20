from dataclasses import dataclass

from app.services.query_resolution_service import (
    QueryResolutionService,
)


@dataclass
class FakeTurn:
    role: str
    content: str


def main() -> None:
    resolver = (
        QueryResolutionService()
    )

    cases = [
        {
            "name":
                "explicit query",
            "turns": [],
            "message":
                "现在 Agent Memory 有什么新方案？",
        },
        {
            "name":
                "continue previous topic",
            "turns": [
                FakeTurn(
                    role="user",
                    content=(
                        "我之前研究 Agent "
                        "长期记忆的时候看了什么？"
                    ),
                ),
                FakeTurn(
                    role="assistant",
                    content=(
                        "你看了 LangGraph Memory..."
                    ),
                ),
            ],
            "message":
                "继续这个方向",
        },
        {
            "name":
                "follow-up with fresh research",
            "turns": [
                FakeTurn(
                    role="user",
                    content=(
                        "我之前研究 Agent "
                        "长期记忆的时候看了什么？"
                    ),
                ),
                FakeTurn(
                    role="assistant",
                    content=(
                        "你看了 LangGraph Memory..."
                    ),
                ),
            ],
            "message":
                "继续这个方向，再看看现在有没有新的方案",
        },
    ]

    for case in cases:
        result = resolver.resolve(
            turns=case["turns"],
            message=case["message"],
        )

        print(
            "\n=============================="
        )
        print(case["name"])
        print("==============================")

        print(
            "Strategy:",
            result.strategy,
        )

        print(
            "Used History:",
            result.used_history,
        )

        print(
            "Standalone:",
            result.standalone_query,
        )

        print(
            "Routing:",
            result.routing_query,
        )


if __name__ == "__main__":
    main()
