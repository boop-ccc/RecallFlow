from dataclasses import dataclass


class BudgetExceeded(RuntimeError):
    """
    Agent 运行预算耗尽。

    预算的目的不是“省钱”这么简单，
    而是给 Agent 的自主行为设置明确上限，
    防止无限循环、工具滥用、失控重试和异常成本。
    """

    def __init__(
        self,
        budget_name: str,
        used: int,
        limit: int,
    ) -> None:
        self.budget_name = budget_name
        self.used = used
        self.limit = limit

        super().__init__(
            f"{budget_name} 预算已耗尽："
            f"{used}/{limit}"
        )


@dataclass
class RunBudget:
    """
    一次 Agent Run 的统一预算。

    每一次用户请求都会创建一份新的 RunBudget。
    Memory / Research / Supervisor / Tool Runtime
    共享这份预算，而不是各自无限执行。
    """

    # -----------------------------
    # Budget Limits
    # -----------------------------

    max_steps: int = 20
    max_llm_calls: int = 8
    max_tool_calls: int = 10
    max_retrievals: int = 4
    max_subagents: int = 3

    # -----------------------------
    # Current Usage
    # -----------------------------

    steps: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    retrievals: int = 0
    subagents: int = 0

    @staticmethod
    def _consume(
        *,
        budget_name: str,
        current: int,
        limit: int,
        amount: int,
    ) -> int:
        if amount <= 0:
            raise ValueError("amount 必须大于 0")

        new_value = current + amount

        if new_value > limit:
            raise BudgetExceeded(
                budget_name=budget_name,
                used=new_value,
                limit=limit,
            )

        return new_value

    def consume_step(
        self,
        amount: int = 1,
    ) -> None:
        self.steps = self._consume(
            budget_name="step",
            current=self.steps,
            limit=self.max_steps,
            amount=amount,
        )

    def consume_llm_call(
        self,
        amount: int = 1,
    ) -> None:
        self.llm_calls = self._consume(
            budget_name="llm_call",
            current=self.llm_calls,
            limit=self.max_llm_calls,
            amount=amount,
        )

    def consume_tool_call(
        self,
        amount: int = 1,
    ) -> None:
        self.tool_calls = self._consume(
            budget_name="tool_call",
            current=self.tool_calls,
            limit=self.max_tool_calls,
            amount=amount,
        )

    def consume_retrieval(
        self,
        amount: int = 1,
    ) -> None:
        self.retrievals = self._consume(
            budget_name="retrieval",
            current=self.retrievals,
            limit=self.max_retrievals,
            amount=amount,
        )

    def consume_subagent(
        self,
        amount: int = 1,
    ) -> None:
        self.subagents = self._consume(
            budget_name="subagent",
            current=self.subagents,
            limit=self.max_subagents,
            amount=amount,
        )

    def snapshot(
        self,
    ) -> dict[str, int]:
        """
        给 Trace / API / Evaluation 使用的预算快照。
        """
        return {
            "steps": self.steps,
            "max_steps": self.max_steps,
            "llm_calls": self.llm_calls,
            "max_llm_calls": self.max_llm_calls,
            "tool_calls": self.tool_calls,
            "max_tool_calls": self.max_tool_calls,
            "retrievals": self.retrievals,
            "max_retrievals": self.max_retrievals,
            "subagents": self.subagents,
            "max_subagents": self.max_subagents,
        }
