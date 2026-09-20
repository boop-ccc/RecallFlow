# RecallFlow

**Personal Work-Recovery Multi-Agent System**

> Recover what you were doing, not just what you visited.

RecallFlow 将碎片化浏览行为重建为可检索的 WorkSession，
并在用户后续提问时恢复历史工作上下文；
需要最新信息时，再由 Research Agent 查询公开互联网，
最终经过 Verifier 的 Evidence Boundary 后返回结果。

## Architecture

```text
Chrome Extension
真实浏览采集 / 用户入口
        ↓
FastAPI
HTTP API
        ↓
Resource / Snapshot / ActivityEvent
原始数据建模
        ↓
WorkSession Reconstruction
历史工作重建
        ↓
Episodic Memory
长期工作记忆
        ↓
BM25 + Dense + RRF
Hybrid Retrieval
        ↓
Supervisor
Hybrid Routing
        ↓
 ┌───────────────┐
 ▼               ▼
Memory Agent   Research Agent
私人历史        公开互联网
 └───────┬───────┘
         ▼
Verifier Agent
Evidence Boundary
         ↓
Final Answer
```

详细架构见 `docs/ARCHITECTURE.md`。

## Engineering Highlights

- Resource / Snapshot / ActivityEvent 分层建模。
- `client_event_id` 保证 Capture Idempotency。
- 30 分钟 Time-gap Sessionization 重建 WorkSession。
- WorkSession title / summary / keywords / open_tasks 形成 Episodic Memory。
- BM25 + Dense Retrieval + RRF。
- LangGraph Memory Agent：Retrieve → Grade → Rewrite → Retrieve → Answer。
- Supervisor Hybrid Routing：确定性高置信规则 + 模糊语义 LLM Router。
- Memory / Research 按 Context / Tool / Permission Domain 隔离。
- `asyncio.gather` 并发执行独立 Sub-Agent。
- Verifier 做 deterministic Evidence Boundary。
- Runtime Harness 统一 Step / LLM / Tool / Retrieval Budget、Timeout、Permission、Trace。
- 429 / timeout / 5xx Retry 与 Graceful Degradation。
- Conversation Thread、WorkSession、RunCheckpoint 三类状态分离。
- Follow-up Query Resolution 解决“继续这个方向”等省略式追问。
- SentenceTransformer 与 Corpus Embedding 进程级缓存。
- Chrome Extension 真实采集 URL / title / page text / timestamp。
- FastAPI 对外提供 Capture / Ask / Retry API。
- pytest + Ruff + GitHub Actions + Docker Compose。

## Local Run

```bash
python -m scripts.init_db
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Main APIs:

```text
GET  /health
POST /api/v1/capture
POST /api/v1/ask
POST /api/v1/threads/{thread_id}/retry
```

## Chrome Extension

Chrome:

```text
chrome://extensions
→ Developer mode
→ Load unpacked
→ select chrome_extension/
```

Functions:

```text
Capture this page
Ask RecallFlow
New thread
```

## Docker Compose

Create `.env` from `.env.example` and fill `GROQ_API_KEY`.

```bash
docker compose up --build
```

Compose includes:

```text
backend
FastAPI + RecallFlow

postgres
PostgreSQL 16

hf_cache
Hugging Face model cache
```

Local development can still use SQLite.

## Tests

```bash
pytest -q
```

CI also runs fatal Ruff correctness checks.

## Evaluation

Controlled offline suite:

```bash
python -m scripts.eval_offline_suite
```

It contains **75 unique controlled cases**:

```text
30 Routing
15 Query Resolution
30 Retrieval
```

Retrieval compares:

```text
BM25
Dense
Hybrid
```

Metrics:

```text
Recall@1
Recall@3
MRR
nDCG@3
```

Trace evaluation:

```bash
python -m scripts.eval_traces
```

Runtime metrics include:

```text
Run Success Rate
p50 / p95 latency
Logical LLM Calls
Tool Calls
Rate-limit Events
Degraded Events
Token Usage
```

The offline suite is a controlled reproducible benchmark,
not a substitute for real browsing-data evaluation.

## Development Measurements

Current development measurements and their limitations are recorded in:

```text
docs/BENCHMARKS.md
```

Do not treat the small two-WorkSession smoke test as a production metric.

## Failure Cases

Real engineering failures encountered during development:

- Groq 429 rate limit.
- Conversation context polluted rule routing.
- SQLAlchemy failed transaction caused `PendingRollbackError`.
- Repeated SentenceTransformer cold start.

See:

```text
docs/FAILURE_CASES.md
```

## Demo

See:

```text
docs/DEMO.md
```

## Core Design Principle

RecallFlow does not give probabilistic models responsibilities that can be solved deterministically.

```text
Database constraints
Permission checks
Budgets
Timeouts
URL / Session validation
High-confidence routing rules
```

remain deterministic.

LLMs are used where semantic reasoning is actually needed:

```text
WorkSession semantic enrichment
Evidence grading
Ambiguous routing
Answer generation
Cross-source synthesis
```
