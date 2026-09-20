import asyncio
from typing import TypedDict

from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from pydantic import ValidationError

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
from app.schemas.research import (
    ResearchAgentResponse,
    ResearchAnswerDraft,
    ResearchEvidenceGrade,
    WebPageEvidence,
    WebSearchResult,
)
from app.tools.research_tools import (
    FetchPageTool,
    WebSearchTool,
)


class ResearchAgentState(TypedDict):
    user_query: str
    search_query: str

    rewrite_count: int
    max_rewrites: int

    search_results: list[
        WebSearchResult
    ]

    evidence: list[
        WebPageEvidence
    ]

    grade: (
        ResearchEvidenceGrade
        | None
    )

    answer: str

    used_urls: list[str]

    abstained: bool


GRADE_SYSTEM_PROMPT = """
你是 RecallFlow Research Agent 的证据评估器。

你的任务不是回答用户问题。

你的任务是判断当前公开互联网证据，
是否足够支持回答用户的问题。

必须只根据提供的 Evidence 判断。

只返回合法 JSON：

{
  "is_sufficient": true,
  "reason": "中文原因",
  "rewrite_query": null
}

如果证据不足：

{
  "is_sufficient": false,
  "reason": "中文原因",
  "rewrite_query": "更适合 Web Search 的搜索词"
}

规则：

1. reason 必须使用中文。
2. 不允许假设 Evidence 中不存在的信息。
3. rewrite_query 应简短、明确。
4. 如果 Evidence 与用户问题明显无关，应判定不足。
""".strip()


ANSWER_SYSTEM_PROMPT = """
你是 RecallFlow 的 Research Agent。

你的任务是根据公开互联网 Evidence，
回答用户关于当前外部信息的问题。

只允许使用提供的 Evidence。

只返回合法 JSON：

{
  "answer": "中文回答",
  "used_urls": [
    "https://example.com"
  ]
}

规则：

1. answer 必须使用中文。
2. 技术名词可以保留英文。
3. 不允许编造 Evidence 中没有的事实。
4. used_urls 只能包含 Evidence 中真实存在的 URL。
5. 如果多个来源共同支持结论，可以使用多个 URL。
6. 回答应简洁、清晰。
""".strip()


class ResearchAgent:
    """
    Research Agent = 公共外部研究 Agent。

    Search
      ↓
    Fetch
      ↓
    Grade
      ↓
    Enough? ── No ──> Rewrite ──> Search
      │
     Yes
      ↓
    Answer
    """

    AGENT_NAME = (
        "research_agent"
    )

    def __init__(
        self,
    ):
        self.llm = LLMClient()

        self.search_tool = (
            WebSearchTool()
        )

        self.fetch_tool = (
            FetchPageTool()
        )

        self.tools = ToolRegistry()

        self.tools.register(
            RegisteredTool(
                name="web_search",
                handler=(
                    self.search_tool.run
                ),
                description=(
                    self.search_tool
                    .description
                ),
                timeout_seconds=15,
                retrieval=True,
            )
        )

        self.tools.register(
            RegisteredTool(
                name="fetch_page",
                handler=(
                    self.fetch_tool.run
                ),
                description=(
                    self.fetch_tool
                    .description
                ),
                timeout_seconds=15,
                retrieval=False,
            )
        )

        self.graph = self._build_graph()

    def _build_graph(
        self,
    ):
        builder = StateGraph(
            ResearchAgentState
        )

        builder.add_node(
            "search",
            self._search_node,
        )

        builder.add_node(
            "fetch",
            self._fetch_node,
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
            "search",
        )

        builder.add_edge(
            "search",
            "fetch",
        )

        builder.add_edge(
            "fetch",
            "grade",
        )

        builder.add_conditional_edges(
            "grade",
            self._route_after_grade,
            {
                "rewrite":
                    "rewrite",
                "answer":
                    "answer",
            },
        )

        builder.add_edge(
            "rewrite",
            "search",
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

    async def _search_node(
        self,
        state: ResearchAgentState,
    ) -> dict:
        self._start_step(
            "search"
        )

        results = await self.tools.execute(
            agent_name=self.AGENT_NAME,
            tool_name="web_search",
            query=(
                state["search_query"]
            ),
            max_results=5,
        )

        return {
            "search_results":
                results,
        }

    async def _fetch_node(
        self,
        state: ResearchAgentState,
    ) -> dict:
        self._start_step(
            "fetch"
        )

        results = (
            state[
                "search_results"
            ][:3]
        )

        if not results:
            return {
                "evidence": [],
            }

        # 每个 fetch_page 都是真实 Tool Call，
        # 所以每一个都经过 ToolRegistry。
        evidence = await asyncio.gather(
            *[
                self.tools.execute(
                    agent_name=(
                        self.AGENT_NAME
                    ),
                    tool_name=(
                        "fetch_page"
                    ),
                    result=result,
                )
                for result in results
            ]
        )

        return {
            "evidence":
                evidence,
        }

    async def _grade_node(
        self,
        state: ResearchAgentState,
    ) -> dict:
        self._start_step(
            "grade"
        )

        evidence = (
            state["evidence"]
        )

        if not evidence:
            return {
                "grade":
                    ResearchEvidenceGrade(
                        is_sufficient=False,
                        reason=(
                            "没有获取到有效的"
                            "公开互联网证据。"
                        ),
                        rewrite_query=None,
                    )
            }

        evidence_text = (
            self._format_evidence(
                evidence
            )
        )

        user_prompt = f"""
用户问题：
{state["user_query"]}

当前搜索词：
{state["search_query"]}

公开互联网 Evidence：
{evidence_text}
""".strip()

        try:
            raw = await (
                self.llm.generate_json(
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
                    ResearchEvidenceGrade(
                        is_sufficient=False,
                        reason=(
                            "模型服务暂时不可用，"
                            "无法完成外部证据评估。"
                        ),
                        rewrite_query=None,
                    )
            }

        try:
            grade = (
                ResearchEvidenceGrade
                .model_validate(raw)
            )

        except ValidationError as exc:
            raise ValueError(
                "Research Grader "
                "返回了错误的结构化输出"
            ) from exc

        return {
            "grade":
                grade,
        }

    def _route_after_grade(
        self,
        state: ResearchAgentState,
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
        state: ResearchAgentState,
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
                state[
                    "rewrite_count"
                ]
                + 1,
        }

    async def _answer_node(
        self,
        state: ResearchAgentState,
    ) -> dict:
        self._start_step(
            "answer"
        )

        grade = state["grade"]
        evidence = (
            state["evidence"]
        )

        if (
            not evidence
            or grade is None
            or not grade.is_sufficient
        ):
            return {
                "answer": (
                    "当前公开互联网证据不足，"
                    "无法可靠回答这个问题。"
                ),
                "used_urls": [],
                "abstained": True,
            }

        evidence_text = (
            self._format_evidence(
                evidence
            )
        )

        user_prompt = f"""
用户问题：
{state["user_query"]}

公开互联网 Evidence：
{evidence_text}
""".strip()

        try:
            raw = await (
                self.llm.generate_json(
                    system_prompt=(
                        ANSWER_SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        user_prompt
                    ),
                )
            )

        except LLMTransientError:
            used_urls = [
                item.url
                for item in evidence[:3]
            ]

            source_lines = [
                (
                    f"- {item.title}: "
                    f"{item.url}"
                )
                for item in evidence[:3]
            ]

            fallback_answer = (
                "模型服务当前暂时受限，"
                "但已完成公开资料检索。"
                "以下来源可以用于继续研究：\n"
                + "\n".join(
                    source_lines
                )
                + "\n可稍后重试生成完整综合回答。"
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
                            len(evidence),
                    },
                )

            return {
                "answer":
                    fallback_answer,
                "used_urls":
                    used_urls,
                "abstained":
                    False,
            }

        try:
            draft = (
                ResearchAnswerDraft
                .model_validate(raw)
            )

        except ValidationError as exc:
            raise ValueError(
                "Research Agent "
                "返回了错误的结构化输出"
            ) from exc

        valid_urls = {
            item.url
            for item in evidence
        }

        used_urls = [
            url
            for url
            in draft.used_urls
            if url in valid_urls
        ]

        return {
            "answer":
                draft.answer,
            "used_urls":
                used_urls,
            "abstained":
                False,
        }

    @staticmethod
    def _format_evidence(
        evidence: list[
            WebPageEvidence
        ],
    ) -> str:
        sections = []

        for index, item in enumerate(
            evidence,
            start=1,
        ):
            content = (
                item.content
                or item.snippet
            )

            section = f"""
[External Source {index}]

Title:
{item.title}

URL:
{item.url}

Search Snippet:
{item.snippet}

Page Content:
{content[:6000]}
""".strip()

            sections.append(section)

        return "\n\n".join(
            sections
        )

    async def run(
        self,
        user_query: str,
    ) -> ResearchAgentResponse:
        initial_state: (
            ResearchAgentState
        ) = {
            "user_query":
                user_query,
            "search_query":
                user_query,
            "rewrite_count":
                0,
            "max_rewrites":
                1,
            "search_results":
                [],
            "evidence":
                [],
            "grade":
                None,
            "answer":
                "",
            "used_urls":
                [],
            "abstained":
                False,
        }

        final_state = (
            await self.graph.ainvoke(
                initial_state
            )
        )

        used_urls = set(
            final_state[
                "used_urls"
            ]
        )

        sources = []

        for item in final_state[
            "evidence"
        ]:
            if (
                used_urls
                and item.url
                not in used_urls
            ):
                continue

            sources.append(item)

        return ResearchAgentResponse(
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
            search_rounds=(
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
