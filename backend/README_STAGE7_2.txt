RecallFlow Stage 7.2 — Docker Build Fix
=======================================

问题：
Docker build 长时间停在 pip install。

原因候选：
1. VPN / Proxy 到 PyPI / download.pytorch.org 不稳定
2. sentence-transformers 间接安装 PyTorch
3. 默认 Linux PyTorch 依赖体积较大

本次修改：
- 显式安装 CPU-only PyTorch
- 不引入 CUDA/NVIDIA Runtime
- pip timeout 提高到 120 秒
- 打开 pip progress bar

覆盖：
Dockerfile

推荐执行顺序：

1. 停掉当前卡住的 build：

Ctrl + C

2. 先测试容器内部能否访问 PyPI：

docker run --rm python:3.12-slim python -c "import urllib.request; print(urllib.request.urlopen('https://pypi.org/simple/pip/', timeout=20).status)"

正常：
200

3. 测试 PyTorch CPU 源：

docker run --rm python:3.12-slim python -c "import urllib.request; print(urllib.request.urlopen('https://download.pytorch.org/whl/cpu/', timeout=20).status)"

正常：
200

4. 用正确的 Compose progress 参数：

docker compose --progress=plain build

5. Build 成功以后：

docker compose up

6. 验证：

http://127.0.0.1:8000/health

如果第 2 或第 3 步 timeout：
这是 Docker 容器内部网络 / VPN Proxy 问题，
不是 RecallFlow Python 代码问题。
