import re

from rank_bm25 import BM25Okapi

from app.retrieval.document import RetrievalDocument


def tokenize(text: str) -> list[str]:
    """
    Tokenize = 分词。

    第一版简单支持：
    - 英文
    - 数字
    - 技术符号
    - 中文字符

    Demo 足够，不做复杂中文分词系统。
    """

    return re.findall(
        r"[A-Za-z0-9_./-]+|[\u4e00-\u9fff]",
        text.lower(),
    )


class BM25Searcher:
    """
    BM25 = 关键词检索。

    擅长精确技术词：
    LangGraph
    FastAPI
    async_sessionmaker
    Qwen
    """

    def __init__(
        self,
        documents: list[RetrievalDocument],
    ):
        self.documents = documents

        # 把所有文档进行分词
        corpus = [
            tokenize(doc.text)
            for doc in documents
        ]

        # 建立 BM25 Index（索引）
        self.index = BM25Okapi(corpus)

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[RetrievalDocument, float]]:
        """
        Query = 用户查询。

        返回 BM25 排名前 top_k 的文档。
        """

        query_tokens = tokenize(query)

        scores = self.index.get_scores(
            query_tokens
        )

        ranked = sorted(
            zip(self.documents, scores),
            key=lambda item: item[1],
            reverse=True,
        )

        return [
            (document, float(score))
            for document, score
            in ranked[:top_k]
        ]