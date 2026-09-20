from dataclasses import dataclass

from app.services.query_resolution_service import (
    QueryResolutionService,
)


@dataclass
class FakeTurn:
    role: str
    content: str


def _turns():
    return [
        FakeTurn(
            role="user",
            content=(
                "我之前在比较 BM25 "
                "和 Dense。"
            ),
        ),
        FakeTurn(
            role="assistant",
            content=(
                "两者召回方式不同。"
            ),
        ),
    ]


def test_followup_uses_previous_user():
    resolver = (
        QueryResolutionService()
    )

    result = resolver.resolve(
        turns=_turns(),
        message="继续这个方向",
    )

    assert (
        result.used_history
        is True
    )

    assert (
        "BM25"
        in result.standalone_query
    )


def test_more_detail_is_followup():
    """
    对应离线 75-case 中之前唯一失败的
    “再详细说”场景。
    """

    resolver = (
        QueryResolutionService()
    )

    result = resolver.resolve(
        turns=_turns(),
        message="再详细说",
    )

    assert (
        result.used_history
        is True
    )

    assert (
        "BM25"
        in result.standalone_query
    )

    assert (
        "再详细说"
        in result.standalone_query
    )


def test_explicit_query_passthrough():
    resolver = (
        QueryResolutionService()
    )

    message = (
        "现在 Agent Memory "
        "有哪些新方案？"
    )

    result = resolver.resolve(
        turns=[],
        message=message,
    )

    assert (
        result.standalone_query
        == message
    )

    assert (
        result.used_history
        is False
    )
