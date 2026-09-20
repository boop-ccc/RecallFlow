import pytest

from app.runtime.budget import (
    BudgetExceeded,
    RunBudget,
)


def test_llm_budget():
    budget = RunBudget(
        max_llm_calls=1
    )

    budget.consume_llm_call()

    with pytest.raises(
        BudgetExceeded
    ):
        budget.consume_llm_call()


def test_tool_budget():
    budget = RunBudget(
        max_tool_calls=1
    )

    budget.consume_tool_call()

    with pytest.raises(
        BudgetExceeded
    ):
        budget.consume_tool_call()
