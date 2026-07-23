"""Get笔记 连接器（预留接口，未接入）。接在：Step0 调研。
抓行业素材/竞品私域打法并入 00-intake.md

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 majia-getnote。【接入时填】
"""


from .base import ConnectorNotImplemented, require_secret

POINTER = "keychain:siyu-team/getnote"


def call(*args, **kwargs):
    # keychain 骨架已就绪：先解析密钥（环境变量 / macOS keychain），再接具体 API。
    require_secret(POINTER, "Get笔记", "SIYU_GETNOTE_TOKEN")
    raise ConnectorNotImplemented("Get笔记密钥已解析；majia-getnote 调用接入时实现。")
