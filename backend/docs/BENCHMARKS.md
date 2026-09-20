# Benchmarks

## 已验证的开发阶段结果

### Follow-up Conversation

第二轮：

```text
用户：继续这个方向
Route: memory_only
Verification: verified
```

说明 Query Resolution 已能把省略式追问重新绑定到上一轮 Memory Intent，
并成功重新召回 WorkSession。

### Routing Smoke Evaluation

```text
Cases: 15
Rule Coverage: 100%
Rule Accuracy: 100%
```

注意：这是小规模高置信规则集，不是生产泛化准确率。

### Two-WorkSession Retrieval Smoke Test

```text
BM25:
Recall@1  = 0.375
Recall@3  = 1.000
MRR       = 0.6875
nDCG@3    = 0.7693

Dense:
Recall@1  = 1.000
Recall@3  = 1.000
MRR       = 1.000
nDCG@3    = 1.000

Hybrid:
Recall@1  = 0.375
Recall@3  = 1.000
MRR       = 0.6875
nDCG@3    = 0.7693
```

注意：
数据库只有两个 WorkSession。两路排名相反时 RRF 会打平，
因此 Hybrid 结果会受到 tie-breaking 影响。
该测试只作为 Smoke Evaluation。

### Trace Smoke Evaluation

```text
Trace Files: 2
Completed Runs: 2
Successful Runs: 2
Run Success Rate: 100%
Mean Latency: 23962.3 ms
p50: 23431.5 ms
p95: 24493.1 ms
Logical LLM Calls: 4
Tool Calls: 2
Rate-limit Events: 1
Recorded LLM Tokens: 4292
```

样本只有两个 Run，不作为最终 latency 指标。

### Retrieval Cache Benchmark

```text
Cold Run: 13559.0 ms
Warm Run: 14.3 ms
Warm / Cold Ratio: 0.001
```

解释：
Cold Run 包含 SentenceTransformer 首次加载和 Corpus Embedding；
Warm Run 复用模型和文档向量。

这不是端到端 Agent latency。
