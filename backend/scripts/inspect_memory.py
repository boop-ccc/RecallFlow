import asyncio

from sqlalchemy import select

from app.db.models.work_session import WorkSession
from app.db.session import AsyncSessionFactory
from app.memory.session_memory import (
    SessionMemoryService,
)


async def main():
    async with AsyncSessionFactory() as db:

        # 找到所有 WorkSession
        stmt = (
            select(WorkSession)
            .order_by(WorkSession.started_at)
        )

        sessions = list(
            (await db.scalars(stmt)).all()
        )

        memory_service = SessionMemoryService(db)

        for index, session in enumerate(
            sessions,
            start=1,
        ):
            context = (
                await memory_service.build_context(
                    session.id
                )
            )

            if context is None:
                continue

            print(
                f"\n========== SESSION {index} ==========\n"
            )

            print(
                memory_service.to_prompt_text(
                    context
                )
            )


if __name__ == "__main__":
    asyncio.run(main())