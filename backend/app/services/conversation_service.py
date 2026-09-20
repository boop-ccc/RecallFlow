from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from app.agents.supervisor import (
    SupervisorAgent,
)
from app.db.models.conversation import (
    ConversationThread,
)
from app.db.repositories.conversation_repository import (
    ConversationRepository,
)
from app.runtime.harness import (
    AgentHarness,
)
from app.services.query_resolution_service import (
    QueryResolutionService,
)
from app.schemas.conversation import (
    ConversationAskResponse,
)


class ConversationService:
    """
    Conversation Service
    = 长对话的业务编排层。

    它把三个东西串起来：

    1. Thread Context
       当前几轮对话上下文

    2. Agent Runtime
       Supervisor + Harness

    3. Checkpoint
       这一次 Agent Run 的持久化状态
    """

    # 只有当前消息明显依赖上一轮时，
    # Routing 才借用上一轮 User Message。
    _FOLLOW_UP_HINTS = (
        "继续",
        "接着",
        "这个",
        "那个",
        "刚才",
        "上面",
        "前面",
        "再说",
        "它",
        "这些",
        "这个方向",
    )

    def __init__(
        self,
        db: AsyncSession,
    ) -> None:
        self.db = db

        self.repo = (
            ConversationRepository(
                db
            )
        )

        self.supervisor = (
            SupervisorAgent(db)
        )

        self.query_resolver = (
            QueryResolutionService()
        )

        self.harness = (
            AgentHarness(
                timeout_seconds=90,
                max_steps=30,
                max_llm_calls=8,
                max_tool_calls=12,
                max_retrievals=4,
                max_subagents=3,
            )
        )

    async def _get_or_create_thread(
        self,
        thread_id: str | None,
    ) -> ConversationThread:
        if thread_id:
            thread = await (
                self.repo.get_thread(
                    thread_id
                )
            )

            if thread is None:
                raise ValueError(
                    "Conversation Thread "
                    f"不存在：{thread_id}"
                )

            return thread

        return await (
            self.repo.create_thread()
        )

    @staticmethod
    def _build_thread_context(
        turns,
        *,
        max_chars: int = 3500,
    ) -> str:
        """
        Thread Context 只保留最近有限窗口。

        目的：
        - 理解“继续”“这个”等指代
        - 不让历史消息无限占用 Token
        """

        if not turns:
            return ""

        lines: list[str] = []

        for turn in turns:
            role = (
                "用户"
                if turn.role == "user"
                else "助手"
            )

            lines.append(
                f"{role}: {turn.content}"
            )

        text = "\n".join(lines)

        return text[-max_chars:]

    @staticmethod
    def _last_user_message(
        turns,
    ) -> str | None:
        for turn in reversed(
            turns
        ):
            if turn.role == "user":
                return turn.content

        return None

    @classmethod
    def _build_routing_query(
        cls,
        *,
        turns,
        message: str,
    ) -> str:
        """
        Routing Context 和 Answer Context 分开。

        为什么？

        Supervisor 的规则路由只应该看：
        “用户这轮真正想做什么”。

        不能因为我们拼接 Prompt 时写了
        “当前用户请求”四个字，就误判成 research_only。

        对“继续这个方向”这种省略式追问，
        才补上一轮 User Message 帮助判断。
        """

        depends_on_history = any(
            hint in message
            for hint in (
                cls._FOLLOW_UP_HINTS
            )
        )

        if not depends_on_history:
            return message

        previous_user = (
            cls._last_user_message(
                turns
            )
        )

        if not previous_user:
            return message

        return (
            f"{previous_user}\n"
            f"{message}"
        )

    @staticmethod
    def _build_effective_query(
        *,
        thread_context: str,
        message: str,
    ) -> str:
        """
        Effective Query = 真正交给专业 Agent 的上下文化请求。

        Routing Query 负责“去哪”；
        Effective Query 负责“到了以后理解完整任务”。

        两者职责不同。
        """

        if not thread_context:
            return message

        return f"""
以下内容是同一 Thread 最近的对话，
只用于理解省略、指代和连续追问：

{thread_context}

本轮用户请求：

{message}
""".strip()

    async def _persist_failed_checkpoint(
        self,
        *,
        checkpoint_id: str,
        error: Exception,
    ) -> None:
        """
        Error Transaction Recovery
        = 失败事务恢复。

        如果 Agent 内部的 DB 操作失败，
        SQLAlchemy Session 可能进入 failed transaction。

        此时不能直接继续 flush。
        必须：

        failed transaction
            ↓
        rollback
            ↓
        重新读取已经 commit 的 Checkpoint
            ↓
        标记 failed
            ↓
        commit

        这样不会让 PendingRollbackError
        把真正的原始错误盖住。
        """

        await self.db.rollback()

        checkpoint = await (
            self.repo.get_checkpoint(
                checkpoint_id
            )
        )

        if checkpoint is None:
            raise RuntimeError(
                "原始 Agent Run 失败，"
                "且无法重新读取 Checkpoint："
                f"{checkpoint_id}"
            ) from error

        await (
            self.repo
            .mark_checkpoint_failed(
                checkpoint=checkpoint,
                error=error,
            )
        )

        await self.db.commit()

    async def ask(
        self,
        *,
        message: str,
        thread_id: str | None = None,
    ) -> ConversationAskResponse:
        thread = await (
            self._get_or_create_thread(
                thread_id
            )
        )

        recent_turns = await (
            self.repo.list_recent_turns(
                thread_id=thread.id,
                limit=6,
            )
        )

        # ==================================
        # Follow-up Query Resolution
        # ==================================
        #
        # 不再把整段 Thread Prompt 直接送去 Retrieval。
        #
        # “继续这个方向”
        #        ↓
        # Query Resolver
        #        ↓
        # “我之前研究 Agent 长期记忆的时候看了什么；
        #  继续这个方向”
        #
        # 这样既保留上下文，
        # 又避免 Prompt Scaffold / Assistant Answer
        # 污染 Retrieval。
        # ==================================

        resolution = (
            self.query_resolver.resolve(
                turns=recent_turns,
                message=message,
            )
        )

        effective_query = (
            resolution.standalone_query
        )

        routing_query = (
            resolution.routing_query
        )

        # ==================================
        # Durability Boundary
        # ==================================
        #
        # 在进入 LLM / Web / Retrieval
        # 这些不稳定外部步骤之前，
        # 先把用户请求与 Checkpoint 落盘。
        # ==================================

        await self.repo.add_turn(
            thread_id=thread.id,
            role="user",
            content=message,
            metadata={
                "query_resolution_strategy":
                    resolution.strategy,
                "used_history":
                    resolution.used_history,
                "standalone_query":
                    resolution.standalone_query[
                        :1000
                    ],
            },
        )

        checkpoint = await (
            self.repo.create_checkpoint(
                thread_id=thread.id,
                user_message=message,
                effective_query=(
                    effective_query
                ),
            )
        )

        await self.db.commit()

        # rollback 后 ORM 对象可能被刷新，
        # 所以提前保存稳定 ID。
        checkpoint_id = (
            checkpoint.id
        )

        try:
            result, context = (
                await self.harness.run(
                    user_query=message,
                    operation=lambda:
                        self.supervisor.run(
                            effective_query,
                            routing_query=(
                                routing_query
                            ),
                        ),
                )
            )

        except Exception as exc:
            await (
                self._persist_failed_checkpoint(
                    checkpoint_id=(
                        checkpoint_id
                    ),
                    error=exc,
                )
            )

            # 这里用裸 raise，
            # 保留真正的原始 traceback。
            raise

        verification_status = (
            result.verification.status
            if result.verification
            is not None
            else None
        )

        await self.repo.add_turn(
            thread_id=thread.id,
            role="assistant",
            content=result.answer,
            metadata={
                "route":
                    result.route,
                "agents_used":
                    result.agents_used,
                "verification_status":
                    verification_status,
                "run_id":
                    context.run_id,
            },
        )

        # checkpoint 已经提前 commit，
        # 成功路径继续使用当前对象即可。
        await (
            self.repo
            .mark_checkpoint_success(
                checkpoint=checkpoint,
                run_id=context.run_id,
                response_json=(
                    result.model_dump(
                        mode="json"
                    )
                ),
            )
        )

        await self.db.commit()

        return ConversationAskResponse(
            thread_id=thread.id,
            checkpoint_id=(
                checkpoint_id
            ),
            result=result,
        )

    async def retry_latest_failed(
        self,
        *,
        thread_id: str,
    ) -> ConversationAskResponse:
        """
        Request-level Recovery
        = 请求级恢复。

        失败后重新执行同一个 effective_query。
        """

        checkpoint = await (
            self.repo
            .latest_failed_checkpoint(
                thread_id=thread_id
            )
        )

        if checkpoint is None:
            raise ValueError(
                "没有可恢复的失败 Checkpoint。"
            )

        checkpoint_id = (
            checkpoint.id
        )

        checkpoint.status = "running"
        checkpoint.error_type = None
        checkpoint.error_message = None

        await self.db.commit()

        try:
            result, context = (
                await self.harness.run(
                    user_query=(
                        checkpoint
                        .user_message
                    ),
                    operation=lambda:
                        self.supervisor.run(
                            checkpoint
                            .effective_query,
                            routing_query=(
                                checkpoint
                                .effective_query
                            ),
                        ),
                )
            )

        except Exception as exc:
            await (
                self._persist_failed_checkpoint(
                    checkpoint_id=(
                        checkpoint_id
                    ),
                    error=exc,
                )
            )

            raise

        verification_status = (
            result.verification.status
            if result.verification
            is not None
            else None
        )

        await self.repo.add_turn(
            thread_id=thread_id,
            role="assistant",
            content=result.answer,
            metadata={
                "route":
                    result.route,
                "agents_used":
                    result.agents_used,
                "verification_status":
                    verification_status,
                "run_id":
                    context.run_id,
                "recovered_from_checkpoint":
                    checkpoint_id,
            },
        )

        # rollback 没有发生时对象仍然可用。
        await (
            self.repo
            .mark_checkpoint_success(
                checkpoint=checkpoint,
                run_id=context.run_id,
                response_json=(
                    result.model_dump(
                        mode="json"
                    )
                ),
            )
        )

        await self.db.commit()

        return ConversationAskResponse(
            thread_id=thread_id,
            checkpoint_id=(
                checkpoint_id
            ),
            result=result,
        )
