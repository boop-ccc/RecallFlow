import asyncio
import json
import time

import httpx

from app.core.config import settings
from app.llm.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.runtime.context import (
    get_run_context,
)


class LLMClient:
    """
    LLM Client = 模型访问层。

    它不负责 Memory / Research 业务，
    只负责所有 Agent 共享的模型调用能力：

    1. OpenAI-compatible HTTP 请求
    2. JSON 输出解析
    3. Timeout
    4. 429 / 5xx Retry
    5. LLM Call Budget
    6. Trace
    7. Token Usage 采集
    """

    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:
        context = get_run_context()

        # ----------------------------------
        # Logical LLM Call Budget
        # ----------------------------------
        #
        # 一次 generate_json 算一次“逻辑调用”。
        # HTTP retry 不重复消耗 llm_call budget，
        # 否则 Provider 的网络抖动会扭曲 Agent 预算。
        # ----------------------------------

        if context is not None:
            context.budget.consume_llm_call()

            context.trace.record(
                component="llm",
                action="generate_json",
                status="started",
                detail={
                    "model":
                        settings.llm_model,
                    "system_chars":
                        len(system_prompt),
                    "user_chars":
                        len(user_prompt),
                    "llm_call":
                        context.budget.llm_calls,
                },
            )

        if not settings.llm_api_key:
            raise RuntimeError(
                "没有配置 LLM_API_KEY / GROQ_API_KEY"
            )

        if not settings.llm_base_url:
            raise RuntimeError(
                "没有配置 LLM_BASE_URL"
            )

        if not settings.llm_model:
            raise RuntimeError(
                "没有配置 LLM_MODEL"
            )

        url = (
            settings.llm_base_url.rstrip("/")
            + "/chat/completions"
        )

        chinese_instruction = """
重要语言要求：

- 所有解释、总结、原因、回答必须使用中文。
- 技术名词可以保留英文，例如 LangGraph、Memory、BM25。
- JSON 的 key 保持程序要求的英文名称。
- JSON 中自然语言 value 必须使用中文。
""".strip()

        final_system_prompt = (
            chinese_instruction
            + "\n\n"
            + system_prompt.strip()
        )

        payload = {
            "model": settings.llm_model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": final_system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        }

        headers = {
            "Authorization": (
                f"Bearer {settings.llm_api_key}"
            ),
            "Content-Type": "application/json",
        }

        max_attempts = 3
        started = time.perf_counter()

        async with httpx.AsyncClient(
            timeout=settings.llm_timeout_seconds
        ) as client:

            for attempt in range(
                1,
                max_attempts + 1,
            ):
                try:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )

                except httpx.TimeoutException as exc:
                    if context is not None:
                        context.trace.record(
                            component="llm",
                            action="http_attempt",
                            status="timeout",
                            detail={
                                "attempt": attempt,
                            },
                        )

                    if attempt == max_attempts:
                        self._record_final_failure(
                            started=started,
                            error_type="timeout",
                        )

                        raise LLMTimeoutError(
                            "LLM 请求连续超时，"
                            "已达到最大重试次数。"
                        ) from exc

                    await asyncio.sleep(
                        2 ** attempt
                    )
                    continue

                # ----------------------------------
                # 429 Rate Limit
                # ----------------------------------

                if response.status_code == 429:
                    remaining_requests = (
                        response.headers.get(
                            "x-ratelimit-remaining-requests"
                        )
                    )

                    remaining_tokens = (
                        response.headers.get(
                            "x-ratelimit-remaining-tokens"
                        )
                    )

                    retry_after = (
                        response.headers.get(
                            "retry-after"
                        )
                    )

                    try:
                        delay = (
                            float(retry_after)
                            if retry_after
                            else float(2 ** attempt)
                        )
                    except ValueError:
                        delay = float(
                            2 ** attempt
                        )

                    if context is not None:
                        context.trace.record(
                            component="llm",
                            action="http_attempt",
                            status="rate_limited",
                            detail={
                                "attempt": attempt,
                                "delay_seconds": delay,
                                "remaining_requests":
                                    remaining_requests,
                                "remaining_tokens":
                                    remaining_tokens,
                            },
                        )

                    if attempt == max_attempts:
                        self._record_final_failure(
                            started=started,
                            error_type="rate_limit",
                        )

                        raise LLMRateLimitError(
                            remaining_requests=(
                                remaining_requests
                            ),
                            remaining_tokens=(
                                remaining_tokens
                            ),
                        )

                    print(
                        f"Groq 触发限流，"
                        f"{delay:.1f} 秒后重试..."
                        f"({attempt}/{max_attempts})"
                    )

                    await asyncio.sleep(delay)
                    continue

                # ----------------------------------
                # Temporary Provider Errors
                # ----------------------------------

                if response.status_code in {
                    500,
                    502,
                    503,
                    504,
                }:
                    if context is not None:
                        context.trace.record(
                            component="llm",
                            action="http_attempt",
                            status="provider_error",
                            detail={
                                "attempt": attempt,
                                "status_code":
                                    response.status_code,
                            },
                        )

                    if attempt == max_attempts:
                        self._record_final_failure(
                            started=started,
                            error_type="provider_error",
                        )

                        raise LLMProviderError(
                            status_code=(
                                response.status_code
                            ),
                            message=(
                                response.text[:300]
                            ),
                        )

                    await asyncio.sleep(
                        2 ** attempt
                    )
                    continue

                # 其他 HTTP 错误通常不是暂时性错误，
                # 直接抛给上层定位配置/请求问题。
                response.raise_for_status()

                data = response.json()

                content = (
                    data["choices"][0]
                    ["message"]
                    ["content"]
                )

                result = self._parse_json(
                    content
                )

                latency_ms = (
                    time.perf_counter()
                    - started
                ) * 1000

                usage = (
                    data.get("usage")
                    or {}
                )

                if context is not None:
                    context.trace.record(
                        component="llm",
                        action="generate_json",
                        status="success",
                        latency_ms=latency_ms,
                        detail={
                            "attempts": attempt,
                            "prompt_tokens":
                                usage.get(
                                    "prompt_tokens"
                                ),
                            "completion_tokens":
                                usage.get(
                                    "completion_tokens"
                                ),
                            "total_tokens":
                                usage.get(
                                    "total_tokens"
                                ),
                        },
                    )

                return result

        raise RuntimeError(
            "LLM 请求失败"
        )

    @staticmethod
    def _parse_json(
        content: str,
    ) -> dict:
        """
        Structured Output Parser
        = 结构化输出解析。
        """

        text = content.strip()

        if text.startswith("```json"):
            text = text[7:]

        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            return json.loads(text)

        except json.JSONDecodeError as exc:
            raise ValueError(
                "LLM 没有返回合法 JSON。\n"
                f"原始输出：\n{text[:1000]}"
            ) from exc

    @staticmethod
    def _record_final_failure(
        *,
        started: float,
        error_type: str,
    ) -> None:
        context = get_run_context()

        if context is None:
            return

        latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        context.trace.record(
            component="llm",
            action="generate_json",
            status="failed",
            latency_ms=latency_ms,
            detail={
                "error_type":
                    error_type,
            },
        )
