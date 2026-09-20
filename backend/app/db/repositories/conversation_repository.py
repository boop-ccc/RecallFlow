from sqlalchemy import (
    func,
    select,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.db.models.conversation import (
    ConversationThread,
    ConversationTurn,
    RunCheckpoint,
)


class ConversationRepository:
    """
    Conversation Repository
    = 对话数据访问层。

    Repository 只负责数据库读写，
    不决定 Thread Context、Routing 等业务规则。
    """

    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

    async def create_thread(
        self,
        *,
        title: str | None = None,
    ) -> ConversationThread:
        thread = ConversationThread(
            title=title
        )

        self.db.add(thread)
        await self.db.flush()

        return thread

    async def get_thread(
        self,
        thread_id: str,
    ) -> ConversationThread | None:
        return await self.db.get(
            ConversationThread,
            thread_id,
        )

    async def get_checkpoint(
        self,
        checkpoint_id: str,
    ) -> RunCheckpoint | None:
        """
        rollback 之后重新读取 Checkpoint。

        为什么需要这个方法？

        一个数据库异常可能让当前 ORM Transaction
        进入 failed state。rollback 后，我们重新从 DB
        获取已经提前 commit 的 Checkpoint，再记录失败状态。
        """
        return await self.db.get(
            RunCheckpoint,
            checkpoint_id,
        )

    async def next_sequence(
        self,
        thread_id: str,
    ) -> int:
        stmt = select(
            func.max(
                ConversationTurn.sequence
            )
        ).where(
            ConversationTurn.thread_id
            == thread_id
        )

        current = await self.db.scalar(
            stmt
        )

        return int(current or 0) + 1

    async def add_turn(
        self,
        *,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> ConversationTurn:
        sequence = await (
            self.next_sequence(
                thread_id
            )
        )

        turn = ConversationTurn(
            thread_id=thread_id,
            sequence=sequence,
            role=role,
            content=content,
            metadata_json=(
                metadata or {}
            ),
        )

        self.db.add(turn)
        await self.db.flush()

        return turn

    async def list_recent_turns(
        self,
        *,
        thread_id: str,
        limit: int = 6,
    ) -> list[
        ConversationTurn
    ]:
        stmt = (
            select(
                ConversationTurn
            )
            .where(
                ConversationTurn.thread_id
                == thread_id
            )
            .order_by(
                ConversationTurn.sequence
                .desc()
            )
            .limit(limit)
        )

        rows = list(
            (
                await self.db.scalars(
                    stmt
                )
            ).all()
        )

        rows.reverse()

        return rows

    async def create_checkpoint(
        self,
        *,
        thread_id: str,
        user_message: str,
        effective_query: str,
    ) -> RunCheckpoint:
        checkpoint = RunCheckpoint(
            thread_id=thread_id,
            status="running",
            user_message=user_message,
            effective_query=(
                effective_query
            ),
        )

        self.db.add(checkpoint)
        await self.db.flush()

        return checkpoint

    async def mark_checkpoint_success(
        self,
        *,
        checkpoint: RunCheckpoint,
        run_id: str,
        response_json: dict,
    ) -> None:
        checkpoint.run_id = run_id
        checkpoint.status = "success"
        checkpoint.response_json = (
            response_json
        )
        checkpoint.error_type = None
        checkpoint.error_message = None

        await self.db.flush()

    async def mark_checkpoint_failed(
        self,
        *,
        checkpoint: RunCheckpoint,
        error: Exception,
    ) -> None:
        checkpoint.status = "failed"
        checkpoint.error_type = (
            type(error).__name__
        )
        checkpoint.error_message = (
            str(error)[:1000]
        )

        await self.db.flush()

    async def latest_failed_checkpoint(
        self,
        *,
        thread_id: str,
    ) -> RunCheckpoint | None:
        stmt = (
            select(
                RunCheckpoint
            )
            .where(
                RunCheckpoint.thread_id
                == thread_id,
                RunCheckpoint.status
                == "failed",
            )
            .order_by(
                RunCheckpoint.created_at
                .desc()
            )
            .limit(1)
        )

        return await self.db.scalar(
            stmt
        )
