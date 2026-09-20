import asyncio
from datetime import datetime

from app.db.session import AsyncSessionFactory
from app.schemas.capture import CaptureRequest
from app.services.capture_service import CaptureService


DEMO_EVENTS = [
    {
        "client_event_id": "seed-001",
        "locator": "https://docs.langchain.com/memory",
        "title": "LangGraph Memory",
        "content_text": "Memory for stateful agents.",
        "observed_at": "2026-09-18T10:00:00+00:00",
    },
    {
        "client_event_id": "seed-002",
        "locator": "https://github.com/example/agent-memory",
        "title": "Agent Memory GitHub",
        "content_text": "Example implementation of agent memory.",
        "observed_at": "2026-09-18T10:10:00+00:00",
    },
    {
        "client_event_id": "seed-003",
        "locator": "https://example.com/agent-memory-blog",
        "title": "Agent Memory Blog",
        "content_text": "Discussion about episodic memory.",
        "observed_at": "2026-09-18T10:20:00+00:00",
    },

    # 和上一条间隔超过 30 分钟
    # 应该进入新的 WorkSession
    {
        "client_event_id": "seed-004",
        "locator": "https://docs.sqlalchemy.org/asyncio",
        "title": "SQLAlchemy Async",
        "content_text": "Async database access with SQLAlchemy.",
        "observed_at": "2026-09-18T11:30:00+00:00",
    },
    {
        "client_event_id": "seed-005",
        "locator": "https://fastapi.tiangolo.com/dependencies",
        "title": "FastAPI Dependencies",
        "content_text": "Dependency injection in FastAPI.",
        "observed_at": "2026-09-18T11:40:00+00:00",
    },
]


async def main():
    async with AsyncSessionFactory() as db:

        service = CaptureService(db)

        for event in DEMO_EVENTS:

            payload = CaptureRequest(
                client_event_id=event["client_event_id"],
                source_type="web",
                locator=event["locator"],
                title=event["title"],
                content_text=event["content_text"],
                event_type="web_visit",

                # ISO 时间字符串 → Python datetime
                observed_at=datetime.fromisoformat(
                    event["observed_at"]
                ),

                context={},
            )

            result = await service.capture(payload)

            print(
                event["client_event_id"],
                "duplicate=",
                result.duplicate,
            )


if __name__ == "__main__":
    asyncio.run(main())