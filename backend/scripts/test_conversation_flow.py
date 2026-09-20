import asyncio
import sys

from app.db.base import Base
from app.db.session import (
    AsyncSessionFactory,
    engine,
)
from app.services.conversation_service import (
    ConversationService,
)


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    # ==================================
    # TURN 1
    # ==================================

    async with (
        AsyncSessionFactory()
        as db
    ):
        service = ConversationService(
            db
        )

        first = await service.ask(
            message=(
                "我之前研究 Agent "
                "长期记忆的时候看了什么？"
            )
        )

        thread_id = (
            first.thread_id
        )

        print(
            "\n=============================="
        )
        print("TURN 1")
        print("==============================")

        print(
            "Thread ID:",
            thread_id,
        )

        print(
            "Route:",
            first.result.route,
        )

        print(
            first.result.answer
        )

    # ==================================
    # TURN 2
    # ==================================
    #
    # 故意重新创建 DB Session，
    # 模拟真正的下一次 HTTP 请求。
    #
    # “继续这个方向”本身语义不完整，
    # ConversationService 会借用上一轮 User Message
    # 做 routing，同时使用最近 Thread Context
    # 帮专业 Agent 理解指代。
    # ==================================

    async with (
        AsyncSessionFactory()
        as db
    ):
        service = ConversationService(
            db
        )

        second_message = (
            "继续这个方向"
            if len(sys.argv) == 1
            else " ".join(
                sys.argv[1:]
            )
        )

        try:
            second = await service.ask(
                thread_id=thread_id,
                message=second_message,
            )

        except Exception as exc:
            print(
                "\n=============================="
            )
            print("TURN 2 FAILED")
            print("==============================")

            print(
                "Original Error Type:",
                type(exc).__name__,
            )

            print(
                "Original Error:",
                str(exc),
            )

            print(
                "\n注意："
                "如果这里仍然失败，"
                "现在显示的应该是真正的原始异常，"
                "而不再是 PendingRollbackError。"
            )

            raise

        print(
            "\n=============================="
        )
        print("TURN 2")
        print("==============================")

        print(
            "Same Thread:",
            second.thread_id
            == thread_id,
        )

        print(
            "User:",
            second_message,
        )

        print(
            "Route:",
            second.result.route,
        )

        print(
            second.result.answer
        )

        if (
            second.result.verification
            is not None
        ):
            print(
                "Verification:",
                second.result
                .verification.status,
            )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
