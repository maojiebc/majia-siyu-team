"""本地 JSONL 追踪：默认只存元数据，内容追踪必须显式开启。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping
from uuid import uuid4


DEFAULT_TRACE_RETENTION_DAYS = 30
MAX_TRACE_RETENTION_DAYS = 36_500
DEFAULT_TRACE_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_TRACE_MAX_FILES = 1_000
_TRACE_ID_PATTERN = re.compile(r"^trace_[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class TraceLevel(str, Enum):
    """追踪内容级别。

    ``metadata`` 不保存请求正文或上下文；``redacted`` 保存正则脱敏后的
    内容；``full`` 保存原始内容，因此只能由调用方显式选择。
    """

    METADATA = "metadata"
    REDACTED = "redacted"
    FULL = "full"


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
        # set 不能 JSON 序列化；稳定排序保证同一内容跨运行序列化一致。
        return sorted((redact(item) for item in value), key=str)
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


def _source_digest(source_text: str) -> str:
    return "sha256:" + hashlib.sha256(source_text.encode("utf-8")).hexdigest()


def _metadata_payload(event: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """按事件白名单提取不可逆元数据，未知内容一律丢弃。"""

    if event == "task.created":
        source_text = str(payload.get("source_text", ""))
        return {
            "kind": str(payload.get("kind", "unknown")),
            "risk": str(payload.get("risk", "unknown")),
            "source_length": len(source_text),
            "source_hash": _source_digest(source_text),
        }
    if event == "task.routed":
        return {
            "route": str(payload.get("skill", "")),
            "needs_clarification": bool(payload.get("needs_clarification", False)),
        }
    if event in {"knowledge.attached", "growth_atoms.attached"}:
        raw_atom_ids = payload.get("atom_ids", payload.get("locators", ()))
        atom_ids = (
            [str(item) for item in raw_atom_ids]
            if isinstance(raw_atom_ids, (list, tuple))
            else []
        )
        raw_count = payload.get("count", len(atom_ids))
        count = (
            raw_count
            if isinstance(raw_count, int) and not isinstance(raw_count, bool)
            else len(atom_ids)
        )
        return {
            "atom_ids": atom_ids,
            "count": count,
            "corpus_version": str(payload.get("corpus_version", "")),
            "corpus_hash": str(payload.get("corpus_hash", "")),
        }
    if event == "contexts.created":
        raw_officers = payload.get("officers", ())
        return {
            "officers": (
                [str(item) for item in raw_officers]
                if isinstance(raw_officers, (list, tuple))
                else []
            )
        }

    # 错误事件只保留稳定错误码。未知事件不猜测字段是否安全。
    error_code = payload.get("error_code", payload.get("code"))
    if error_code is not None:
        return {"error_code": str(error_code)}
    if payload:
        # 保留“有内容但已丢弃”的可观测性，也兼容旧消费者识别脱敏记录。
        return {"content": "[REDACTED]"}
    return {}


def _coerce_non_negative(value: int | None, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} 必须是非负整数或 None")
    return value


def _validate_trace_id(trace_id: str) -> str:
    if not isinstance(trace_id, str) or not _TRACE_ID_PATTERN.fullmatch(trace_id):
        raise ValueError(
            "trace_id 必须以 trace_ 开头，且只能包含字母、数字、下划线和连字符"
        )
    return trace_id


def _validate_trace_root(directory: str | Path) -> Path:
    root = Path(directory)
    if root.is_symlink():
        raise ValueError(f"追踪目录不得是符号链接：{root}")
    if root.exists() and not root.is_dir():
        raise ValueError(f"追踪路径不是目录：{root}")
    return root


class TraceRecorder:
    def __init__(
        self,
        directory: str | Path = ".siyu-team/traces",
        *,
        level: TraceLevel | str = TraceLevel.METADATA,
        retention_days: int = DEFAULT_TRACE_RETENTION_DAYS,
        max_bytes: int | None = DEFAULT_TRACE_MAX_BYTES,
        max_files: int | None = DEFAULT_TRACE_MAX_FILES,
    ) -> None:
        self.directory = _validate_trace_root(directory)
        try:
            self.level = TraceLevel(level)
        except ValueError as exc:
            allowed = ", ".join(item.value for item in TraceLevel)
            raise ValueError(f"trace level 必须是：{allowed}") from exc
        normalized_days = _coerce_non_negative(retention_days, "retention_days")
        assert normalized_days is not None
        if normalized_days > MAX_TRACE_RETENTION_DAYS:
            raise ValueError(
                f"retention_days 不得超过 {MAX_TRACE_RETENTION_DAYS}"
            )
        self.retention_days = normalized_days
        self.max_bytes = _coerce_non_negative(max_bytes, "max_bytes")
        self.max_files = _coerce_non_negative(max_files, "max_files")
        # 启动即清理，不依赖用户记得单独执行维护命令。
        self.cleanup()

    def cleanup(self) -> tuple[int, int]:
        return cleanup_old_traces(
            self.directory,
            self.retention_days,
            max_bytes=self.max_bytes,
            max_files=self.max_files,
        )

    def new_trace_id(self) -> str:
        return f"trace_{uuid4().hex}"

    def _payload(self, event: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        if self.level is TraceLevel.FULL:
            return dict(payload)
        if self.level is TraceLevel.REDACTED:
            redacted = redact(dict(payload))
            assert isinstance(redacted, dict)
            return redacted
        return _metadata_payload(event, payload)

    def emit(
        self,
        trace_id: str,
        task_id: str,
        event: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Path:
        normalized_trace_id = _validate_trace_id(trace_id)
        _validate_trace_root(self.directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        # mkdir 与后续 open 之间仍可能被换成链接；再次检查并配合
        # O_NOFOLLOW 关闭两个层级的常见 TOCTOU 写入路径。
        _validate_trace_root(self.directory)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        path = self.directory / f"{normalized_trace_id}.jsonl"
        raw_payload = dict(payload or {})
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "trace_id": normalized_trace_id,
            "task_id": task_id,
            "event": event,
            "trace_level": self.level.value,
            "payload": self._payload(event, raw_payload),
        }
        line = (
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        flags |= getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        flags |= getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError as exc:
            raise ValueError(f"追踪文件路径不安全或不可写：{path}") from exc
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError(f"追踪文件必须是单链接普通文件：{path}")
            os.fchmod(descriptor, 0o600)
            view = memoryview(line)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
        finally:
            os.close(descriptor)
        # 写入也可能越过容量阈值；立即把最旧记录清掉。
        self.cleanup()
        return path


def cleanup_old_traces(
    directory: str | Path = ".siyu-team/traces",
    days: int = DEFAULT_TRACE_RETENTION_DAYS,
    *,
    max_bytes: int | None = None,
    max_files: int | None = None,
) -> tuple[int, int]:
    """按 TTL 和容量删除最旧追踪，返回 ``(文件数, 字节数)``。"""

    normalized_days = _coerce_non_negative(days, "days")
    assert normalized_days is not None
    if normalized_days > MAX_TRACE_RETENTION_DAYS:
        raise ValueError(f"days 不得超过 {MAX_TRACE_RETENTION_DAYS}")
    normalized_bytes = _coerce_non_negative(max_bytes, "max_bytes")
    normalized_files = _coerce_non_negative(max_files, "max_files")
    root = _validate_trace_root(directory)
    if not root.exists():
        return 0, 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=normalized_days)
    deleted_count = 0
    deleted_bytes = 0

    for path in root.glob("trace_*.jsonl"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                path.unlink()
                deleted_count += 1
                deleted_bytes += stat.st_size
        except OSError:
            continue

    remaining: list[tuple[float, str, Path, int]] = []
    for path in root.glob("trace_*.jsonl"):
        try:
            if path.is_symlink() or not path.is_file():
                continue
            stat = path.stat()
            remaining.append((stat.st_mtime, path.name, path, stat.st_size))
        except OSError:
            continue
    remaining.sort()
    total_bytes = sum(item[3] for item in remaining)

    while remaining and (
        normalized_files is not None
        and len(remaining) > normalized_files
        or normalized_bytes is not None
        and total_bytes > normalized_bytes
    ):
        _mtime, _name, path, size = remaining.pop(0)
        try:
            path.unlink()
        except OSError:
            continue
        total_bytes -= size
        deleted_count += 1
        deleted_bytes += size

    return deleted_count, deleted_bytes
