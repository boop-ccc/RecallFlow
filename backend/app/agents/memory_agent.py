from typing import TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient
from app.llm.errors import (
    LLMTransientError,
)
from app.runtime.context import (
    get_run_context,
)
from app.runtime.tool_registry import (
    RegisteredTool,
    ToolRegistry,
)
from app.schemas.agent import (
    MemoryAgentResponse,
    MemoryAnswerDraft,
    MemoryEvidenceGrade,
    MemorySearchHit,
    MemorySource,
)
from app.services.memory_search_service import (
    MemorySearchService,
)
from app.tools.memory_tools import (
    SearchMemoryTool,
)


class MemoryAgentState(TypedDict):
    user_query: str
    search_query: str

    rewrite_count: int
    max_rewrites: int

    hits: list[MemorySearchHit]

    grade: MemoryEvidenceGrade | None

    answer: str

    used_session_ids: list[str]

    abstained: bool


GRADE_SYSTEM_PROMPT = """
You are the retrieval grader of a personal memory agent.

Your job is to decide whether the retrieved historical evidence
is sufficient to answer the user's question.

You must NOT answer the user's question.

Return ONLY valid JSON:

{
  "is_sufficient": true,
  "reason": "short Chinese explanation",
  "rewrite_query": null
}

If evidence is insufficient, return:

{
  "is_sufficient": false,
  "reason": "short Chinese explanation",
  "rewrite_query": "a better search query"
}

Rules:

1. Only judge based on the provided evidence.
2. Do not assume missing facts.
3. rewrite_query should be concise and useful for retrieval.
4. If evidence clearly supports the answer,
   is_sufficient must be true.
""".strip()


ANSWER_SYSTEM_PROMPT = """
You are the Memory Agent of RecallFlow.

Answer the user's question ONLY from the retrieved historical evidence.

Return ONLY valid JSON:

{
  "answer": "Chinese answer",
  "used_session_ids": ["session-id"]
}

Rules:

1. Do not invent facts.
2. Only use information contained in the evidence.
3. If multiple sessions are relevant, you may use multiple session IDs.
4. The answer should be concise but useful.
5. used_session_ids must only contain IDs present in the evidence.
""".strip()


class MemoryAgent:
    """
    Memory Agent = 私人历史记忆 Agent。

    LangGraph：

    Retrieve
      ↓
    Grade
      ↓
    Enough? ── No ──> Rewrite ──> Retrieve
      │
     Yes
      ↓
    Answer

    Runtime 负责限制：
    - Step
    - Tool Call
    - Retrieval
    - LLM Call
    """

    AGENT_NAME = "memory_agent"

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db
        self.llm = LLMClient()

        search_service = (
            MemorySearchService(db)
        )

        self.search_tool = (
            SearchMemoryTool(
                search_service
            )
        )

        # ---------------------------------
        # Tool Registry
        # ---------------------------------
        #
        # Memory Agent 不再直接调用 Tool，
        # 而是通过 Runtime 的统一入口。
        # ---------------------------------

        self.tools = ToolRegistry()

        self.tools.register(
            RegisteredTool(
                name=(
                    self.search_tool.name
                ),
                handler=(
                    self.search_tool.run
                ),
                description=(
                    self.search_tool
                    .description
                ),
                timeout_seconds=20,
                retrieval=True,
            )
        )

        self.graph = self._build_graph()

    def _build_graph(
        self,
    ):
        builder = StateGraph(
            MemoryAgentState
        )

        builder.add_node(
            "retrieve",
            self._retrieve_node,
        )

        builder.add_node(
            "grade",
            self._grade_node,
        )

        builder.add_node(
            "rewrite",
            self._rewrite_node,
        )

        builder.add_node(
            "answer",
            self._answer_node,
        )

        builder.add_edge(
            START,
            "retrieve",
        )

        builder.add_edge(
            "retrieve",
            "grade",
        )

        builder.add_conditional_edges(
            "grade",
            self._route_after_grade,
            {
                "rewrite": "rewrite",
                "answer": "answer",
            },
        )

        builder.add_edge(
            "rewrite",
            "retrieve",
        )

        builder.add_edge(
            "answer",
            END,
        )

        return builder.compile()

    def _start_step(
        self,
        action: str,
    ) -> None:
        """
        统一记录 Agent Node Step。
        """

        context = get_run_context()

        if context is None:
            return

        context.budget.consume_step()

        context.trace.record(
            component=self.AGENT_NAME,
            action=f"node:{action}",
            status="started",
            detail={
                "step":
                    context.budget.steps,
            },
        )

    async def _retrieve_node(
        self,
        state: MemoryAgentState,
    ) -> dict:
        self._start_step(
            "retrieve"
        )

        hits = await self.tools.execute(
            agent_name=self.AGENT_NAME,
            tool_name="search_memory",
            query=state["search_query"],
            top_k=3,
        )

        return {
            "hits": hits,
        }

    async def _grade_node(
        self,
        state: MemoryAgentState,
    ) -> dict:
        self._start_step(
            "grade"
        )

        hits = state["hits"]

        if not hits:
            return {
                "grade":
                    MemoryEvidenceGrade(
                        is_sufficient=False,
                        reason=(
                            "没有检索到历史工作记录。"
                        ),
                        rewrite_query=None,
                    )
            }

        evidence_text = (
            self._format_hits(
                hits
            )
        )

        user_prompt = f"""
User Question:
{state["user_query"]}

Current Search Query:
{state["search_query"]}

Retrieved Historical Evidence:
{evidence_text}
""".strip()

        try:
            raw_result = (
                await self.llm.generate_json(
                    system_prompt=(
                        GRADE_SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        user_prompt
                    ),
                )
            )

        except LLMTransientError:
            # --------------------------------
            # Graceful Degradation
            # --------------------------------
            #
            # Provider 临时不可用时，
            # 不允许模型“跳过证据评估后继续编答案”。
            # 直接进入安全拒答路径。
            # --------------------------------

            context = get_run_context()

            if context is not None:
                context.trace.record(
                    component=self.AGENT_NAME,
                    action="fallback:grade",
                    status="degraded",
                    detail={
                        "reason":
                            "llm_transient_error"
                    },
                )

            return {
                "grade":
                    MemoryEvidenceGrade(
                        is_sufficient=False,
                        reason=(
                            "模型服务暂时不可用，"
                            "无法完成语义证据评估。"
                        ),
                        rewrite_query=None,
                    )
            }

        try:
            grade = (
                MemoryEvidenceGrade
                .model_validate(
                    raw_result
                )
            )

        except ValidationError as exc:
            raise ValueError(
                "Memory Agent grader returned "
                "invalid structured output"
            ) from exc

        return {
            "grade": grade,
        }

    def _route_after_grade(
        self,
        state: MemoryAgentState,
    ) -> str:
        grade = state["grade"]

        if grade is None:
            return "answer"

        if grade.is_sufficient:
            return "answer"

        if (
            state["rewrite_count"]
            < state["max_rewrites"]
            and grade.rewrite_query
        ):
            return "rewrite"

        return "answer"

    async def _rewrite_node(
        self,
        state: MemoryAgentState,
    ) -> dict:
        self._start_step(
            "rewrite"
        )

        grade = state["grade"]

        if (
            grade is None
            or not grade.rewrite_query
        ):
            return {}

        return {
            "search_query":
                grade.rewrite_query,
            "rewrite_count":
                state["rewrite_count"] + 1,
        }

    async def _answer_node(
        self,
        state: MemoryAgentState,
    ) -> dict:
        self._start_step(
            "answer"
        )

        grade = state["grade"]
        hits = state["hits"]

        if (
            not hits
            or grade is None
            or not grade.is_sufficient
        ):
            return {
                "answer": (
                    "根据当前检索到的历史工作记录，"
                    "没有足够证据回答这个问题。"
                ),
                "used_session_ids": [],
                "abstained": True,
            }

        evidence_text = (
            self._format_hits(
                hits
            )
        )

        user_prompt = f"""
User Question:
{state["user_query"]}

Historical Evidence:
{evidence_text}
""".strip()

        try:
            raw_result = (
                await self.llm.generate_json(
                    system_prompt=(
                        ANSWER_SYSTEM_PROMPT
                    ),
                    user_prompt=user_prompt,
                )
            )

        except LLMTransientError:
            # --------------------------------
            # Graceful Degradation
            # --------------------------------
            #
            # 证据已经通过 Grade，
            # 只是最终生成模型暂时不可用。
            #
            # 不让整个 Run 崩溃，
            # 返回“证据级恢复结果”。
            # --------------------------------

            used_session_ids = [
                hit.session_id
                for hit in hits[:3]
            ]

            summary_lines = []

            for hit in hits[:3]:
                summary = (
                    hit.summary
                    or hit.evidence_text[:180]
                )

                summary_lines.append(
                    f"- {hit.title}："
                    f"{summary}"
                )

            fallback_answer = (
                "模型服务当前暂时受限，"
                "但 RecallFlow 已成功恢复到"
                "以下相关历史工作记录：\n"
                + "\n".join(
                    summary_lines
                )
                + "\n可稍后重试生成完整总结。"
            )

            context = get_run_context()

            if context is not None:
                context.trace.record(
                    component=self.AGENT_NAME,
                    action="fallback:answer",
                    status="degraded",
                    detail={
                        "reason":
                            "llm_transient_error",
                        "evidence_count":
                            len(hits),
                    },
                )

            return {
                "answer":
                    fallback_answer,
                "used_session_ids":
                    used_session_ids,
                "abstained":
                    False,
            }

        try:
            draft = (
                MemoryAnswerDraft
                .model_validate(
                    raw_result
                )
            )

        except ValidationError as exc:
            raise ValueError(
                "Memory Agent answer returned "
                "invalid structured output"
            ) from exc

        valid_session_ids = {
            hit.session_id
            for hit in hits
        }

        used_session_ids = [
            session_id
            for session_id
            in draft.used_session_ids
            if session_id
            in valid_session_ids
        ]

        return {
            "answer":
                draft.answer,
            "used_session_ids":
                used_session_ids,
            "abstained":
                False,
        }

    @staticmethod
    def _format_hits(
        hits: list[MemorySearchHit],
    ) -> str:
        sections = []

        for rank, hit in enumerate(
            hits,
            start=1,
        ):
            keywords = ", ".join(
                hit.keywords
            )

            section = f"""
[Memory {rank}]

Session ID:
{hit.session_id}

Title:
{hit.title}

Summary:
{hit.summary or "No summary"}

Keywords:
{keywords}

Time:
{hit.started_at} -> {hit.ended_at}

Evidence:
{hit.evidence_text}
""".strip()

            sections.append(section)

        return "\n\n".join(
            sections
        )

    async def run(
        self,
        user_query: str,
    ) -> MemoryAgentResponse:
        initial_state: MemoryAgentState = {
            "user_query":
                user_query,
            "search_query":
                user_query,
            "rewrite_count":
                0,
            "max_rewrites":
                1,
            "hits":
                [],
            "grade":
                None,
            "answer":
                "",
            "used_session_ids":
                [],
            "abstained":
                False,
        }

        final_state = (
            await self.graph.ainvoke(
                initial_state
            )
        )

        used_ids = set(
            final_state[
                "used_session_ids"
            ]
        )

        sources: list[
            MemorySource
        ] = []

        seen_sources: set[
            tuple[str, str]
        ] = set()

        for hit in final_state[
            "hits"
        ]:
            if (
                used_ids
                and hit.session_id
                not in used_ids
            ):
                continue

            for source in hit.sources:
                key = (
                    source.session_id,
                    source.locator,
                )

                if key in seen_sources:
                    continue

                seen_sources.add(
                    key
                )

                sources.append(
                    source
                )

        return MemoryAgentResponse(
            answer=(
                final_state["answer"]
            ),
            sources=(
                []
                if final_state[
                    "abstained"
                ]
                else sources
            ),
            search_query=(
                final_state[
                    "search_query"
                ]
            ),
            retrieval_rounds=(
                final_state[
                    "rewrite_count"
                ]
                + 1
            ),
            abstained=(
                final_state[
                    "abstained"
                ]
            ),
        )
