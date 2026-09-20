import asyncio

from app.agents.memory_agent import MemoryAgent
from app.db.session import (
    AsyncSessionFactory,
)


async def main():
    async with AsyncSessionFactory() as db:

        agent = MemoryAgent(db)

        queries = [
            # 应该能找到 Agent Memory
            (
                "我之前研究 Agent "
                "长期记忆的时候主要看了什么？"
            ),

            # 当前 Demo 数据里没有 Kubernetes
            # 用来测试 Evidence不足时是否拒答。
            (
                "我之前有没有研究过 "
                "Kubernetes 网络策略？"
            ),
        ]

        for query in queries:

            print(
                "\n"
                "================================"
            )

            print(
                "USER:",
                query,
            )

            print(
                "================================"
            )

            result = await agent.run(
                query
            )

            print(
                "\nANSWER:"
            )

            print(
                result.answer
            )

            print(
                "\nSEARCH QUERY:"
            )

            print(
                result.search_query
            )

            print(
                "\nRETRIEVAL ROUNDS:",
                result.retrieval_rounds,
            )

            print(
                "\nABSTAINED:",
                result.abstained,
            )

            print(
                "\nSOURCES:"
            )

            if not result.sources:
                print(
                    "No sources."
                )

            for source in result.sources:
                print(
                    "-",
                    source.session_title,
                    "|",
                    source.locator,
                )


if __name__ == "__main__":
    asyncio.run(main())