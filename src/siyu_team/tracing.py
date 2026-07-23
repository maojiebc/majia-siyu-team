"""本地 JSONL 追踪；默认脱敏、最小权限、单行追加。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4


# 敏感字段名：命中即整值打码。覆盖常见凭据字段（含驼峰/连字符）与中文别名。
_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|passwd|pwd|authorization|cookie|"
    r"phone|mobile|id_card|idcard|"
    r"api[_-]?key|access[_-]?key|secret[_-]?key|private[_-]?key|app[_-]?secret|"
    r"credential|session|"
    r"密码|密钥|口令|令牌|手机号|身份证)",
    re.IGNORECASE,
)
# 手机号：容忍 +86 / 86 / 0086 国家码前缀，同时用 (?<!\d)/(?!\d) 防长数字串误伤。
_PHONE = re.compile(r"(?<!\d)(?:\+?0{0,2}86[-\s]?)?1[3-9]\d{9}(?!\d)")
# 身份证：18 位（末位可 X）或 15 位老号。
_ID_CARD = re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")
# 值里裸露的常见令牌：GitHub / OpenAI-Stripe / Slack / AWS / Google 等前缀。
# 前置 (?<![A-Za-z0-9]) 只挡字母数字，故中文紧贴（我的sk-xxx）仍能命中、ask/task 不误伤。
_TOKEN_VALUE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:(?:gh[opsur]|github_pat|sk|pk|rk|xox[baprs])[_-][A-Za-z0-9][A-Za-z0-9_-]{5,}"
    r"|(?:AKIA|ASIA|AIza)[A-Za-z0-9]{10,})"
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _mask_text(text: str) -> str:
    text = _PHONE.sub("[PHONE]", text)
    text = _ID_CARD.sub("[ID_CARD]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _TOKEN_VALUE.sub("[TOKEN]", text)
    text = _EMAIL.sub("[EMAIL]", text)
    return text


def redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, (set, frozenset)):
        # set 不能 JSON 序列化，落盘前统一转 list 并逐项脱敏。
        return [redact(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        # int 型手机号/身份证也要脱；未命中则保持原值与类型。
        text = str(value)
        masked = _PHONE.sub("[PHONE]", text)
        masked = _ID_CARD.sub("[ID_CARD]", masked)
        return masked if masked != text else value
    if isinstance(value, str):
        return _mask_text(value)
    return value


class TraceRecorder:
    def __init__(self, directory: str | Path = ".siyu-team/traces") -> None:
        self.directory = Path(directory)

    def new_trace_id(self) -> str:
        return f"trace_{uuid4().hex}"

    def emit(
        self,
        trace_id: str,
        task_id: str,
        event: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        path = self.directory / f"{trace_id}.jsonl"
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": trace_id,
            "task_id": task_id,
            "event": event,
            "payload": redact(dict(payload or {})),
        }
        line = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o600,
        )
        try:
            os.write(descriptor, line)
        finally:
            os.close(descriptor)
        return path
