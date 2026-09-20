RecallFlow Stage 7.1
Evaluation-driven Quality Fix
================================

这次不是加新功能，而是根据真实 Evaluation 修两个问题。

1. Query Resolution
-------------------

75-case 结果：
93.33% = 14 / 15

唯一失败：
“再详细说”

原因：
Follow-up Prefix 没包含这个表达。

修复后重新运行：

python -m scripts.eval_offline_suite

目标：
Query Resolution Accuracy 应重新验证。
不要预设最终数字，以真实输出为准。

2. Hybrid Retrieval
-------------------

原 Controlled Offline Benchmark：

BM25 Recall@1   0.8000
Dense Recall@1  0.9000
Hybrid Recall@1 0.8333

说明 Equal-weight RRF 在当前中英混合语义查询上
把较强的 Dense Ranking 拉低了。

现在 Production Hybrid 改成 Weighted RRF：

BM25 weight  = 1.0
Dense weight = 2.0

原因：
- Dense 保持跨语言语义召回优势
- BM25 仍为技术精确词提供 lexical signal
- 仍使用 rank fusion，不直接相加不同 score scale

重新运行：

pytest -q
python -m scripts.eval_offline_suite
python -m scripts.eval_retrieval

最终使用真实新结果，不假定一定提升。
