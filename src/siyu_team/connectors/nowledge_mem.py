"""Nowledge Mem 连接器（预留接口，未接入）。接在：四官 skill 检索。
马甲真实 SOP 语义检索（护城河 RAG 取数）

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 memory_search。【接入时填】
"""


from .base import ConnectorNotImplemented, require_secret

POINTER = "keychain:siyu-team/nowledge_mem"


def call(*args, **kwargs):
    # keychain 骨架已就绪：先解析密钥（环境变量 / macOS keychain），再接具体 API。
    require_secret(POINTER, "Nowledge Mem", "SIYU_NOWLEDGE_MEM_TOKEN")
    raise ConnectorNotImplemented("Nowledge Mem 密钥已解析；memory_search 调用接入时实现。")
