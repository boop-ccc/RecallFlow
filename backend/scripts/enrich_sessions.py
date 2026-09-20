import asyncio

from sqlalchemy import select

from app.db.models.work_session import WorkSession
from app.db.session import AsyncSessionFactory
from app.services.session_enrichment_service import (
    SessionEnrichmentService,
)


async def main():
    async with AsyncSessionFactory() as db:

        stmt = (
            select(WorkSession)
            .order_by(WorkSession.started_at)
        )

        sessions = list(
            (await db.scalars(stmt)).all()
        )

        service = SessionEnrichmentService(db)

        for index, session in enumerate(
            sessions,
            start=1,
        ):
            print(
                f"\nEnriching Session {index}..."
            )

            result = await service.enrich(
                session.id
            )

            print(
                "Title:",
                result.title,
            )

            print(
                "Summary:",
                result.summary,
            )

            print(
                "Keywords:",
                result.keywords,
            )

            print(
                "Open Tasks:",
                result.open_tasks,
            )


if __name__ == "__main__":
    asyncio.run(main())