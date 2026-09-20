import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    """
    通用重试策略。

    注意：
    Retry 不是“所有错误都重试”。

    只有暂时性错误，例如：
    - timeout
    - 429
    - 502/503/504

    才适合重试。

    权限错误、参数错误、Schema 错误等
    通常不应该通过重试解决。
    """

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0

    def delay_for(
        self,
        attempt: int,
    ) -> float:
        if attempt <= 0:
            raise ValueError(
                "attempt 必须从 1 开始"
            )

        delay = (
            self.base_delay_seconds
            * (2 ** (attempt - 1))
        )

        return min(
            delay,
            self.max_delay_seconds,
        )

    async def run(
        self,
        operation: Callable[
            [],
            Awaitable[T],
        ],
        *,
        retry_on: tuple[
            type[BaseException],
            ...,
        ],
    ) -> T:
        last_error: BaseException | None = None

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            try:
                return await operation()

            except retry_on as exc:
                last_error = exc

                if (
                    attempt
                    == self.max_attempts
                ):
                    raise

                await asyncio.sleep(
                    self.delay_for(
                        attempt
                    )
                )

        assert last_error is not None
        raise last_error
