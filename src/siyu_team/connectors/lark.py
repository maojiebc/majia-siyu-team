"""飞书 连接器（预留接口，未接入）。接在：Completion。
04-playbook.md 落成飞书 docx；进度同步；改正文走 lark-cli str_replace

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 lark-cli。【接入时填】
"""


from .base import ConnectorNotImplemented, require_secret

POINTER = "keychain:siyu-team/lark"


def call(*args, **kwargs):
    # keychain 骨架已就绪：先解析密钥（环境变量 / macOS keychain），再接具体 API。
    require_secret(POINTER, "飞书", "SIYU_LARK_TOKEN")
    raise ConnectorNotImplemented("飞书密钥已解析；lark-cli 调用接入时实现。")
