from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResolution:
    """
    QueryResolution
    = 长对话追问解析结果。
    """

    original_query: str
    standalone_query: str
    routing_query: str
    used_history: bool
    strategy: str


class QueryResolutionService:
    """
    Query Resolution Service
    = 长对话追问解析层。

    目标：
    把“继续这个方向 / 再详细说 / 为什么？”
    这类依赖上一轮的问题，恢复成可独立理解的 Query。

    第一版优先确定性规则：
    - 不增加额外 LLM Call
    - 低延迟
    - 可稳定回归测试
    """

    _FOLLOW_UP_PREFIXES = (
        "继续",
        "接着",
        "展开",
        "详细说",
        "再详细说",
        "再讲",
        "再说",
        "然后呢",
        "还有呢",
    )

    _REFERENCE_HINTS = (
        "这个",
        "那个",
        "这些",
        "它",
        "刚才",
        "上面",
        "前面",
        "这个方向",
        "那个方向",
        "这个方案",
        "那个方案",
    )

    @staticmethod
    def _last_user_message(
        turns,
    ) -> str | None:
        for turn in reversed(turns):
            if turn.role == "user":
                return turn.content.strip()

        return None

    @classmethod
    def _is_follow_up(
        cls,
        message: str,
    ) -> bool:
        text = message.strip()

        if any(
            text.startswith(prefix)
            for prefix in cls._FOLLOW_UP_PREFIXES
        ):
            return True

        if any(
            hint in text
            for hint in cls._REFERENCE_HINTS
        ):
            return True

        if (
            len(text) <= 10
            and text.endswith(
                ("？", "?")
            )
        ):
            return True

        return False

    @staticmethod
    def _combine(
        previous_user: str,
        message: str,
    ) -> str:
        previous = previous_user.rstrip(
            "。！？!? "
        )

        current = message.strip()

        return (
            f"{previous}；{current}"
        )

    def resolve(
        self,
        *,
        turns,
        message: str,
    ) -> QueryResolution:
        original = message.strip()

        if not turns:
            return QueryResolution(
                original_query=original,
                standalone_query=original,
                routing_query=original,
                used_history=False,
                strategy="passthrough_no_history",
            )

        if not self._is_follow_up(
            original
        ):
            return QueryResolution(
                original_query=original,
                standalone_query=original,
                routing_query=original,
                used_history=False,
                strategy="passthrough_explicit_query",
            )

        previous_user = (
            self._last_user_message(
                turns
            )
        )

        if not previous_user:
            return QueryResolution(
                original_query=original,
                standalone_query=original,
                routing_query=original,
                used_history=False,
                strategy="passthrough_no_user_anchor",
            )

        standalone = self._combine(
            previous_user,
            original,
        )

        return QueryResolution(
            original_query=original,
            standalone_query=standalone,
            routing_query=standalone,
            used_history=True,
            strategy="previous_user_anchor",
        )
