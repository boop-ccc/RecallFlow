from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.resource_repository import (
    ResourceRepository,
)
from app.schemas.capture import CaptureRequest
from app.services.session_reconstruction_service import (
    SessionReconstructionService,
)


def _to_utc_naive(dt: datetime) -> datetime:
    """
    统一数据库内部使用的时间格式。

    浏览器传来的时间可能带时区，
    SQLite 读取出来的时间通常不带时区。

    这里统一后再进行比较和保存，
    避免 aware / naive datetime 报错。
    """
    if dt.tzinfo is None:
        return dt

    return (
        dt.astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


@dataclass
class CaptureResult:
    """
    一次 Capture 最终返回的结果。
    """

    resource_id: str
    snapshot_id: str | None
    activity_id: str
    duplicate: bool


class CaptureService:
    """
    CaptureService = 浏览行为采集服务。

    一次 Capture 的完整流程：

    浏览器页面
        ↓
    Resource
        ↓
    Snapshot
        ↓
    ActivityEvent
        ↓
    自动更新 WorkSession
    """

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

        # Resource / Snapshot / Activity 数据访问
        self.repo = ResourceRepository(db)

        # WorkSession 自动划分服务
        self.session_service = (
            SessionReconstructionService(db)
        )

    async def capture(
        self,
        payload: CaptureRequest,
    ) -> CaptureResult:

        try:
            # ---------------------------------
            # 0. 统一本次事件时间
            # ---------------------------------
            observed_at = _to_utc_naive(
                payload.observed_at
            )

            # ---------------------------------
            # 1. Idempotency
            # 幂等检查
            #
            # 同一个 client_event_id
            # 重试时不会重复创建 Activity。
            # ---------------------------------
            existing_activity = (
                await self.repo
                .get_activity_by_event_id(
                    payload.client_event_id
                )
            )

            if existing_activity is not None:

                # 即使是重复请求，
                # 也检查一下它是否已经进入 WorkSession。
                #
                # 这样可以修复：
                # Activity 已经存在，
                # 但之前 WorkSession 更新失败的情况。
                await (
                    self.session_service
                    .add_activity_incrementally(
                        existing_activity
                    )
                )

                return CaptureResult(
                    resource_id=(
                        existing_activity.resource_id
                    ),
                    snapshot_id=(
                        existing_activity.snapshot_id
                    ),
                    activity_id=(
                        existing_activity.id
                    ),
                    duplicate=True,
                )

            # ---------------------------------
            # 2. Resource
            # 找到或创建网页资源
            # ---------------------------------
            resource = (
                await self.repo.get_resource(
                    payload.source_type,
                    payload.locator,
                )
            )

            if resource is None:

                resource = (
                    await self.repo.create_resource(
                        source_type=(
                            payload.source_type
                        ),
                        locator=payload.locator,
                        observed_at=observed_at,
                    )
                )

            else:

                last_seen_at = _to_utc_naive(
                    resource.last_seen_at
                )

                if observed_at > last_seen_at:
                    resource.last_seen_at = (
                        observed_at
                    )

            # ---------------------------------
            # 3. Snapshot
            # 网页内容版本
            # ---------------------------------
            snapshot = None

            if payload.content_text:

                content_hash = (
                    self._build_content_hash(
                        payload.title,
                        payload.content_text,
                    )
                )

                snapshot = (
                    await self.repo.get_snapshot(
                        resource_id=resource.id,
                        content_hash=content_hash,
                    )
                )

                # 内容发生变化时，
                # 才创建新的 Snapshot。
                if snapshot is None:

                    snapshot = (
                        await self.repo
                        .create_snapshot(
                            resource_id=resource.id,
                            title=payload.title,
                            content_text=(
                                payload.content_text
                            ),
                            content_hash=(
                                content_hash
                            ),
                            captured_at=(
                                observed_at
                            ),
                        )
                    )

            # ---------------------------------
            # 4. ActivityEvent
            #
            # 每一次真实访问行为
            # 都产生一条 Activity。
            # ---------------------------------
            activity = (
                await self.repo.create_activity(
                    client_event_id=(
                        payload.client_event_id
                    ),
                    resource_id=resource.id,
                    snapshot_id=(
                        snapshot.id
                        if snapshot is not None
                        else None
                    ),
                    event_type=(
                        payload.event_type
                    ),
                    observed_at=observed_at,
                    context_json=(
                        payload.context
                    ),
                )
            )

            # ---------------------------------
            # 5. 自动更新 WorkSession
            #
            # 这就是这次新增的关键逻辑。
            #
            # 不再需要每次手动：
            # python -m scripts.rebuild_sessions
            # ---------------------------------
            await (
                self.session_service
                .add_activity_incrementally(
                    activity
                )
            )

            # add_activity_incrementally()
            # 会完成本次事务提交。

            return CaptureResult(
                resource_id=resource.id,
                snapshot_id=(
                    snapshot.id
                    if snapshot is not None
                    else None
                ),
                activity_id=activity.id,
                duplicate=False,
            )

        except Exception:
            # 任意一步失败都进行回滚。
            await self.db.rollback()
            raise

    @staticmethod
    def _build_content_hash(
        title: str | None,
        content_text: str,
    ) -> str:
        """
        Content Hash = 内容指纹。

        相同网页内容：
        hash 相同。

        网页内容发生变化：
        hash 不同。
        """

        raw = (
            f"{title or ''}\n"
            f"{content_text}"
        )

        return sha256(
            raw.encode("utf-8")
        ).hexdigest()