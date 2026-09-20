import pytest

from app.runtime.permissions import (
    PermissionPolicy,
    ToolPermissionDenied,
)


def test_memory_agent_can_search_memory():
    policy = PermissionPolicy()

    assert policy.is_allowed(
        agent_name="memory_agent",
        tool_name="search_memory",
    )


def test_research_agent_cannot_search_memory():
    policy = PermissionPolicy()

    with pytest.raises(
        ToolPermissionDenied
    ):
        policy.require(
            agent_name=(
                "research_agent"
            ),
            tool_name=(
                "search_memory"
            ),
        )
