# Failure Cases

这些不是假设场景，而是开发过程中真实暴露的问题。

## 1. Groq 429 Rate Limit

现象：
- Memory Agent 的 LLM 节点触发 429。
- 一次 Agent Run 可能包含 Grade、Answer、Synthesis 等多次模型调用。

处理：
- LLM Error Classification。
- 429 / timeout / 5xx 仅作为 transient failure 重试。
- 指数退避。
- Logical LLM Call 与 HTTP Retry Attempt 分开统计。
- Trace 记录 rate_limited。
- Answer/Synthesis 支持 Graceful Degradation。

## 2. Conversation Context Pollution

现象：
- 第二轮用户只说“继续这个方向”。
- 将完整 Prompt Scaffold 送入 Rule Router 后，
  “当前用户请求”中的“当前”误触发 Research 路由。

处理：
- Routing Query 与 Execution Query 分离。
- Query Resolution 把省略式追问恢复为 standalone query。
- Retrieval 不再直接吃完整 Thread Prompt。

## 3. SQLAlchemy PendingRollbackError

现象：
- Agent 内数据库事务失败后，
  Conversation Service 直接尝试写 failed checkpoint。
- Session 已处于 failed transaction，
  导致 PendingRollbackError 覆盖原始异常。

处理：
- 进入 failure boundary 后先 rollback。
- 重新读取已提前 commit 的 checkpoint。
- 写入 failed 状态并 commit。
- 最后重新抛出原始异常。

## 4. Embedding Cold Start

现象：
- DenseSearcher 重复初始化 SentenceTransformer。
- 开发 Benchmark 中 Cold Run 约 13.6 秒。

处理：
- 进程级 Embedding Model Cache。
- Corpus Embedding Cache。
- 同一进程 Warm Run 开发 Benchmark 约 14ms。
- 该数字只代表 Retrieval Cache Benchmark，不代表端到端 Agent latency。
