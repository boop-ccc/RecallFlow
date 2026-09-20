from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.agent import MemorySource
from app.schemas.research import WebPageEvidence
from app.schemas.verifier import VerificationResult


class SupervisorDecision(BaseModel):
    """
    Supervisor Decision = Supervisor 路由决策。
    """

    route: Literal[
        "memory_only",
        "research_only",
        "memory_and_research",
    ]

    reason: str


class SupervisorAnswerDraft(BaseModel):
    """
    Memory + Research 完成后的汇总结果。
    """

    answer: str


class SupervisorResponse(BaseModel):
    """
    Supervisor 最终结果。

    verification:
    Verifier Agent 对最终 Answer + Sources
    做完 Evidence Boundary 检查后的结果。
    """

    answer: str

    route: str

    route_reason: str

    agents_used: list[str] = Field(
        default_factory=list
    )

    memory_sources: list[
        MemorySource
    ] = Field(
        default_factory=list
    )

    research_sources: list[
        WebPageEvidence
    ] = Field(
        default_factory=list
    )

    verification: (
        VerificationResult
        | None
    ) = None
