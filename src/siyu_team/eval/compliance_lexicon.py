"""合规与静态质量正则的单一真源。其他模块只能 import，不得复制词表。"""
from __future__ import annotations

import re


# (flag, 说明, severity, 是否硬卡 exit 1, 正则)
PATTERNS = [
    ("COMPLIANCE_RED", "封号/诱导分享/绝对化承诺", 0.20, True,
     re.compile(r"(诱导分享|外挂|群发软件|虚拟定位|改定位|第一|最便宜|最好|100%|永久免费|稳赚|包赚)")),
    ("NO_CALIBRATION", "出现转化/复购率但无口径", 0.15, False,
     re.compile(r"(转化率|复购率|加微率)(?!.{0,30}(分母|UV|加微数|周期|时间窗|=))")),
    ("ABSOLUTE_CLAIM", "广告法绝对化用词", 0.10, False,
     re.compile(r"(国家级|顶级|绝无仅有|独一无二|史上最)")),
    ("NO_RESPONSIBLE_PARTY", "SOP 段无责任人", 0.10, False, None),
    ("NO_METRIC", "全文无可埋点指标", 0.10, False,
     re.compile(r"(率|人数|GMV|客单|复购|留存|触达)")),
]

# 群发和欢迎语共用的社交裂变门槛。
INDUCE_PATTERN = re.compile(
    r"(转发.{0,8}(领|送|得|抽|享|免)|集\s*\d*\s*赞|集赞|拉\s*\d+\s*人|拉够\s*\d+"
    r"|分享.{0,4}(到|给).{0,4}(群|好友)|邀请\s*\d+\s*位?好友|\d+\s*人成团才)"
)

# 欢迎语中未带授权口径的敏感信息索取信号。
PRIVACY_PATTERN = re.compile(
    r"(留.{0,3}(手机号|电话|微信号)|发.{0,3}(身份证|定位|位置)|报.{0,3}(手机号|电话)"
    r"|加我.{0,4}(发|留).{0,4}(定位|手机号|身份证)|银行卡|身份证号)"
)
