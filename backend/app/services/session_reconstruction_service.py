from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import ActivityEvent
from app.db.models.work_session import WorkSession
from app.db.repositories.work_session_repository import (
    WorkSessionRepository,
)


# Session Gap = 会话间隔阈值
SESSION_GAP = timedelta(minutes=30)


class SessionReconstructionService:
    """
    WorkSession Reconstruction
    = 工作会话重建服务。

    两种模式：

    rebuild()
    → 手动完整重建，主要用于调试。

    add_activity_incrementally()
    → Chrome Capture 后自动增量更新。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkSessionRepository(db)

    async def rebuild(self) -> int:
        """
        完整重建全部 WorkSession。
        """

        activities = await self.repo.list_activities()

        if not activities:
            return 0

        await self.repo.clear_sessions()

        session_count = 0
        current_group: list[ActivityEvent] = []

        for activity in activities:

            if not current_group:
                current_group.append(activity)
                continue

            previous = current_group[-1]

            gap = (
                activity.observed_at
                - previous.observed_at
            )

            if gap <= SESSION_GAP:
                current_group.append(activity)

            else:
                await self._save_group(
                    current_group
                )

                session_count += 1
                current_group = [activity]

        if current_group:
            await self._save_group(
                current_group
            )
            session_count += 1

        await self.db.commit()

        return session_count

    async def add_activity_incrementally(
        self,
        activity: ActivityEvent,
    ) -> WorkSession:
        """
        新 Activity 到来以后，
        自动加入已有 WorkSession，
        或创建新的 WorkSession。
        """

        # --------------------------------
        # 1. 防止重复加入
        # --------------------------------
        existing_item = (
            await self.repo.get_activity_item(
                activity.id
            )
        )

        if existing_item is not None:

            existing_session = (
                await self.repo.get_session(
                    existing_item.session_id
                )
            )

            if existing_session is None:
                raise RuntimeError(
                    "Activity 已存在 WorkSessionItem，"
                    "但 WorkSession 不存在。"
                )

            return existing_session

        # --------------------------------
        # 2. 查找附近 WorkSession
        # --------------------------------
        lower_bound = (
            activity.observed_at
            - SESSION_GAP
        )

        upper_bound = (
            activity.observed_at
            + SESSION_GAP
        )

        nearby_sessions = (
            await self.repo.list_nearby_sessions(
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            )
        )

        # --------------------------------
        # 3. 加入已有 Session
        # --------------------------------
        if nearby_sessions:

            session = nearby_sessions[0]

            if (
                activity.observed_at
                < session.started_at
            ):
                session.started_at = (
                    activity.observed_at
                )

            if (
                activity.observed_at
                > session.ended_at
            ):
                session.ended_at = (
                    activity.observed_at
                )

        # --------------------------------
        # 4. 或创建新的 Session
        # --------------------------------
        else:

            session = (
                await self.repo.create_session(
                    started_at=activity.observed_at,
                    ended_at=activity.observed_at,
                )
            )

        # --------------------------------
        # 5. 关键：
        # 新 Activity 出现后，
        # 原来的语义摘要已经过期。
        #
        # 这里先清空，
        # 但不立即调用 LLM。
        #
        # 等用户真正查询时，
        # 再自动重新生成。
        # --------------------------------
        session.title = None
        session.summary = None
        session.keywords = []
        session.open_tasks = []

        # --------------------------------
        # 6. Activity 加入 Session
        # --------------------------------
        position = (
            await self.repo.count_session_items(
                session.id
            )
        )

        await self.repo.add_activity(
            session_id=session.id,
            activity_id=activity.id,
            position=position,
        )

        await self.db.flush()

        # --------------------------------
        # 7. 按真实发生时间重新排序
        # --------------------------------
        items = (
            await self.repo
            .list_session_items_chronologically(
                session.id
            )
        )

        for index, item in enumerate(items):
            item.position = index

        await self.db.commit()

        return session

    async def _save_group(
        self,
        activities: list[ActivityEvent],
    ) -> None:
        """
        rebuild() 使用。
        """

        session = (
            await self.repo.create_session(
                started_at=(
                    activities[0].observed_at
                ),
                ended_at=(
                    activities[-1].observed_at
                ),
            )
        )

        for position, activity in enumerate(
            activities
        ):

            await self.repo.add_activity(
                session_id=session.id,
                activity_id=activity.id,
                position=position,
            )