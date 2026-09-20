import asyncio

from app.db.base import Base
from app.db.session import (
    AsyncSessionFactory,
    engine,
)
from app.services.conversation_service import (
    ConversationService,
)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    async with (
        AsyncSessionFactory()
        as db
    ):
        service = ConversationService(
            db
        )

        first = await service.ask(
            message=(
                "我之前研究 Agent "
                "长期记忆的时候看了什么？"
            )
        )

        thread_id = (
            first.thread_id
        )

        print(
            "\nTURN 1"
        )
        print(
            "Route:",
            first.result.route,
        )
        print(
            "Answer:",
            first.result.answer,
        )

    async with (
        AsyncSessionFactory()
        as db
    ):
        service = ConversationService(
            db
        )

        second = await service.ask(
            thread_id=thread_id,
            message="继续这个方向",
        )

        print(
            "\nTURN 2"
        )
        print(
            "Same Thread:",
            second.thread_id
            == thread_id,
        )
        print(
            "Route:",
            second.result.route,
        )
        print(
            "Answer:",
            second.result.answer,
        )

        print(
            "Verification:",
            (
                second.result
                .verification.status
                if second.result
                .verification
                is not None
                else None
            ),
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
