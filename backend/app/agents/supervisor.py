import asyncio

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.memory_agent import (
    MemoryAgent,
)
from app.agents.research_agent import (
    ResearchAgent,
)
from app.agents.verifier_agent import (
    VerifierAgent,
)
from app.llm.client import (
    LLMClient,
)
from app.llm.errors import (
    LLMTransientError,
)
from app.runtime.context import (
    get_run_context,
)
from app.schemas.supervisor import (
    SupervisorAnswerDraft,
    SupervisorDecision,
    SupervisorResponse,
)


ROUTER_SYSTEM_PROMPT = """
你是 RecallFlow 的 Supervisor Agent。

你的任务是判断用户请求应该交给哪个 Agent。

RecallFlow 有两个专业 Agent：

1. Memory Agent
   负责用户的私人历史工作记忆。

2. Research Agent
   负责当前公开互联网信息。

3. 如果用户既需要过去的私人工作上下文，
   又需要当前公开互联网信息，
   使用 memory_and_research。

只返回合法 JSON：

{
  "route": "memory_only",
  "reason": "中文原因"
}

route 只能是：

memory_only
research_only
memory_and_research

规则：

1. reason 必须使用中文。
2. 不要回答用户问题，只负责路由。
3. “之前、昨天、上次、我的历史”等通常需要 Memory Agent。
4. “现在、最新、当前、外部资料”等通常需要 Research Agent。
5. 同时出现历史恢复和当前研究需求时，
   使用 memory_and_research。
""".strip()


SYNTHESIS_SYSTEM_PROMPT = """
你是 RecallFlow 的结果汇总组件。

你会收到：

1. Memory Agent 的历史记忆结果
2. Research Agent 的当前公开研究结果

请将两部分合并成一个清晰的中文回答。

只返回合法 JSON：

{
  "answer": "中文回答"
}

规则：

1. 不允许添加两个 Agent 都没有提供的新事实。
2. 明确区分用户过去的工作和当前公开信息。
3. 技术名词可以保留英文。
4. 回答应简洁、清楚。
""".strip()


class SupervisorAgent:
    """
    Supervisor = 多 Agent 调度层。

    负责：
    - Routing
    - Sub-Agent Dispatch
    - Parallel Execution
    - Result Aggregation

    不负责：
    - Memory Retrieval 的具体实现
    - Web Search 的具体实现
    """

    AGENT_NAME = "supervisor"

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.llm = LLMClient()

        self.memory_agent = (
            MemoryAgent(db)
        )

        self.research_agent = (
            ResearchAgent()
        )

        self.verifier_agent = (
            VerifierAgent()
        )

    @staticmethod
    def _rule_based_route(
        user_query: str,
    ) -> SupervisorDecision | None:
        """
        High-confidence Intent：
        优先确定性路由。

        模糊请求才交给 LLM Router。

        这叫 Hybrid Routing。
        """

        query = (
            user_query
            .strip()
            .lower()
        )

        memory_hints = (
            "之前",
            "以前",
            "昨天",
            "上次",
            "过去",
            "历史",
            "我看过",
            "我研究过",
            "我之前",
            "做到哪里",
            "继续之前",
            "接着上次",
        )

        research_hints = (
            "现在",
            "当前",
            "最新",
            "目前",
            "最近",
            "新的方案",
            "有没有新的",
            "公开资料",
            "外部资料",
            "互联网",
            "网上查",
            "搜索一下",
        )

        has_memory = any(
            hint in query
            for hint in memory_hints
        )

        has_research = any(
            hint in query
            for hint in research_hints
        )

        if (
            has_memory
            and has_research
        ):
            return SupervisorDecision(
                route=(
                    "memory_and_research"
                ),
                reason=(
                    "规则路由：请求同时包含"
                    "历史恢复和当前研究需求。"
                ),
            )

        if has_memory:
            return SupervisorDecision(
                route="memory_only",
                reason=(
                    "规则路由：请求明确涉及"
                    "用户过去的工作历史。"
                ),
            )

        if has_research:
            return SupervisorDecision(
                route="research_only",
                reason=(
                    "规则路由：请求明确涉及"
                    "当前公开信息。"
                ),
            )

        return None

    def _start_step(
        self,
        action: str,
    ) -> None:
        context = get_run_context()

        if context is None:
            return

        context.budget.consume_step()

        context.trace.record(
            component=self.AGENT_NAME,
            action=f"step:{action}",
            status="started",
            detail={
                "step":
                    context.budget.steps,
            },
        )

    async def _decide_route(
        self,
        user_query: str,
    ) -> SupervisorDecision:
        self._start_step(
            "route"
        )

        rule_decision = (
            self._rule_based_route(
                user_query
            )
        )

        context = get_run_context()

        if rule_decision is not None:
            if context is not None:
                context.route = (
                    rule_decision.route
                )

                context.trace.record(
                    component=self.AGENT_NAME,
                    action="route",
                    status="success",
                    detail={
                        "source":
                            "deterministic_rule",
                        "route":
                            rule_decision.route,
                    },
                )

            return rule_decision

        raw = await self.llm.generate_json(
            system_prompt=(
                ROUTER_SYSTEM_PROMPT
            ),
            user_prompt=user_query,
        )

        try:
            decision = (
                SupervisorDecision
                .model_validate(raw)
            )

        except ValidationError as exc:
            raise ValueError(
                "Supervisor 返回了"
                "错误的路由结构"
            ) from exc

        if context is not None:
            context.route = (
                decision.route
            )

            context.trace.record(
                component=self.AGENT_NAME,
                action="route",
                status="success",
                detail={
                    "source":
                        "llm_router",
                    "route":
                        decision.route,
                },
            )

        return decision

    async def _run_memory(
        self,
        user_query: str,
    ):
        context = get_run_context()

        if context is not None:
            context.budget.consume_subagent()

            context.trace.record(
                component=self.AGENT_NAME,
                action=(
                    "dispatch:memory_agent"
                ),
                status="started",
            )

        return await (
            self.memory_agent.run(
                user_query
            )
        )

    async def _run_research(
        self,
        user_query: str,
    ):
        context = get_run_context()

        if context is not None:
            context.budget.consume_subagent()

            context.trace.record(
                component=self.AGENT_NAME,
                action=(
                    "dispatch:research_agent"
                ),
                status="started",
            )

        return await (
            self.research_agent.run(
                user_query
            )
        )

    async def _synthesize(
        self,
        *,
        user_query: str,
        memory_answer: str,
        research_answer: str,
    ) -> str:
        self._start_step(
            "synthesize"
        )

        user_prompt = f"""
用户原始问题：

{user_query}


====================
Memory Agent
用户历史工作结果：
====================

{memory_answer}


====================
Research Agent
当前公开研究结果：
====================

{research_answer}
""".strip()

        try:
            raw = await (
                self.llm.generate_json(
                    system_prompt=(
                        SYNTHESIS_SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        user_prompt
                    ),
                )
            )

        except LLMTransientError:
            # 两个专业 Agent 已经有结果，
            # 只有最后的“润色汇总”失败。
            #
            # 这时不应该丢掉全部结果。
            context = get_run_context()

            if context is not None:
                context.trace.record(
                    component=self.AGENT_NAME,
                    action=(
                        "fallback:synthesize"
                    ),
                    status="degraded",
                    detail={
                        "reason":
                            "llm_transient_error"
                    },
                )

            return (
                "【历史工作】\n"
                f"{memory_answer}\n\n"
                "【当前公开研究】\n"
                f"{research_answer}"
            )

        try:
            result = (
                SupervisorAnswerDraft
                .model_validate(raw)
            )

        except ValidationError as exc:
            raise ValueError(
                "Supervisor 汇总结果"
                "格式错误"
            ) from exc

        return result.answer

    async def _run_unverified(
        self,
        user_query: str,
        *,
        routing_query: str | None = None,
    ) -> SupervisorResponse:
        decision = (
            await self._decide_route(
                routing_query
                or user_query
            )
        )

        print(
            "\nSupervisor Route:",
            decision.route,
        )

        print(
            "Route Reason:",
            decision.reason,
        )

        # ----------------------------------
        # Memory Only
        # ----------------------------------

        if (
            decision.route
            == "memory_only"
        ):
            memory_result = (
                await self._run_memory(
                    user_query
                )
            )

            return SupervisorResponse(
                answer=(
                    memory_result.answer
                ),
                route=(
                    decision.route
                ),
                route_reason=(
                    decision.reason
                ),
                agents_used=[
                    "memory_agent"
                ],
                memory_sources=(
                    memory_result.sources
                ),
                research_sources=[],
            )

        # ----------------------------------
        # Research Only
        # ----------------------------------

        if (
            decision.route
            == "research_only"
        ):
            research_result = (
                await self._run_research(
                    user_query
                )
            )

            return SupervisorResponse(
                answer=(
                    research_result.answer
                ),
                route=(
                    decision.route
                ),
                route_reason=(
                    decision.reason
                ),
                agents_used=[
                    "research_agent"
                ],
                memory_sources=[],
                research_sources=(
                    research_result.sources
                ),
            )

        # ----------------------------------
        # Memory + Research
        # ----------------------------------
        #
        # return_exceptions=True：
        # 某一个 Sub-Agent 失败时，
        # 不让另一个成功结果一起丢失。
        # ----------------------------------

        memory_result, research_result = (
            await asyncio.gather(
                self._run_memory(
                    user_query
                ),
                self._run_research(
                    user_query
                ),
                return_exceptions=True,
            )
        )

        memory_failed = isinstance(
            memory_result,
            BaseException,
        )

        research_failed = isinstance(
            research_result,
            BaseException,
        )

        # 两个都失败：
        # 当前任务没有可用结果。
        if (
            memory_failed
            and research_failed
        ):
            raise RuntimeError(
                "Memory Agent 和 "
                "Research Agent 均执行失败。"
            ) from memory_result

        # Memory 失败，Research 成功：
        # Partial Success
        if memory_failed:
            return SupervisorResponse(
                answer=(
                    "历史记忆分支暂时不可用。"
                    "以下为当前公开研究结果：\n\n"
                    f"{research_result.answer}"
                ),
                route=(
                    decision.route
                ),
                route_reason=(
                    decision.reason
                ),
                agents_used=[
                    "research_agent"
                ],
                memory_sources=[],
                research_sources=(
                    research_result.sources
                ),
            )

        # Research 失败，Memory 成功：
        # Partial Success
        if research_failed:
            return SupervisorResponse(
                answer=(
                    f"{memory_result.answer}\n\n"
                    "当前公开研究分支暂时不可用，"
                    "可稍后重试。"
                ),
                route=(
                    decision.route
                ),
                route_reason=(
                    decision.reason
                ),
                agents_used=[
                    "memory_agent"
                ],
                memory_sources=(
                    memory_result.sources
                ),
                research_sources=[],
            )

        final_answer = (
            await self._synthesize(
                user_query=user_query,
                memory_answer=(
                    memory_result.answer
                ),
                research_answer=(
                    research_result.answer
                ),
            )
        )

        return SupervisorResponse(
            answer=(
                final_answer
            ),
            route=(
                decision.route
            ),
            route_reason=(
                decision.reason
            ),
            agents_used=[
                "memory_agent",
                "research_agent",
            ],
            memory_sources=(
                memory_result.sources
            ),
            research_sources=(
                research_result.sources
            ),
        )

    async def _verify_response(
        self,
        response: SupervisorResponse,
    ) -> SupervisorResponse:
        """
        Verifier Agent = 最终证据边界。

        Supervisor 负责生成候选结果；
        Verifier 负责判断：
        “这个结果有没有真实来源支撑？”
        """

        context = get_run_context()

        if context is not None:
            context.budget.consume_subagent()

            context.trace.record(
                component=self.AGENT_NAME,
                action="dispatch:verifier_agent",
                status="started",
            )

        verification = (
            self.verifier_agent.verify(
                answer=response.answer,
                route=response.route,
                agents_used=(
                    response.agents_used
                ),
                memory_sources=(
                    response.memory_sources
                ),
                research_sources=(
                    response.research_sources
                ),
            )
        )

        # Hard Boundary：
        # Verifier 拒绝时，不把原回答继续当成可信答案。
        if not verification.passed:
            safe_answer = (
                "最终回答未通过证据验证，"
                "系统已阻止该结果作为可信答案返回。"
            )

            return response.model_copy(
                update={
                    "answer":
                        safe_answer,
                    "verification":
                        verification,
                }
            )

        return response.model_copy(
            update={
                "verification":
                    verification,
            }
        )

    async def run(
        self,
        user_query: str,
        *,
        routing_query: str | None = None,
    ) -> SupervisorResponse:
        """
        Supervisor 对外正式入口。

        先运行 Multi-Agent 主链路，
        再经过 Verifier Agent，
        最终结果才允许返回。
        """

        response = (
            await self._run_unverified(
                user_query,
                routing_query=(
                    routing_query
                ),
            )
        )

        return await (
            self._verify_response(
                response
            )
        )

