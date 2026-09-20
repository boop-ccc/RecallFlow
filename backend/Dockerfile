FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

COPY requirements-ci.txt .

# RecallFlow 的 SentenceTransformer 只做 CPU Embedding，
# 不需要 CUDA / NVIDIA Runtime。
#
# 先显式安装 CPU-only PyTorch，
# 避免 sentence-transformers 从默认 PyPI
# 拉取体积巨大的 GPU/CUDA 依赖。
RUN python -m pip install --upgrade pip --progress-bar on \
    && python -m pip install \
        --index-url https://download.pytorch.org/whl/cpu \
        torch \
        --progress-bar on \
    && python -m pip install \
        -r requirements-ci.txt \
        --progress-bar on

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python -m scripts.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
