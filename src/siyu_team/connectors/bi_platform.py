"""某 BI 平台 连接器（预留接口，未接入）。接在：Step0 调研 + Step3 收口。
取真实漏斗数据验证转化口径；方案埋点指标建成某 BI 平台卡片/看板

密钥走 keychain 指针 keychain:siyu-team/<tool>，真 token 不入库。
实现：调用 bi-cli/bi-ds/bi-vis。【接入时填】
"""


def call(*args, **kwargs):
    raise NotImplementedError("接入 某 BI 平台 时实现：bi-cli/bi-ds/bi-vis")
