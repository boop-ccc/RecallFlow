RecallFlow Stage 6
API + Chrome Extension + Retrieval Cache + pytest
=================================================

这轮解决三个项目落地问题：

1. 性能：
   SentenceTransformer 不再每次请求重新加载。

2. 产品入口：
   POST /api/v1/ask
   POST /api/v1/threads/{thread_id}/retry

3. 真实数据入口：
   最小 Chrome Extension 可直接 Capture 当前页面，
   并在 popup 中调用 RecallFlow。

新增/覆盖：
app/retrieval/embedding_model.py
app/retrieval/search/dense_search.py
app/api/routes/conversation.py
app/main.py
scripts/benchmark_retrieval_cache.py
tests/test_query_resolution.py
tests/test_evaluation_metrics.py
tests/test_permissions.py
chrome_extension/*

----------------------------------------
1. 语法
----------------------------------------

python -m py_compile app\retrieval\embedding_model.py
python -m py_compile app\retrieval\search\dense_search.py
python -m py_compile app\api\routes\conversation.py
python -m py_compile app\main.py
python -m py_compile scripts\benchmark_retrieval_cache.py

----------------------------------------
2. pytest
----------------------------------------

pytest -q

----------------------------------------
3. 性能测试
----------------------------------------

python -m scripts.benchmark_retrieval_cache

重点比较：
Cold Run
Warm Run

----------------------------------------
4. FastAPI
----------------------------------------

uvicorn app.main:app --reload

浏览：
http://127.0.0.1:8000/docs

应该看到：
GET  /health
POST /api/v1/capture
POST /api/v1/ask
POST /api/v1/threads/{thread_id}/retry

----------------------------------------
5. Chrome Extension
----------------------------------------

Chrome:
chrome://extensions
→ Developer mode
→ Load unpacked
→ 选择 backend/chrome_extension

然后：
Capture this page
Ask RecallFlow
