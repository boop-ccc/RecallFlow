from functools import lru_cache

from sentence_transformers import (
    SentenceTransformer,
)


MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


@lru_cache(maxsize=1)
def get_embedding_model(
) -> SentenceTransformer:
    """
    Embedding Model Cache
    = Embedding 模型进程级缓存。

    原问题：
    每创建一个 DenseSearcher，
    都重新加载一次 SentenceTransformer，
    导致每个请求出现明显 Cold Start。

    现在：
    同一个 Python 进程只加载一次模型。
    """
    return SentenceTransformer(
        MODEL_NAME
    )


@lru_cache(maxsize=8)
def get_corpus_embeddings(
    texts: tuple[str, ...],
):
    """
    Corpus Embedding Cache
    = WorkSession 文档向量缓存。

    相同 WorkSession 文本集合在同一进程中
    不重复编码。

    当 WorkSession 内容变化时，
    texts tuple 变化，会自然产生新的缓存项。
    """

    model = get_embedding_model()

    return model.encode(
        list(texts),
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
