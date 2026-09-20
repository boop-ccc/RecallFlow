from dataclasses import dataclass


@dataclass
class RetrievalDocument:
    """
    RetrievalDocument = 检索文档。

    一个 WorkSession 在检索系统中的表示。
    """

    # WorkSession ID
    session_id: str

    # 给用户 / Agent 展示的标题
    title: str

    # 真正参与 BM25 / Dense 检索的文本
    text: str