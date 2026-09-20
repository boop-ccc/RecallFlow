RecallFlow Chrome Extension
===========================

1. 先启动后端：

uvicorn app.main:app --reload

2. Chrome 打开：

chrome://extensions

3. 开启 Developer mode

4. Load unpacked

5. 选择：
backend\chrome_extension

6. 打开普通网页，点击 RecallFlow 图标。

功能：
- Capture this page
  采集当前 URL / title / body text / timestamp

- Ask RecallFlow
  调用 POST /api/v1/ask

- New thread
  清理 Chrome local storage 中的 thread_id

注意：
chrome:// 页面、Chrome Web Store 等受保护页面
不允许普通 Extension 注入脚本，这是 Chrome 安全限制。
