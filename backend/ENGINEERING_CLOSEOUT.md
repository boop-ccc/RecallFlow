# Engineering Closeout

Run these in order.

## 1. Unit Tests

```cmd
pytest -q
```

## 2. Offline 75-Case Evaluation

```cmd
python -m scripts.eval_offline_suite
```

Expected output is NOT predetermined.
Record the real metrics.

## 3. Existing DB Retrieval Evaluation

```cmd
python -m scripts.eval_retrieval
```

This evaluates your current captured WorkSessions.

## 4. Runtime Trace Evaluation

```cmd
python -m scripts.eval_traces
```

## 5. Retrieval Cache Benchmark

```cmd
python -m scripts.benchmark_retrieval_cache
```

## 6. FastAPI

```cmd
uvicorn app.main:app --reload
```

Check:

```text
http://127.0.0.1:8000/docs
```

## 7. Chrome Extension

Capture at least several real technical pages.
Then rebuild / enrich WorkSessions using your existing scripts.

## 8. Docker

Docker Desktop running:

```cmd
docker compose up --build
```

Check:

```text
http://127.0.0.1:8000/health
```

## 9. GitHub CI

Push repository to GitHub.
The workflow `.github/workflows/ci.yml` should run:

```text
ruff
pytest
```

## 10. Before Resume

Only after the above outputs are real:

- freeze final metrics
- rewrite README benchmark section
- create resume bullets
- create interview question bank
