"""贡献内容的基础隐私、凭据和敏感经营信息扫描。"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class PrivacyFinding:
    category: str
    field: str
    blocking: bool
    message: str


@dataclass(frozen=True)
class PrivacyScan:
    safe: bool
    findings: tuple[PrivacyFinding, ...]

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(finding.message for finding in self.findings))

    @property
    def affected_fields(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(finding.field for finding in self.findings))


_PATTERNS: tuple[tuple[str, re.Pattern[str], bool, str], ...] = (
    (
        "phone",
        re.compile(r"(?<!\d)(?:\+?0{0,2}86[-\s]?)?1[3-9]\d{9}(?!\d)"),
        True,
        "检测到手机号，请删除或脱敏后再提交。",
    ),
    (
        "id_card",
        re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)"),
        True,
        "检测到身份证号，请删除后再提交。",
    ),
    (
        "email",
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
        True,
        "检测到邮箱，请移到授权联系人字段或删除。",
    ),
    (
        "credential",
        re.compile(
            r"(?i)(?:bearer\s+[A-Za-z0-9._~+/=-]+|"
            r"(?:gh[opsur]|github_pat|sk|pk|rk|xox[baprs])[_-][A-Za-z0-9_-]{6,}|"
            r"(?:api[_-]?key|app[_-]?secret|password|密码|密钥)\s*[:=]\s*\S+)"
        ),
        True,
        "检测到密钥或凭据，禁止提交。",
    ),
    (
        "store_identifier",
        re.compile(r"(?:门店|加盟商)(?:编号|编码|ID)\s*[:：]?\s*[A-Za-z0-9_-]{3,}"),
        True,
        "检测到可识别门店或加盟商编号，请脱敏后再提交。",
    ),
    (
        "sensitive_business_metric",
        re.compile(r"(?:营收|流水|毛利率?|客单价|订单明细|净利润)\s*[:：]?\s*[¥￥]?\d"),
        False,
        "检测到具体经营数据，请确认已获授权且无需进一步脱敏。",
    ),
)


def scan_fields(fields: Iterable[tuple[str, str]]) -> PrivacyScan:
    findings: list[PrivacyFinding] = []
    for field, text in fields:
        for category, pattern, blocking, message in _PATTERNS:
            if pattern.search(text):
                findings.append(PrivacyFinding(category, field, blocking, message))
    return PrivacyScan(
        safe=not any(finding.blocking for finding in findings),
        findings=tuple(findings),
    )
