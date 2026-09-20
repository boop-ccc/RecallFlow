from typing import TypedDict
from urllib.parse import urlparse

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
from app.memory.session_memory import (
    format_time,
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
    is_recent_memory_query,
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


RECENT_ANSWER_SYSTEM_PROMPT = """
You are the recent-work recovery component of RecallFlow.

The user is asking about what they did just now or very recently.

You MUST answer ONLY from the provided Recent Historical Evidence.
Do not use older WorkSession summaries.
Do not invent research goals, conclusions, failures, or unfinished tasks
that are not directly supported by the recent evidence.

Return ONLY valid JSON:

{
  "answer": "Chinese answer",
  "used_session_ids": ["session-id"]
}

Answer requirements:

1. Use Chinese.
2. Start with a concise overall summary of the user's recent activity.
3. Then give 2-4 useful points about what was viewed, revisited,
   or focused on recently.
4. If page content clearly reveals the topic, summarize that topic briefly.
5. If evidence only proves page visits, say "查看/访问/多次打开";
   do NOT claim a deeper research conclusion.
6. Do not repeat an old whole-day or whole-session summary.
7. used_session_ids must only contain IDs present in the evidence.
""".strip()


class MemoryAgent:
    """
    Memory Agent = 私人历史记忆 Agent。

    普通历史问题：

    Retrieve
      ↓
    Grade
      ↓
    Evidence Enough?
      ↓
    Rewrite / Answer

    “刚才”类问题：

    Recent Activity Retrieval
      ↓
    Recent Summary
      ↓
    Deterministic Timeline / Fallback

    即：

    时间明确的问题
    尽量使用确定性程序解决，

    语义模糊的问题
    再交给 LLM。
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

        # -----------------------------
        # Tool Registry
        # -----------------------------
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
            # 普通历史问题的降级路径。
            #
            # 模型生成暂时不可用，
            # 仍然返回已检索到的证据摘要。
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
                "但 RecallFlow 已恢复到"
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

    @staticmethod
    def _source_label(
        source: MemorySource,
    ) -> str:
        """
        给最近 Activity 生成人能看懂的名称。
        """

        if source.title:
            return source.title

        locator = source.locator or ""

        # arXiv PDF 没有网页标题时，
        # 从 URL 中提取论文编号。
        marker = "arxiv.org/pdf/"

        if marker in locator:

            paper_id = (
                locator
                .split(marker, 1)[1]
                .split("?", 1)[0]
                .removesuffix(".pdf")
            )

            return (
                f"arXiv 论文 {paper_id}"
            )

        parsed = urlparse(locator)

        if parsed.netloc:
            return parsed.netloc

        return locator or "未命名页面"

    @staticmethod
    def _dedupe_sources(
        sources: list[MemorySource],
    ) -> list[MemorySource]:
        """
        API Sources 不重复展示同一个页面。
        """

        result: list[
            MemorySource
        ] = []

        seen: set[
            tuple[str, str]
        ] = set()

        for source in sources:

            key = (
                source.session_id,
                source.locator,
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(source)

        return result

    def _build_recent_timeline(
        self,
        hits: list[MemorySearchHit],
    ) -> str:
        """
        根据最近 Activity 生成确定性时间线。

        这部分完全不依赖 LLM，
        用于：
        1. 正常回答中的可核对时间线；
        2. LLM 429 / timeout / 输出异常时的 fallback。
        """

        sources: list[
            MemorySource
        ] = []

        for hit in hits:
            sources.extend(
                hit.sources
            )

        if not sources:
            return ""

        # 最新行为优先。
        sources.sort(
            key=lambda source:
                source.observed_at,
            reverse=True,
        )

        # 相同页面合并访问时间。
        grouped: dict[
            str,
            dict,
        ] = {}

        order: list[str] = []

        for source in sources:

            key = source.locator

            if key not in grouped:

                grouped[key] = {
                    "label":
                        self._source_label(
                            source
                        ),
                    "times": [],
                }

                order.append(key)

            local_time = (
                format_time(
                    source.observed_at
                )
                .split(" ")[-1]
            )

            if (
                local_time
                not in grouped[key]["times"]
            ):
                grouped[key][
                    "times"
                ].append(
                    local_time
                )

        lines = []

        for key in order:

            data = grouped[key]

            # 同一页面内部按时间从早到晚展示。
            times = sorted(
                data["times"]
            )

            lines.append(
                "- "
                + "、".join(times)
                + "："
                + data["label"]
            )

        return "\n".join(lines)

    def _build_recent_answer(
        self,
        hits: list[MemorySearchHit],
    ) -> str:
        """
        Recent 查询的确定性 fallback。
        """

        timeline = (
            self._build_recent_timeline(
                hits
            )
        )

        if not timeline:
            return (
                "暂时没有找到最近的浏览活动。"
            )

        return (
            "你刚才主要有这些浏览/研究活动：\n"
            + timeline
        )

    async def _run_recent_query(
        self,
        user_query: str,
    ) -> MemoryAgentResponse:
        """
        “刚才”专用 Fast Path。

        流程：

        Recent Activity Retrieval
            ↓
        只拿最近 30 分钟证据
            ↓
        LLM 生成更有信息量的 Recent Summary
            ↓
        追加确定性时间线

        如果 LLM 429 / timeout / 输出异常：
            ↓
        自动退化为确定性时间线

        注意：
        不经过普通 WorkSession Hybrid Retrieval，
        也不会使用旧的整段 Session Summary。
        """

        self._start_step(
            "recent_activity"
        )

        hits = await self.tools.execute(
            agent_name=self.AGENT_NAME,
            tool_name="search_memory",
            query=user_query,
            top_k=1,
        )

        if not hits:

            return MemoryAgentResponse(
                answer=(
                    "暂时没有找到最近的工作记录。"
                ),
                sources=[],
                search_query=(
                    user_query
                ),
                retrieval_rounds=1,
                abstained=True,
            )

        all_sources: list[
            MemorySource
        ] = []

        for hit in hits:
            all_sources.extend(
                hit.sources
            )

        sources = (
            self._dedupe_sources(
                all_sources
            )
        )

        timeline = (
            self._build_recent_timeline(
                hits
            )
        )

        fallback_answer = (
            self._build_recent_answer(
                hits
            )
        )

        evidence_text = (
            self._format_hits(
                hits
            )
        )

        user_prompt = f"""
User Question:
{user_query}

Recent Historical Evidence:
{evidence_text}

Deterministic Recent Timeline:
{timeline}
""".strip()

        answer = fallback_answer
        llm_used = False
        degraded_reason = None

        try:
            raw_result = (
                await self.llm.generate_json(
                    system_prompt=(
                        RECENT_ANSWER_SYSTEM_PROMPT
                    ),
                    user_prompt=user_prompt,
                )
            )

            draft = (
                MemoryAnswerDraft
                .model_validate(
                    raw_result
                )
            )

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

            # 模型若没有返回合法 Session ID，
            # 不影响回答；Recent Evidence 本身已经确定。
            if not used_session_ids:
                used_session_ids = [
                    hit.session_id
                    for hit in hits
                ]

            semantic_answer = (
                draft.answer.strip()
            )

            if semantic_answer:

                answer = (
                    semantic_answer
                    + "\n\n最近活动时间线：\n"
                    + timeline
                )

                llm_used = True

        except LLMTransientError:
            degraded_reason = (
                "llm_transient_error"
            )

        except (ValidationError, ValueError):
            degraded_reason = (
                "invalid_llm_output"
            )

        context = get_run_context()

        if context is not None:

            context.trace.record(
                component=self.AGENT_NAME,
                action=(
                    "recent_activity_answer"
                ),
                status=(
                    "success"
                    if llm_used
                    else "degraded"
                ),
                detail={
                    "evidence_count":
                        len(all_sources),
                    "llm_used":
                        llm_used,
                    "fallback_used":
                        not llm_used,
                    "reason":
                        degraded_reason,
                },
            )

        return MemoryAgentResponse(
            answer=answer,
            sources=sources,
            search_query=user_query,
            retrieval_rounds=1,
            abstained=False,
        )

    async def run(
        self,
        user_query: str,
    ) -> MemoryAgentResponse:

        # =================================
        # Recent Activity Fast Path
        #
        # “刚才做了什么？”
        # 不需要让 LLM 猜时间。
        # =================================
        if is_recent_memory_query(
            user_query
        ):
            return (
                await self._run_recent_query(
                    user_query
                )
            )

        # =================================
        # 普通历史问题
        # 继续使用原来的 LangGraph Agent
        # =================================
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
                final_state[
                    "answer"
                ]
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