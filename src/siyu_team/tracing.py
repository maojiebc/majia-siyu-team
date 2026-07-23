"""本地 JSONL 追踪；默认脱敏、最小权限、单行追加。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping
from uuid import uuid4


_SENSITIVE_KEY = re.compile(
    r"(token|secret|password|authorization|cookie|phone|mobile|id_card)",
    re.IGNORECASE,
)
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_ID_CARD = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


def redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = _PHONE.sub("[PHONE]", value)
        value = _ID_CARD.sub("[ID_CARD]", value)
        return _BEARER.sub("Bearer [REDACTED]", value)
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
