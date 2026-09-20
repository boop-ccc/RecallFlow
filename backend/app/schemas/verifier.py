from typing import Literal

from pydantic import BaseModel, Field


class VerificationCheck(BaseModel):
    """
    Verification Check = 一项验证检查。
    """

    name: str
    passed: bool
    detail: str


class VerificationIssue(BaseModel):
    """
    Verification Issue = 验证发现的问题。
    """

    severity: Literal[
        "warning",
        "error",
    ]

    code: str
    message: str


class VerificationResult(BaseModel):
    """
    Verifier Agent 的最终验证结果。

    verified:
        所有硬性 Evidence Boundary 都通过。

    verified_with_warnings:
        没有硬错误，但存在降级/拒答/部分成功等情况。

    rejected:
        发现无证据答案、来源不合法、路由与来源冲突等硬错误。
    """

    passed: bool

    status: Literal[
        "verified",
        "verified_with_warnings",
        "rejected",
    ]

    checks: list[
        VerificationCheck
    ] = Field(
        default_factory=list
    )

    issues: list[
        VerificationIssue
    ] = Field(
        default_factory=list
    )

    memory_session_ids: list[str] = Field(
        default_factory=list
    )

    research_urls: list[str] = Field(
        default_factory=list
    )
