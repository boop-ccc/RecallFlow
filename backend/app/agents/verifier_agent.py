from urllib.parse import urlparse

from app.runtime.context import (
    get_run_context,
)
from app.schemas.agent import (
    MemorySource,
)
from app.schemas.research import (
    WebPageEvidence,
)
from app.schemas.verifier import (
    VerificationCheck,
    VerificationIssue,
    VerificationResult,
)


class VerifierAgent:
    """
    Verifier Agent = 证据验证智能体。

    当前在线链路先做 Deterministic Verification：
    确定性验证。

    它不负责重新回答问题，而是检查：

    1. Answer 是否为空
    2. Route 和实际 Agent 是否一致
    3. Memory 结论是否绑定真实 Memory Source
    4. Research 结论是否绑定真实 URL
    5. Source 格式是否合法
    6. Partial Success / Abstention 是否被明确暴露

    为什么第一层不用 LLM？

    因为：
    “URL 是否存在、Session ID 是否存在、Agent 是否越界”
    都是程序可以 100% 确定的事情，
    不应该再交给概率模型判断。
    """

    AGENT_NAME = "verifier_agent"

    _ABSTENTION_MARKERS = (
        "没有足够证据",
        "证据不足",
        "无法可靠回答",
        "无法回答这个问题",
    )

    _DEGRADED_MARKERS = (
        "暂时不可用",
        "暂时受限",
        "稍后重试",
        "分支暂时不可用",
    )

    def _start_step(
        self,
    ) -> None:
        context = get_run_context()

        if context is None:
            return

        context.budget.consume_step()

        context.trace.record(
            component=self.AGENT_NAME,
            action="verify",
            status="started",
            detail={
                "step":
                    context.budget.steps,
            },
        )

    @classmethod
    def _looks_like_abstention(
        cls,
        answer: str,
    ) -> bool:
        return any(
            marker in answer
            for marker in (
                cls._ABSTENTION_MARKERS
            )
        )

    @classmethod
    def _looks_degraded(
        cls,
        answer: str,
    ) -> bool:
        return any(
            marker in answer
            for marker in (
                cls._DEGRADED_MARKERS
            )
        )

    @staticmethod
    def _valid_http_url(
        value: str,
    ) -> bool:
        parsed = urlparse(value)

        return (
            parsed.scheme
            in {"http", "https"}
            and bool(parsed.netloc)
        )

    @staticmethod
    def _add_check(
        checks: list[
            VerificationCheck
        ],
        *,
        name: str,
        passed: bool,
        detail: str,
    ) -> None:
        checks.append(
            VerificationCheck(
                name=name,
                passed=passed,
                detail=detail,
            )
        )

    @staticmethod
    def _add_issue(
        issues: list[
            VerificationIssue
        ],
        *,
        severity: str,
        code: str,
        message: str,
    ) -> None:
        issues.append(
            VerificationIssue(
                severity=severity,
                code=code,
                message=message,
            )
        )

    def verify(
        self,
        *,
        answer: str,
        route: str,
        agents_used: list[str],
        memory_sources: list[
            MemorySource
        ],
        research_sources: list[
            WebPageEvidence
        ],
    ) -> VerificationResult:
        self._start_step()

        checks: list[
            VerificationCheck
        ] = []

        issues: list[
            VerificationIssue
        ] = []

        answer = answer.strip()

        is_abstention = (
            self._looks_like_abstention(
                answer
            )
        )

        is_degraded = (
            self._looks_degraded(
                answer
            )
        )

        # ==================================
        # 1. Answer Integrity
        # 回答完整性
        # ==================================

        answer_ok = bool(answer)

        self._add_check(
            checks,
            name="answer_not_empty",
            passed=answer_ok,
            detail=(
                "最终回答非空。"
                if answer_ok
                else "最终回答为空。"
            ),
        )

        if not answer_ok:
            self._add_issue(
                issues,
                severity="error",
                code="empty_answer",
                message="最终回答为空。",
            )

        # ==================================
        # 2. Route / Agent Boundary
        # 路由与Agent边界
        # ==================================

        valid_routes = {
            "memory_only",
            "research_only",
            "memory_and_research",
        }

        route_ok = (
            route in valid_routes
        )

        self._add_check(
            checks,
            name="route_valid",
            passed=route_ok,
            detail=(
                f"route={route}"
            ),
        )

        if not route_ok:
            self._add_issue(
                issues,
                severity="error",
                code="invalid_route",
                message=(
                    f"未知路由：{route}"
                ),
            )

        agent_set = set(
            agents_used
        )

        if (
            route == "memory_only"
            and "research_agent"
            in agent_set
        ):
            self._add_issue(
                issues,
                severity="error",
                code="route_agent_mismatch",
                message=(
                    "memory_only 路由却执行了 "
                    "Research Agent。"
                ),
            )

        if (
            route == "research_only"
            and "memory_agent"
            in agent_set
        ):
            self._add_issue(
                issues,
                severity="error",
                code="route_agent_mismatch",
                message=(
                    "research_only 路由却执行了 "
                    "Memory Agent。"
                ),
            )

        if (
            route
            == "memory_and_research"
        ):
            expected = {
                "memory_agent",
                "research_agent",
            }

            missing = (
                expected - agent_set
            )

            if missing:
                # 允许 Partial Success，
                # 但必须显式记录 warning。
                self._add_issue(
                    issues,
                    severity="warning",
                    code="partial_success",
                    message=(
                        "混合任务只完成了部分 "
                        f"Sub-Agent：缺少 {sorted(missing)}"
                    ),
                )

        # ==================================
        # 3. Memory Provenance
        # 历史来源追踪
        # ==================================

        memory_session_ids: list[
            str
        ] = []

        memory_seen: set[
            tuple[str, str]
        ] = set()

        memory_sources_ok = True

        for source in memory_sources:
            if (
                not source.session_id
                or not source.locator
            ):
                memory_sources_ok = False

                self._add_issue(
                    issues,
                    severity="error",
                    code="invalid_memory_source",
                    message=(
                        "Memory Source 缺少 "
                        "session_id 或 locator。"
                    ),
                )

                continue

            key = (
                source.session_id,
                source.locator,
            )

            if key in memory_seen:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="duplicate_memory_source",
                    message=(
                        "发现重复 Memory Source："
                        f"{source.locator}"
                    ),
                )
                continue

            memory_seen.add(key)

            if (
                source.session_id
                not in memory_session_ids
            ):
                memory_session_ids.append(
                    source.session_id
                )

        self._add_check(
            checks,
            name="memory_source_integrity",
            passed=memory_sources_ok,
            detail=(
                "Memory Source 均绑定了 "
                "session_id + locator。"
                if memory_sources_ok
                else "存在不完整 Memory Source。"
            ),
        )

        # ==================================
        # 4. Research Provenance
        # 外部来源追踪
        # ==================================

        research_urls: list[str] = []

        research_seen: set[str] = set()

        research_sources_ok = True

        for source in research_sources:
            if not self._valid_http_url(
                source.url
            ):
                research_sources_ok = False

                self._add_issue(
                    issues,
                    severity="error",
                    code="invalid_research_url",
                    message=(
                        "Research Source URL "
                        f"不合法：{source.url}"
                    ),
                )

                continue

            if source.url in research_seen:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="duplicate_research_source",
                    message=(
                        "发现重复 Research URL："
                        f"{source.url}"
                    ),
                )
                continue

            research_seen.add(
                source.url
            )

            research_urls.append(
                source.url
            )

        self._add_check(
            checks,
            name="research_source_integrity",
            passed=research_sources_ok,
            detail=(
                "Research Source 均为合法 "
                "HTTP/HTTPS URL。"
                if research_sources_ok
                else "存在非法 Research URL。"
            ),
        )

        # ==================================
        # 5. Evidence Boundary
        # 证据边界
        # ==================================

        memory_used = (
            "memory_agent"
            in agent_set
        )

        research_used = (
            "research_agent"
            in agent_set
        )

        if (
            memory_used
            and not memory_sources
        ):
            if is_abstention:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="memory_abstained",
                    message=(
                        "Memory Agent 没有来源，"
                        "但最终回答明确拒答。"
                    ),
                )

            elif is_degraded:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="memory_degraded",
                    message=(
                        "Memory 分支没有来源，"
                        "但回答明确暴露了降级状态。"
                    ),
                )

            else:
                self._add_issue(
                    issues,
                    severity="error",
                    code="memory_answer_without_evidence",
                    message=(
                        "Memory Agent 参与了回答，"
                        "但没有提供历史 Evidence。"
                    ),
                )

        if (
            research_used
            and not research_sources
        ):
            if is_abstention:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="research_abstained",
                    message=(
                        "Research Agent 没有来源，"
                        "但最终回答明确拒答。"
                    ),
                )

            elif is_degraded:
                self._add_issue(
                    issues,
                    severity="warning",
                    code="research_degraded",
                    message=(
                        "Research 分支没有来源，"
                        "但回答明确暴露了降级状态。"
                    ),
                )

            else:
                self._add_issue(
                    issues,
                    severity="error",
                    code="research_answer_without_evidence",
                    message=(
                        "Research Agent 参与了回答，"
                        "但没有提供公开 Evidence。"
                    ),
                )

        if (
            memory_sources
            and not memory_used
        ):
            self._add_issue(
                issues,
                severity="error",
                code="unexpected_memory_evidence",
                message=(
                    "Memory Agent 未执行，"
                    "却出现了 Memory Source。"
                ),
            )

        if (
            research_sources
            and not research_used
        ):
            self._add_issue(
                issues,
                severity="error",
                code="unexpected_research_evidence",
                message=(
                    "Research Agent 未执行，"
                    "却出现了 Research Source。"
                ),
            )

        evidence_exists = bool(
            memory_sources
            or research_sources
        )

        if (
            not evidence_exists
            and not is_abstention
            and not is_degraded
        ):
            self._add_issue(
                issues,
                severity="error",
                code="answer_without_any_evidence",
                message=(
                    "最终回答没有任何 Evidence，"
                    "且没有明确拒答或降级。"
                ),
            )

        self._add_check(
            checks,
            name="evidence_boundary",
            passed=not any(
                issue.severity == "error"
                and issue.code in {
                    "memory_answer_without_evidence",
                    "research_answer_without_evidence",
                    "unexpected_memory_evidence",
                    "unexpected_research_evidence",
                    "answer_without_any_evidence",
                }
                for issue in issues
            ),
            detail=(
                "最终回答与实际 Agent 来源已绑定，"
                "无证据结论会被拦截。"
            ),
        )

        # ==================================
        # 6. Final Status
        # ==================================

        has_error = any(
            issue.severity == "error"
            for issue in issues
        )

        has_warning = any(
            issue.severity == "warning"
            for issue in issues
        )

        if has_error:
            status = "rejected"
            passed = False

        elif has_warning:
            status = (
                "verified_with_warnings"
            )
            passed = True

        else:
            status = "verified"
            passed = True

        result = VerificationResult(
            passed=passed,
            status=status,
            checks=checks,
            issues=issues,
            memory_session_ids=(
                memory_session_ids
            ),
            research_urls=(
                research_urls
            ),
        )

        context = get_run_context()

        if context is not None:
            context.trace.record(
                component=self.AGENT_NAME,
                action="verify",
                status=(
                    "success"
                    if passed
                    else "rejected"
                ),
                detail={
                    "verification_status":
                        status,
                    "memory_sessions":
                        len(
                            memory_session_ids
                        ),
                    "research_urls":
                        len(
                            research_urls
                        ),
                    "issues":
                        len(issues),
                },
            )

        return result
