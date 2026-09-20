from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import ActivityEvent
from app.db.repositories.work_session_repository import (
    WorkSessionRepository,
)


# Session Gap = 会话间隔阈值
#
# 两次行为间隔超过 30 分钟，
# 第一版就认为用户已经进入另一项工作。
SESSION_GAP = timedelta(minutes=30)


class SessionReconstructionService:
    """
    WorkSession Reconstruction
    工作会话重建服务。

    输入：
    一堆 ActivityEvent

    输出：
    多个 WorkSession
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkSessionRepository(db)

    async def rebuild(self) -> int:
        """
        重新构建全部 WorkSession。

        返回值：
        最终创建了多少个 Session。
        """

        # 1. 获取全部历史行为。
        activities = await self.repo.list_activities()

        if not activities:
            return 0

        # 第一版为了方便调试，
        # 每次都重新生成 WorkSession。
        await self.repo.clear_sessions()

        session_count = 0

        # 当前正在构建的一组 Activity。
        current_group: list[ActivityEvent] = []

        for activity in activities:

            # 第一条 Activity：
            # 直接开始一个新的 Group。
            if not current_group:
                current_group.append(activity)
                continue

            previous = current_group[-1]

            # Time Gap = 时间间隔
            gap = (
                activity.observed_at
                - previous.observed_at
            )

            # 30分钟以内：
            # 暂时认为属于同一个工作 Session。
            if gap <= SESSION_GAP:
                current_group.append(activity)

            else:
                # 当前 Session 结束。
                await self._save_group(current_group)

                session_count += 1

                # 开始新的 Session。
                current_group = [activity]

        # for 循环结束之后，
        # 最后一组还没有保存。
        if current_group:
            await self._save_group(current_group)
            session_count += 1

        # Transaction Commit
        # 事务最终提交。
        await self.db.commit()

        return session_count

    async def _save_group(
        self,
        activities: list[ActivityEvent],
    ) -> None:

        session = await self.repo.create_session(
            started_at=activities[0].observed_at,
            ended_at=activities[-1].observed_at,
        )

        for position, activity in enumerate(activities):

            await self.repo.add_activity(
                session_id=session.id,
                activity_id=activity.id,
                position=position,
            )