class LLMError(RuntimeError):
    """
    LLM 调用层的基础异常。

    业务 Agent 不需要理解具体 HTTP 细节，
    只需要根据异常类型决定：
    - 是否重试
    - 是否降级
    - 是否直接失败
    """


class LLMTransientError(LLMError):
    """
    暂时性错误。

    例如：
    - 429 Rate Limit
    - Timeout
    - 502 / 503 / 504

    这类错误通常可以重试或做 Graceful Degradation。
    """


class LLMRateLimitError(LLMTransientError):
    def __init__(
        self,
        *,
        remaining_requests: str | None = None,
        remaining_tokens: str | None = None,
    ) -> None:
        self.remaining_requests = remaining_requests
        self.remaining_tokens = remaining_tokens

        super().__init__(
            "LLM Provider 触发 Rate Limit（429）。"
            f" remaining_requests={remaining_requests},"
            f" remaining_tokens={remaining_tokens}"
        )


class LLMTimeoutError(LLMTransientError):
    pass


class LLMProviderError(LLMTransientError):
    def __init__(
        self,
        *,
        status_code: int,
        message: str,
    ) -> None:
        self.status_code = status_code

        super().__init__(
            f"LLM Provider 暂时不可用："
            f"HTTP {status_code} | {message}"
        )
