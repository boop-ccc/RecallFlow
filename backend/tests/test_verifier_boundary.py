from datetime import (
    datetime,
    timezone,
)

from app.agents.verifier_agent import (
    VerifierAgent,
)
from app.schemas.agent import (
    MemorySource,
)


def _source():
    return MemorySource(
        session_id="session-1",
        session_title="Agent Memory",
        title="LangGraph Memory",
        locator=(
            "https://example.com/memory"
        ),
        observed_at=datetime.now(
            timezone.utc
        ),
    )


def test_evidence_backed_answer_passes():
    result = VerifierAgent().verify(
        answer="你之前研究过 Agent Memory。",
        route="memory_only",
        agents_used=[
            "memory_agent"
        ],
        memory_sources=[
            _source()
        ],
        research_sources=[],
    )

    assert result.passed is True
    assert result.status == "verified"


def test_answer_without_evidence_rejected():
    result = VerifierAgent().verify(
        answer="你之前研究过 Agent Memory。",
        route="memory_only",
        agents_used=[
            "memory_agent"
        ],
        memory_sources=[],
        research_sources=[],
    )

    assert result.passed is False
    assert result.status == "rejected"


def test_abstention_without_evidence_allowed():
    result = VerifierAgent().verify(
        answer=(
            "当前没有足够证据回答这个问题。"
        ),
        route="memory_only",
        agents_used=[
            "memory_agent"
        ],
        memory_sources=[],
        research_sources=[],
    )

    assert result.passed is True
    assert (
        result.status
        == "verified_with_warnings"
    )
