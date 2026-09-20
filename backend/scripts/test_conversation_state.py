import asyncio

from sqlalchemy import select

from app.db.base import Base
from app.db.models.conversation import (
    ConversationThread,
    ConversationTurn,
    RunCheckpoint,
)
from app.db.session import (
    AsyncSessionFactory,
    engine,
)


async def main() -> None:
    # 测试脚本自己确保新表存在，
    # 不依赖你是否已经手动跑 init_db。
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    async with (
        AsyncSessionFactory()
        as db
    ):
        thread = ConversationThread(
            title="Runtime Memory Test"
        )

        db.add(thread)
        await db.flush()

        db.add(
            ConversationTurn(
                thread_id=thread.id,
                sequence=1,
                role="user",
                content=(
                    "我在研究 Agent Memory。"
                ),
                metadata_json={},
            )
        )

        db.add(
            ConversationTurn(
                thread_id=thread.id,
                sequence=2,
                role="assistant",
                content=(
                    "已经恢复到相关工作记录。"
                ),
                metadata_json={
                    "verification_status":
                        "verified"
                },
            )
        )

        checkpoint = RunCheckpoint(
            thread_id=thread.id,
            status="failed",
            user_message=(
                "继续这个方向"
            ),
            effective_query=(
                "历史上下文：Agent Memory\n"
                "当前请求：继续这个方向"
            ),
            error_type="DemoError",
            error_message=(
                "模拟失败，用于验证持久化。"
            ),
        )

        db.add(checkpoint)

        await db.commit()

        thread_id = thread.id
        checkpoint_id = checkpoint.id

    # 新建一个完全不同的 DB Session，
    # 模拟“程序下一次重新读取”。
    async with (
        AsyncSessionFactory()
        as db
    ):
        thread = await db.get(
            ConversationThread,
            thread_id,
        )

        turns = list(
            (
                await db.scalars(
                    select(
                        ConversationTurn
                    )
                    .where(
                        ConversationTurn
                        .thread_id
                        == thread_id
                    )
                    .order_by(
                        ConversationTurn
                        .sequence
                    )
                )
            ).all()
        )

        checkpoint = await db.get(
            RunCheckpoint,
            checkpoint_id,
        )

        print(
            "\n=============================="
        )
        print("THREAD PERSISTENCE")
        print("==============================")

        print(
            "Thread Exists:",
            thread is not None,
        )

        print(
            "Turns:",
            [
                (
                    item.sequence,
                    item.role,
                    item.content,
                )
                for item in turns
            ],
        )

        print(
            "\n=============================="
        )
        print("CHECKPOINT PERSISTENCE")
        print("==============================")

        print(
            "Checkpoint Status:",
            checkpoint.status,
        )

        print(
            "Failed Request:",
            checkpoint.user_message,
        )

        print(
            "Recoverable:",
            checkpoint.status
            == "failed",
        )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
