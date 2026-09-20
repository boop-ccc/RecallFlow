from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import ActivityEvent
from app.db.models.work_session import (
    WorkSession,
    WorkSessionItem,
)


class WorkSessionRepository:
    """
    WorkSession 的数据库访问层。

    Repository 只负责数据库操作，
    不负责判断 Activity 应该怎么分组。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_activities(self) -> list[ActivityEvent]:
        """
        按用户真实访问时间读取全部 Activity。
        """

        stmt = (
            select(ActivityEvent)
            .order_by(ActivityEvent.observed_at.asc())
        )

        result = await self.db.scalars(stmt)

        return list(result.all())

    async def clear_sessions(self) -> None:
        """
        第一版为了方便重新测试，
        每次 Reconstruction 前先清空旧 Session。
        """

        await self.db.execute(
            delete(WorkSessionItem)
        )

        await self.db.execute(
            delete(WorkSession)
        )

    async def create_session(
        self,
        *,
        started_at,
        ended_at,
    ) -> WorkSession:

        session = WorkSession(
            started_at=started_at,
            ended_at=ended_at,
        )

        self.db.add(session)

        # flush = 把数据发给数据库，
        # 但现在还没有最终 commit。
        await self.db.flush()

        return session

    async def add_activity(
        self,
        *,
        session_id: str,
        activity_id: str,
        position: int,
    ) -> WorkSessionItem:

        item = WorkSessionItem(
            session_id=session_id,
            activity_id=activity_id,
            position=position,
        )

        self.db.add(item)

        return item