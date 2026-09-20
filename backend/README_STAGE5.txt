RecallFlow Stage 5
Follow-up Query Resolution + Evaluation Foundation
==================================================

这一阶段做两件真正影响简历质量的事：

1. 修复长对话 Follow-up Retrieval
2. 建立可量化 Evaluation

新增：
app/services/query_resolution_service.py
app/evaluation/__init__.py
app/evaluation/metrics.py
app/evaluation/datasets.py
scripts/test_query_resolution.py
scripts/test_followup_flow.py
scripts/eval_routing.py
scripts/eval_retrieval.py
scripts/eval_traces.py

覆盖：
app/services/conversation_service.py

----------------------------------------
1. 语法检查
----------------------------------------

python -m py_compile app\services\query_resolution_service.py
python -m py_compile app\services\conversation_service.py
python -m py_compile app\evaluation\metrics.py
python -m py_compile app\evaluation\datasets.py
python -m py_compile scripts\test_query_resolution.py
python -m py_compile scripts\test_followup_flow.py
python -m py_compile scripts\eval_routing.py
python -m py_compile scripts\eval_retrieval.py
python -m py_compile scripts\eval_traces.py

----------------------------------------
2. Query Resolution
----------------------------------------

python -m scripts.test_query_resolution

重点看：

continue previous topic
Strategy: previous_user_anchor
Used History: True
Standalone:
我之前研究 Agent 长期记忆的时候看了什么；继续这个方向

----------------------------------------
3. 两轮真实对话
----------------------------------------

python -m scripts.test_followup_flow

期望：
TURN 2
Route: memory_only

并且不再因为整个 Thread Prompt 污染 Retrieval
而直接出现“证据不足”。

----------------------------------------
4. Routing Evaluation
----------------------------------------

python -m scripts.eval_routing

这一步完全不调用 Groq。

输出真实：
Rule Coverage
Rule Accuracy

----------------------------------------
5. Retrieval Evaluation
----------------------------------------

python -m scripts.eval_retrieval

会比较：
BM25
Dense
Hybrid

指标：
Recall@1
Recall@3
MRR
nDCG@3

数字跑出来多少写多少，不造指标。

----------------------------------------
6. Trace Evaluation
----------------------------------------

python -m scripts.eval_traces

从 artifacts/traces/*.jsonl 统计真实：
Run Success Rate
Mean / p50 / p95 Latency
LLM Calls
Tool Calls
Rate-limit Events
Degraded Events
Token Usage
