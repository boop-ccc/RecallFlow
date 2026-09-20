from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import (
    ActivityEvent,
    Resource,
    ResourceSnapshot,
)


class ResourceRepository:
    """
    Repository = 数据访问层

    只负责：
    查数据库 / 新增数据

    不负责：
    判断业务流程。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_resource(
        self,
        source_type: str,
        locator: str,
    ) -> Resource | None:
        """
        根据 source_type + locator 查找 Resource。
        """

        stmt = select(Resource).where(
            Resource.source_type == source_type,
            Resource.locator == locator,
        )

        return await self.db.scalar(stmt)

    async def create_resource(
        self,
        *,
        source_type: str,
        locator: str,
        observed_at: datetime,
    ) -> Resource:

        resource = Resource(
            source_type=source_type,
            locator=locator,
            last_seen_at=observed_at,
        )

        self.db.add(resource)

        # flush = 把当前修改发送给数据库，
        # 但事务还没有最终 commit。
        await self.db.flush()

        return resource

    async def get_snapshot(
        self,
        *,
        resource_id: str,
        content_hash: str,
    ) -> ResourceSnapshot | None:

        stmt = select(ResourceSnapshot).where(
            ResourceSnapshot.resource_id == resource_id,
            ResourceSnapshot.content_hash == content_hash,
        )

        return await self.db.scalar(stmt)

    async def create_snapshot(
        self,
        *,
        resource_id: str,
        title: str | None,
        content_text: str,
        content_hash: str,
        captured_at: datetime,
    ) -> ResourceSnapshot:

        snapshot = ResourceSnapshot(
            resource_id=resource_id,
            title=title,
            content_text=content_text,
            content_hash=content_hash,
            captured_at=captured_at,
        )

        self.db.add(snapshot)
        await self.db.flush()

        return snapshot

    async def get_activity_by_event_id(
        self,
        client_event_id: str,
    ) -> ActivityEvent | None:
        """
        用幂等键判断同一次事件是否已经处理过。
        """

        stmt = select(ActivityEvent).where(
            ActivityEvent.client_event_id == client_event_id
        )

        return await self.db.scalar(stmt)

    async def create_activity(
        self,
        *,
        client_event_id: str,
        resource_id: str,
        snapshot_id: str | None,
        event_type: str,
        observed_at: datetime,
        context_json: dict,
    ) -> ActivityEvent:

        activity = ActivityEvent(
            client_event_id=client_event_id,
            resource_id=resource_id,
            snapshot_id=snapshot_id,
            event_type=event_type,
            observed_at=observed_at,
            context_json=context_json,
        )

        self.db.add(activity)
        await self.db.flush()

        return activity