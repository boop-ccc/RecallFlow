# Demo Script

## Demo 1 — Capture

1. 启动 FastAPI。
2. Chrome 打开一篇技术文档。
3. 点击 RecallFlow Extension。
4. 点击 `Capture this page`。
5. 后端产生 Resource / Snapshot / ActivityEvent。

## Demo 2 — Historical Recovery

输入：

```text
我之前研究 Agent Memory 的时候看了什么？
```

观察：

```text
Supervisor
→ memory_only

Memory Agent
→ search_memory

Hybrid Retrieval
→ Top WorkSession

Verifier
→ verified
```

## Demo 3 — Follow-up

继续输入：

```text
继续这个方向
```

展示：

```text
Conversation Thread
→ Query Resolution
→ standalone query
→ Memory Retrieval
→ verified answer
```

## Demo 4 — Memory + Fresh Research

输入：

```text
继续我之前关于 Agent Memory 的研究，
再看看现在有没有新的方案。
```

展示：

```text
Supervisor
→ memory_and_research

Memory Agent ─┐
              ├─ concurrent
Research Agent┘

Verifier
→ final answer
```

## Demo 5 — Failure Case

展示一份 Trace：

```text
llm -> http_attempt -> rate_limited
llm -> retry
llm -> success
```

说明 Runtime 不把 Provider 波动当业务逻辑错误。
