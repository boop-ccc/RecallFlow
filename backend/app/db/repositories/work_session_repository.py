from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import ActivityEvent
from app.db.models.work_session import (
    WorkSession,
    WorkSessionItem,
)


class WorkSessionRepository:
    """
    WorkSession 的数据库访问层。

    Repository = 数据访问层。
    只负责数据库查询、创建、修改，
    不负责判断 30 分钟是不是同一个 Session。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_activities(self) -> list[ActivityEvent]:
        """
        按真实访问时间读取全部 Activity。
        主要给手动 rebuild 使用。
        """

        stmt = (
            select(ActivityEvent)
            .order_by(ActivityEvent.observed_at.asc())
        )

        result = await self.db.scalars(stmt)

        return list(result.all())

    async def clear_sessions(self) -> None:
        """
        清空全部 WorkSession。

        注意：
        这个方法只给手动 rebuild 使用。
        正常 Capture 不应该调用它。
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
        """
        创建新的 WorkSession。
        """

        session = WorkSession(
            started_at=started_at,
            ended_at=ended_at,
        )

        self.db.add(session)

        # flush：
        # 先把数据发送给数据库，
        # 这样马上就能拿到 session.id。
        await self.db.flush()

        return session

    async def get_session(
        self,
        session_id: str,
    ) -> WorkSession | None:
        """
        根据 session_id 获取 WorkSession。
        """

        stmt = select(WorkSession).where(
            WorkSession.id == session_id
        )

        return await self.db.scalar(stmt)

    async def get_activity_item(
        self,
        activity_id: str,
    ) -> WorkSessionItem | None:
        """
        判断某个 Activity 是否已经加入 WorkSession。

        防止同一条 Activity 被重复加入。
        """

        stmt = select(WorkSessionItem).where(
            WorkSessionItem.activity_id == activity_id
        )

        return await self.db.scalar(stmt)

    async def list_nearby_sessions(
        self,
        *,
        lower_bound: datetime,
        upper_bound: datetime,
    ) -> list[WorkSession]:
        """
        查找时间上接近当前 Activity 的 WorkSession。

        例如新 Activity 是 20:36：
        系统会寻找前后 30 分钟范围内的 Session。
        """

        stmt = (
            select(WorkSession)
            .where(
                WorkSession.started_at <= upper_bound,
                WorkSession.ended_at >= lower_bound,
            )
            .order_by(
                WorkSession.ended_at.desc()
            )
        )

        result = await self.db.scalars(stmt)

        return list(result.all())

    async def count_session_items(
        self,
        session_id: str,
    ) -> int:
        """
        统计一个 WorkSession 已经有多少条 Activity。
        """

        count = await self.db.scalar(
            select(func.count())
            .select_from(WorkSessionItem)
            .where(
                WorkSessionItem.session_id
                == session_id
            )
        )

        return int(count or 0)

    async def add_activity(
        self,
        *,
        session_id: str,
        activity_id: str,
        position: int,
    ) -> WorkSessionItem:
        """
        把一条 Activity 加入 WorkSession。
        """

        item = WorkSessionItem(
            session_id=session_id,
            activity_id=activity_id,
            position=position,
        )

        self.db.add(item)

        return item

    async def list_session_items_chronologically(
        self,
        session_id: str,
    ) -> list[WorkSessionItem]:
        """
        按 Activity 的真实发生时间重新排列 Session 内部顺序。

        这样即使某条 Activity 晚几分钟才传到后端，
        也不会破坏 WorkSession 内部时间顺序。
        """

        stmt = (
            select(WorkSessionItem)
            .join(
                ActivityEvent,
                ActivityEvent.id
                == WorkSessionItem.activity_id,
            )
            .where(
                WorkSessionItem.session_id
                == session_id
            )
            .order_by(
                ActivityEvent.observed_at.asc(),
                ActivityEvent.id.asc(),
            )
        )

        result = await self.db.scalars(stmt)

        return list(result.all())