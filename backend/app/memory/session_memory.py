from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.memory_repository import MemoryRepository
from app.schemas.memory import EvidenceItem, SessionEvidence
from datetime import timezone
from datetime import timezone, timedelta

CHINA_TZ = timezone(timedelta(hours=8))


def format_time(dt):
    # 数据库里的无时区时间按 UTC 处理
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    # 转北京时间，显示为 24 小时制
    return dt.astimezone(CHINA_TZ).strftime("%Y-%m-%d %H:%M")

class SessionMemoryService:
    """
    Session Memory Service = 工作记忆服务。

    作用：
    把数据库中的 WorkSession / Activity / Resource / Snapshot
    整理成 Agent 和 Retrieval 可以直接使用的内容。
    """

    def __init__(self, db: AsyncSession):
        self.repo = MemoryRepository(db)

    async def build_context(
        self,
        session_id: str,
    ) -> SessionEvidence | None:
        """
        Context = 上下文。

        根据一个 WorkSession，
        构造带真实来源的 Evidence（证据）。
        """

        session = await self.repo.get_session(session_id)

        if session is None:
            return None

        rows = await self.repo.get_session_evidence(session_id)

        items = []

        for row in rows:
            items.append(
                EvidenceItem(
                    activity_id=row.activity_id,
                    observed_at=row.observed_at,
                    resource_id=row.resource_id,
                    locator=row.locator,
                    title=row.title,
                    content_text=row.content_text,
                )
            )

        return SessionEvidence(
            session_id=session.id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            items=items,
        )

    @staticmethod
    def to_prompt_text(
        context: SessionEvidence,
    ) -> str:
        """
        把结构化 Evidence 转换成 LLM 能阅读的文本。

        每条正文最多取 500 字，
        避免把过多无关内容塞进 Prompt。
        """

        lines = [
            f"Session ID: {context.session_id}",
            f"Time: {format_time(context.started_at)} -> {format_time(context.ended_at)}",
            "",
            "Evidence:",
        ]

        for index, item in enumerate(
            context.items,
            start=1,
        ):
            content = (item.content_text or "")[:500]

            lines.append(
                f"""
[{index}]
Title: {item.title or "Unknown"}
Source: {item.locator}
Observed At: {format_time(item.observed_at)}
Content: {content}
""".strip()
            )

        return "\n\n".join(lines)

    async def build_retrieval_text(
        self,
        session_id: str,
    ) -> str | None:
        """
        Retrieval Text = 检索文本。

        把一个 WorkSession 整理成：
        BM25 和 Dense Retrieval 都可以搜索的文本。

        使用：
        title
        summary
        keywords
        原始 evidence
        """

        session = await self.repo.get_session(session_id)

        if session is None:
            return None

        context = await self.build_context(session_id)

        if context is None:
            return None

        parts: list[str] = []

        # LLM Semantic Enrichment
        # LLM 已经生成的语义信息。
        if session.title:
            parts.append(session.title)

        if session.summary:
            parts.append(session.summary)

        if session.keywords:
            parts.append(
                " ".join(session.keywords)
            )

        # 原始 Evidence
        # 保证检索结果仍然基于真实资料。
        for item in context.items:
            if item.title:
                parts.append(item.title)

            if item.content_text:
                parts.append(
                    item.content_text[:500]
                )

        return "\n".join(parts)