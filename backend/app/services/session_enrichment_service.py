from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.db.models.work_session import WorkSession
from app.llm.client import LLMClient
from app.memory.session_memory import SessionMemoryService
from app.schemas.memory import WorkSessionEnrichment


SYSTEM_PROMPT = """
You are the semantic analysis component of RecallFlow.

Your job is to analyze ONE user's WorkSession.

You MUST only use the provided evidence.
Do not invent facts or unfinished tasks.

Return ONLY valid JSON in this format:

{
  "title": "short Chinese title",
  "summary": "short Chinese summary",
  "keywords": ["keyword1", "keyword2"],
  "open_tasks": ["task1"]
}

Rules:
1. title and summary should be Chinese.
2. keywords may contain English technical terms.
3. open_tasks must only contain tasks clearly supported by evidence.
4. If there is no evidence of unfinished tasks, return [].
5. keywords must contain no more than 8 items.
6. open_tasks must contain no more than 5 items.
"""


class SessionEnrichmentService:
    """
    Semantic Enrichment = 语义增强

    原始 WorkSession
    ↓
    Evidence
    ↓
    LLM
    ↓
    title / summary / keywords / open_tasks
    """

    def __init__(self, db: AsyncSession):
        self.db = db

        self.memory = SessionMemoryService(db)
        self.llm = LLMClient()

    async def enrich(
        self,
        session_id: str,
    ) -> WorkSessionEnrichment:

        # 1. 构造有证据来源的 Context
        context = await self.memory.build_context(
            session_id
        )

        if context is None:
            raise ValueError(
                "WorkSession does not exist"
            )

        prompt_text = (
            self.memory.to_prompt_text(context)
        )

        # 2. 调用 LLM
        raw_result = await self.llm.generate_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt_text,
        )

        # 3. Structured Output Validation
        # Pydantic 检查模型输出格式。
        try:
            enrichment = (
                WorkSessionEnrichment.model_validate(
                    raw_result
                )
            )

        except ValidationError as exc:
            raise ValueError(
                "LLM returned invalid structured output"
            ) from exc

        # 4. 保存到 WorkSession
        session = await self.db.get(
            WorkSession,
            session_id,
        )

        session.title = enrichment.title
        session.summary = enrichment.summary
        session.keywords = enrichment.keywords
        session.open_tasks = enrichment.open_tasks

        await self.db.commit()

        return enrichment