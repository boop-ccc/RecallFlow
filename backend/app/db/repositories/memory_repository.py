from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import (
    ActivityEvent,
    Resource,
    ResourceSnapshot,
)
from app.db.models.work_session import (
    WorkSession,
    WorkSessionItem,
)


class MemoryRepository:
    """
    Memory 数据访问层。

    负责从数据库找到：
    WorkSession 对应的 Activity / Resource / Snapshot。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_session(
        self,
        session_id: str,
    ) -> WorkSession | None:
        """
        获取一个 WorkSession。
        """

        return await self.db.get(
            WorkSession,
            session_id,
        )

    async def get_session_evidence(
        self,
        session_id: str,
    ):
        """
        获取这个 WorkSession 下的全部真实证据。
        """

        stmt = (
            select(
                ActivityEvent.id.label("activity_id"),
                ActivityEvent.observed_at,

                Resource.id.label("resource_id"),
                Resource.locator,

                ResourceSnapshot.title,
                ResourceSnapshot.content_text,
            )

            # 从 WorkSessionItem 开始查
            .select_from(WorkSessionItem)

            # WorkSessionItem -> Activity
            .join(
                ActivityEvent,
                ActivityEvent.id
                == WorkSessionItem.activity_id,
            )

            # Activity -> Resource
            .join(
                Resource,
                Resource.id
                == ActivityEvent.resource_id,
            )

            # Activity -> Snapshot
            # outerjoin = Snapshot 不存在也允许返回
            .outerjoin(
                ResourceSnapshot,
                ResourceSnapshot.id
                == ActivityEvent.snapshot_id,
            )

            .where(
                WorkSessionItem.session_id
                == session_id
            )

            # 保留原始访问顺序
            .order_by(
                WorkSessionItem.position
            )
        )

        result = await self.db.execute(stmt)

        return result.all()