from sentence_transformers.util import (
    cos_sim,
)

from app.retrieval.document import (
    RetrievalDocument,
)
from app.retrieval.embedding_model import (
    MODEL_NAME,
    get_corpus_embeddings,
    get_embedding_model,
)


class DenseSearcher:
    """
    Dense Retrieval
    = 稠密向量 / 语义检索。

    作用：
    用户表达和历史文本字面不同，
    但语义相近时仍然能够召回。

    性能优化：
    - Embedding Model 进程级复用
    - 相同 Corpus Embedding 复用
    """

    MODEL_NAME = MODEL_NAME

    def __init__(
        self,
        documents: list[
            RetrievalDocument
        ],
    ):
        if not documents:
            raise ValueError(
                "DenseSearcher requires "
                "at least one document"
            )

        self.documents = documents

        self.model = (
            get_embedding_model()
        )

        self.texts = tuple(
            document.text
            for document
            in documents
        )

        self.embeddings = (
            get_corpus_embeddings(
                self.texts
            )
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[
        tuple[
            RetrievalDocument,
            float,
        ]
    ]:
        query_embedding = (
            self.model.encode(
                query,
                convert_to_tensor=True,
                normalize_embeddings=True,
            )
        )

        scores = cos_sim(
            query_embedding,
            self.embeddings,
        )[0]

        ranked_indexes = (
            scores.argsort(
                descending=True
            )[:top_k]
        )

        results = []

        for index in (
            ranked_indexes
        ):
            i = int(index)

            results.append(
                (
                    self.documents[i],
                    float(scores[i]),
                )
            )

        return results
