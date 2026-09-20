from app.schemas.agent import MemorySearchHit
from app.services.memory_search_service import (
    MemorySearchService,
)


class SearchMemoryTool:
    """
    Search Memory Tool = 记忆搜索工具。

    Memory Agent 通过这个 Tool
    访问用户历史 WorkSession。
    """

    name = "search_memory"

    description = (
        "Search the user's historical WorkSessions "
        "and return evidence-backed memory results."
    )

    def __init__(
        self,
        service: MemorySearchService,
    ):
        self.service = service

    async def run(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[MemorySearchHit]:
        """
        Tool 的统一执行入口。
        """

        return await self.service.search(
            query=query,
            top_k=top_k,
        )