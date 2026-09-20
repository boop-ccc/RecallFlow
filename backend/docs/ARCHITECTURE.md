# RecallFlow Architecture

```text
Chrome Extension
浏览器插件
作用：采集真实网页 + 提供用户查询入口
        ↓

FastAPI
HTTP 服务入口
作用：/capture、/ask、/retry
        ↓

Capture / Conversation Service
业务层
作用：事务、Thread、Query Resolution、Checkpoint
        ↓

Resource / Snapshot / ActivityEvent
原始行为数据层
作用：资源身份、内容版本、用户行为
        ↓

WorkSession Reconstruction
工作会话重建
作用：把零散 Activity 组织成历史工作经历
        ↓

Episodic Memory
长期情景记忆
作用：保存 title / summary / keywords / evidence
        ↓

Hybrid Retrieval
BM25 + Dense + RRF
作用：从历史 WorkSession 中召回相关记忆
        ↓

Supervisor
主管智能体
作用：Hybrid Routing + Sub-Agent 调度
        ↓
  ┌───────────────┐
  ▼               ▼

Memory Agent     Research Agent
记忆智能体       研究智能体
私人历史          公开互联网
search_memory     web_search / fetch_page
  └────────┬──────┘
           ▼

Verifier Agent
证据验证智能体
作用：检查 Route / Agent / Session / URL / Evidence Boundary
           ↓

Agent Runtime Harness
运行控制层
作用：Step / LLM / Tool / Retrieval Budget
     + Timeout + Retry + Permission + Trace
           ↓

Final Answer
最终可信结果
```

## 三类状态

```text
ConversationThread / Turn
短期对话状态
→ “继续这个方向”指什么

WorkSession
长期 Episodic Memory
→ “三天前研究什么”

RunCheckpoint
运行状态
→ 某次 Agent Run 成功 / 失败 / 是否可重放
```
