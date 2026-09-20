import asyncio

from app.agents.research_agent import (
    ResearchAgent,
)


async def main():
    agent = ResearchAgent()

    queries = [
        (
            "现在 Agent Memory "
            "常见的设计方式有哪些？"
        ),
        (
            "LangGraph 当前有哪些 "
            "Memory 相关能力？"
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
            "\nFINAL SEARCH QUERY:"
        )

        print(
            result.search_query
        )

        print(
            "\nSEARCH ROUNDS:",
            result.search_rounds,
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
                source.title,
            )

            print(
                " ",
                source.url,
            )


if __name__ == "__main__":
    asyncio.run(main())