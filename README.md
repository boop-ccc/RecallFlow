# RecallFlow

一个面向技术调研场景的 **个人工作上下文恢复 Multi-Agent 系统**。

它不是简单记录“你访问过哪些网页”，而是尝试回答：

- 我刚才在做什么？
- 我之前研究过什么？
- 我上次做到哪里了？
- 继续这个方向。
- 继续之前的研究，并补充最新公开资料。

---

## ✨ 项目亮点

### 1. 从浏览行为重建 WorkSession

RecallFlow 会通过 Chrome 扩展采集真实浏览行为，并把离散页面访问组织成一段完整的工作会话：

```text
Chrome Capture
→ ActivityEvent
→ WorkSession
→ Episodic Memory
```

相比普通浏览器历史，它更关注：

> “这一段时间你在做什么工作”

而不是只保存一串 URL。

---

### 2. 支持“刚才做了什么”

对于：

```text
我刚才做了什么？
```

RecallFlow 会优先读取最近 Activity，而不是从整段历史里做模糊语义检索。

例如：

```text
你刚才主要在继续查看 arXiv 论文 2305.00673，
并在此之前多次使用 Groq。

最近活动时间线：
- 21:32、21:37：arXiv 论文 2305.00673
- 21:14、21:15、21:27：Groq
```

如果 LLM 暂时不可用，系统仍会退化为确定性的时间线结果。

---

### 3. WorkSession 级长期记忆

RecallFlow 使用 WorkSession 作为长期记忆单元，而不是把单个网页 Chunk 直接当成 Memory。

每个 WorkSession 可以包含：

```text
title
summary
keywords
open_tasks
```

用于恢复：

- 当时研究了什么
- 主要看了哪些资料
- 做到了哪里
- 还有什么没完成

---

### 4. Hybrid Retrieval

普通历史问题使用：

```text
BM25
+
Dense Retrieval
+
Weighted RRF
```

当前受控实验结果：

| 方法 | Recall@1 | Recall@3 |
|---|---:|---:|
| BM25 | 0.80 | 0.90 |
| Dense | 0.90 | 1.00 |
| Weighted RRF | 0.8667 | 1.00 |

---

### 5. Multi-Agent

RecallFlow 按数据边界拆分两个核心 Agent：

```text
Memory Agent
→ 用户私人历史 WorkSession

Research Agent
→ 当前公开互联网信息
```

由 Supervisor 在以下路径中选择：

```text
memory_only
research_only
memory_and_research
```

例如：

```text
继续我之前对 Agent Memory 的研究，
再看看现在有没有新的方案。
```

会同时调用 Memory Agent 和 Research Agent。

---

## 🧠 整体流程

```text
Chrome Extension
      ↓
ActivityEvent
      ↓
WorkSession
      ↓
Episodic Memory
      ↓

User Query
      ↓
Query Resolution
      ↓
Supervisor
   ↙       ↘
Memory    Research
 Agent      Agent
   ↘       ↙
   Final Answer
```

---

## 🛠 技术栈

- Python
- FastAPI
- LangGraph
- SQLAlchemy Async
- PostgreSQL / SQLite
- Sentence-Transformers
- BM25 + Weighted RRF
- asyncio
- Docker
- pytest
- Ruff

---

## 🚀 本地运行

进入后端目录：

```cmd
cd /d F:\hello_agents_study\recallflow_ma\backend
```

激活虚拟环境：

```cmd
.venv\Scripts\activate
```

启动服务：

```cmd
uvicorn app.main:app --reload
```

然后通过 Chrome 扩展进行：

```text
Capture
→ Ask
```

---

## 💬 示例问题

```text
我刚才做了什么？
```

```text
我之前研究 Agent 长期记忆的时候看了什么？
```

```text
我上次做到哪里了？
```

```text
继续这个方向。
```

```text
继续我之前研究的 Agent Memory，
再看看现在有没有新的公开资料。
```

---

## 📊 当前验证结果

```text
Routing：30 / 30
Query Resolution：15 / 15
pytest：18 passed
Ruff：All checks passed
```

---

## 🔧 已处理的真实工程问题

项目开发过程中实际处理过：

- Groq 429 限流与重试
- Docker 冷启动超时
- Follow-up 路由污染
- SQLAlchemy PendingRollbackError
- Chrome Capture 时间字段不一致
- WorkSession 增量更新
- LLM 不可用时的降级回答

---

## 🎯 项目定位

RecallFlow 想解决的不是：

> “我访问过哪些网页？”

而是：

> “我之前到底在做什么，以及现在该怎么继续？”

---

## 📌 一句话介绍

**RecallFlow 是一个通过真实浏览行为重建工作情景，并利用长期记忆与 Multi-Agent 帮助用户恢复被打断任务的个人工作上下文系统。**

---

## License

For learning and research purposes.
