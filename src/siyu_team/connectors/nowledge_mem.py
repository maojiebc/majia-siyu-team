"""Nowledge Mem 连接器（预留接口，未接入）。接在：四官 skill 检索。
马甲真实 SOP 语义检索（护城河 RAG 取数）

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 memory_search。【接入时填】
"""


def call(*args, **kwargs):
    raise NotImplementedError("接入 Nowledge Mem 时实现：memory_search")
