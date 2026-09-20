import asyncio

from sqlalchemy import func, select

from app.db.models.work_session import (
    WorkSession,
    WorkSessionItem,
)
from app.db.session import AsyncSessionFactory
from app.services.session_reconstruction_service import (
    SessionReconstructionService,
)


async def main():
    async with AsyncSessionFactory() as db:

        service = SessionReconstructionService(db)

        count = await service.rebuild()

        print(f"\nCreated {count} WorkSessions\n")

        # 读取刚刚生成的 WorkSession
        stmt = (
            select(WorkSession)
            .order_by(WorkSession.started_at)
        )

        sessions = list(
            (await db.scalars(stmt)).all()
        )

        for index, session in enumerate(
            sessions,
            start=1,
        ):

            # 统计这个 Session 包含多少 Activity
            item_count = await db.scalar(
                select(func.count())
                .select_from(WorkSessionItem)
                .where(
                    WorkSessionItem.session_id
                    == session.id
                )
            )

            print(
                f"Session {index}: "
                f"{session.started_at} "
                f"-> {session.ended_at} "
                f"| activities={item_count}"
            )


if __name__ == "__main__":
    asyncio.run(main())