"""飞书 连接器（薄包装）。接在：Completion。
04-playbook.md 落成飞书 docx；进度同步；改正文走 lark-cli str_replace

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 lark-cli。【接入时填】
"""


def call(*args, **kwargs):
    raise NotImplementedError("接入 飞书 时实现：lark-cli")
