from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.resource_repository import (
    ResourceRepository,
)
from app.schemas.capture import CaptureRequest


@dataclass
class CaptureResult:
    resource_id: str
    snapshot_id: str | None
    activity_id: str
    duplicate: bool


class CaptureService:
    """
    CaptureService = 采集业务服务

    负责一次 Capture 的完整业务流程。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ResourceRepository(db)

    async def capture(
        self,
        payload: CaptureRequest,
    ) -> CaptureResult:

        try:
            # 1. Idempotency Check
            # 幂等检查：
            # 同一个 client_event_id 已经处理过，
            # 就直接返回旧结果。
            existing_activity = (
                await self.repo.get_activity_by_event_id(
                    payload.client_event_id
                )
            )

            if existing_activity is not None:
                return CaptureResult(
                    resource_id=existing_activity.resource_id,
                    snapshot_id=existing_activity.snapshot_id,
                    activity_id=existing_activity.id,
                    duplicate=True,
                )

            # 2. Find or Create Resource
            # 查找或者创建资源身份。
            resource = await self.repo.get_resource(
                payload.source_type,
                payload.locator,
            )

            if resource is None:
                resource = await self.repo.create_resource(
                    source_type=payload.source_type,
                    locator=payload.locator,
                    observed_at=payload.observed_at,
                )

            else:
                # 更新最近访问时间。
                if payload.observed_at > resource.last_seen_at:
                    resource.last_seen_at = payload.observed_at

            snapshot = None

            # 3. Snapshot
            # 正文存在时才处理内容版本。
            if payload.content_text:
                content_hash = self._build_content_hash(
                    payload.title,
                    payload.content_text,
                )

                snapshot = await self.repo.get_snapshot(
                    resource_id=resource.id,
                    content_hash=content_hash,
                )

                # 相同内容已经存在，就不重复创建。
                if snapshot is None:
                    snapshot = await self.repo.create_snapshot(
                        resource_id=resource.id,
                        title=payload.title,
                        content_text=payload.content_text,
                        content_hash=content_hash,
                        captured_at=payload.observed_at,
                    )

            # 4. Activity
            # 每一次真实访问都会产生新的 Activity。
            activity = await self.repo.create_activity(
                client_event_id=payload.client_event_id,
                resource_id=resource.id,
                snapshot_id=(
                    snapshot.id
                    if snapshot is not None
                    else None
                ),
                event_type=payload.event_type,
                observed_at=payload.observed_at,
                context_json=payload.context,
            )

            # Transaction Commit
            # 事务提交：
            # 上面的修改作为一次完整 Capture 保存。
            await self.db.commit()

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
            # Rollback = 回滚
            # 中间任何一步出错，
            # 撤销这一轮未提交的数据。
            await self.db.rollback()
            raise

    @staticmethod
    def _build_content_hash(
        title: str | None,
        content_text: str,
    ) -> str:
        """
        Content Hash = 内容指纹

        内容完全一样 → hash 一样
        内容发生变化 → hash 不一样
        """

        raw = f"{title or ''}\n{content_text}"

        return sha256(
            raw.encode("utf-8")
        ).hexdigest()