import asyncio

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS

from app.schemas.research import (
    WebPageEvidence,
    WebSearchResult,
)


class WebSearchTool:
    """
    Web Search Tool = 公共互联网搜索工具。

    Research Agent 专用。

    注意：
    Memory Agent 后面不会拥有这个 Tool。
    """

    name = "web_search"

    description = (
        "Search the public web for current information."
    )

    async def run(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[WebSearchResult]:
        """
        DDGS 本身是同步函数。

        asyncio.to_thread：
        把同步搜索放到线程中执行，
        避免阻塞整个 async Agent Runtime。
        """

        raw_results = await asyncio.to_thread(
            self._search_sync,
            query,
            max_results,
        )

        results: list[WebSearchResult] = []

        for item in raw_results:
            url = item.get("href", "")

            if not url:
                continue

            results.append(
                WebSearchResult(
                    title=(
                        item.get("title")
                        or "Untitled"
                    ),
                    url=url,
                    snippet=(
                        item.get("body")
                        or ""
                    ),
                )
            )

        return results

    @staticmethod
    def _search_sync(
        query: str,
        max_results: int,
    ) -> list[dict]:
        """
        真正执行同步 Web Search。
        """

        try:
            return DDGS(
                timeout=10
            ).text(
                query,
                max_results=max_results,
            )

        except Exception as exc:
            print(
                "Web Search 失败：",
                str(exc),
            )

            return []


class FetchPageTool:
    """
    Fetch Page Tool = 网页正文抓取工具。

    Search 只能得到标题和摘要，
    Fetch Page 再尝试读取真实网页内容。
    """

    name = "fetch_page"

    description = (
        "Fetch readable text from a public web page."
    )

    async def run(
        self,
        result: WebSearchResult,
    ) -> WebPageEvidence:
        """
        抓取网页正文。

        如果网页禁止抓取，
        仍保留 Search Snippet，
        不让整个 Agent 失败。
        """

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "RecallFlowResearchAgent/1.0"
            )
        }

        content = ""

        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(
                    result.url
                )

                response.raise_for_status()

                # 目前只处理 HTML。
                content_type = (
                    response.headers.get(
                        "content-type",
                        ""
                    )
                )

                if "text/html" in content_type:
                    soup = BeautifulSoup(
                        response.text,
                        "html.parser",
                    )

                    # 去掉页面脚本等无关内容
                    for tag in soup(
                        [
                            "script",
                            "style",
                            "nav",
                            "footer",
                            "noscript",
                        ]
                    ):
                        tag.decompose()

                    text = soup.get_text(
                        separator=" ",
                        strip=True,
                    )

                    # Context Control
                    # 上下文控制：
                    # 单网页最多保留 6000 字符。
                    content = text[:6000]

        except Exception as exc:
            # Graceful Degradation = 优雅降级
            #
            # 页面抓取失败，
            # 仍然保留搜索结果摘要。
            print(
                "网页抓取失败：",
                result.url,
                "|",
                str(exc),
            )

        return WebPageEvidence(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            content=content,
        )