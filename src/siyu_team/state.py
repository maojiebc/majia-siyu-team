"""按 run 隔离的状态存储，带原子写入、文件锁与旧状态只读迁移。"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator, Mapping, Optional
from uuid import uuid4


STATE_DIR = ".siyu-team"
# 旧路径仅作为迁移输入保留；新写入位于 runs/{run_id}/state.json。
STATE_PATH = os.path.join(STATE_DIR, "state.json")
RUNS_DIR = "runs"
CURRENT_PATH = "current"
STATE_SCHEMA_VERSION = "1.0"
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROTECTED_UPDATE_FIELDS = frozenset(
    {
        "schema_version",
        "run_id",
        "revision",
        "current_step",
        "status",
        "started_at",
        "last_updated",
        "files_created",
        "completed_steps",
    }
)
_RAW_CONTENT_FIELDS = frozenset(
    {
        "source_text",
        "raw_source",
        "raw_request",
        "request_text",
        "full_chat",
        "chat",
        "chat_history",
        "conversation_history",
        "messages",
        "transcript",
        "prompt",
        "prompts",
        "raw_prompt",
        "officer_outputs",
        "raw_officer_outputs",
        "原始请求",
        "完整聊天",
        "聊天记录",
        "原始提示词",
    }
)


class StateError(RuntimeError):
    """状态缺失、损坏、并发冲突或转移非法。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"run_{stamp}_{uuid4().hex[:12]}"


def _validate_run_id(run_id: str) -> str:
    normalized = run_id.strip()
    if not _RUN_ID_PATTERN.fullmatch(normalized) or normalized in {".", ".."}:
        raise StateError("run_id 只能包含字母、数字、点、下划线和连字符")
    return normalized


def _valid_step(step: Any) -> bool:
    return (
        isinstance(step, int)
        and not isinstance(step, bool)
        and step >= 0
        or isinstance(step, str)
        and (step == "complete" or step.startswith("checkpoint-"))
    )


def _reject_symlink(path: Path, label: str) -> None:
    if path.is_symlink():
        raise StateError(f"{label} 不得是符号链接：{path}")


def _read_text_no_follow(path: Path, label: str) -> str:
    _reject_symlink(path, label)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StateError(f"{label} 无法安全读取：{path}") from exc
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise StateError(f"{label} 必须是单链接普通文件：{path}")
    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeError) as exc:
        raise StateError(f"{label} 无法读取：{path}") from exc


def _normalized_content_key(key: object) -> str:
    return str(key).strip().casefold().replace("-", "_").replace(" ", "_")


def _find_raw_content_fields(value: Any) -> tuple[str, ...]:
    """递归找出会把完整对话或 Prompt 落盘的字段路径。"""

    found: list[str] = []
    seen: set[int] = set()

    def visit(item: Any, path: str) -> None:
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in seen:
                return
            seen.add(identity)
            for key, child in item.items():
                name = str(key)
                child_path = f"{path}.{name}" if path else name
                if _normalized_content_key(key) in _RAW_CONTENT_FIELDS:
                    found.append(child_path)
                visit(child, child_path)
        elif isinstance(item, (list, tuple)):
            identity = id(item)
            if identity in seen:
                return
            seen.add(identity)
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")

    visit(value, "")
    return tuple(found)


def _ensure_private_directory(path: Path) -> None:
    _reject_symlink(path, "受管目录")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    _reject_symlink(path, "受管目录")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise StateError(f"受管目录路径不安全或不可访问：{path}") from exc
    try:
        os.fchmod(descriptor, 0o700)
    finally:
        os.close(descriptor)


@contextmanager
def _file_lock(path: Path, *, exclusive: bool = True) -> Iterator[None]:
    """使用同目录锁文件协调跨线程、跨进程状态更新。"""

    _ensure_private_directory(path.parent)
    _reject_symlink(path, "锁文件")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise StateError(f"锁文件路径不安全或不可写：{path}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise StateError(f"锁文件必须是单链接普通文件：{path}")
        os.fchmod(descriptor, 0o600)
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(descriptor, operation)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _atomic_write(path: Path, content: str) -> None:
    _ensure_private_directory(path.parent)
    _reject_symlink(path, "状态写入目标")
    descriptor, temporary_path = tempfile.mkstemp(
        prefix=f".{path.name}-",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, 0o600)
        _reject_symlink(path, "状态写入目标")
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _serialize(state: dict[str, Any]) -> str:
    try:
        return json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    except (TypeError, ValueError) as exc:
        raise StateError("状态包含不可序列化字段") from exc


class StateStore:
    def __init__(
        self,
        directory: str | Path = STATE_DIR,
        *,
        run_id: str | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.runs_directory = self.directory / RUNS_DIR
        self.current_path = self.directory / CURRENT_PATH
        self.legacy_path = self.directory / "state.json"
        self.run_id = ""
        self.run_directory = self.runs_directory
        self.path = self.legacy_path
        self.task_path = self.directory / "task.json"
        self.outputs_directory = self.directory / "outputs"
        self.traces_directory = self.directory / "traces"
        self._explicit_run_id = run_id is not None
        if run_id is not None:
            self._activate(run_id)
        elif self.current_path.is_symlink():
            raise StateError(f"current 指针不得是符号链接：{self.current_path}")
        elif self.current_path.exists():
            # 只解析指针，不在构造函数里触发旧状态迁移或任何写入。
            self._activate(self._read_current_pointer())

    def _activate(self, run_id: str) -> None:
        normalized = _validate_run_id(run_id)
        self.run_id = normalized
        self.run_directory = self.runs_directory / normalized
        self.path = self.run_directory / "state.json"
        self.task_path = self.run_directory / "task.json"
        self.outputs_directory = self.run_directory / "outputs"
        self.traces_directory = self.run_directory / "traces"

    @property
    def revision(self) -> int:
        return int(self.read()["revision"])

    def _create_run_layout(self) -> None:
        _ensure_private_directory(self.directory)
        _ensure_private_directory(self.runs_directory)
        _ensure_private_directory(self.run_directory)
        _ensure_private_directory(self.outputs_directory)
        _ensure_private_directory(self.traces_directory)

    def _read_current_pointer(self) -> str:
        try:
            value = _read_text_no_follow(
                self.current_path, "current 指针"
            ).strip()
        except StateError as exc:
            raise StateError(f"current 指针无法读取：{self.current_path}") from exc
        return _validate_run_id(value)

    def _write_current_pointer(self) -> None:
        _atomic_write(self.current_path, f"{self.run_id}\n")

    def _write_task_summary(self, state: dict[str, Any]) -> None:
        summary = {
            "schema_version": state["schema_version"],
            "run_id": state["run_id"],
            "client": state.get("client", ""),
            "industry": state.get("industry", ""),
            "stage": state.get("stage", ""),
            "created_at": state.get("started_at", _now()),
        }
        _atomic_write(self.task_path, _serialize(summary))

    def initialize(
        self,
        client: str,
        industry: str = "",
        stage: str = "",
        *,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        if not client.strip():
            raise StateError("client 不能为空")
        chosen_run_id = (
            run_id
            or (self.run_id if self._explicit_run_id else "")
            or _new_run_id()
        )
        if self._explicit_run_id and run_id is not None and run_id != self.run_id:
            raise StateError("StateStore 已绑定其他 run_id")
        self._activate(chosen_run_id)
        self._explicit_run_id = True
        self._create_run_layout()
        now = _now()
        state: dict[str, Any] = {
            "schema_version": STATE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "revision": 1,
            "client": client.strip(),
            "industry": industry.strip().lower(),
            "stage": stage.strip().lower(),
            "status": "in_progress",
            "current_step": 0,
            "completed_steps": [],
            "files_created": [],
            "officer_scores": {},
            "compliance_flags": [],
            "host_rounds": 0,
            "started_at": now,
            "last_updated": now,
        }
        with _file_lock(self.run_directory / ".state.lock"):
            if self.path.exists():
                raise StateError(f"run 已存在，拒绝覆盖：{self.run_id}")
            _atomic_write(self.path, _serialize(state))
            self._write_task_summary(state)
        # current 是兼容入口；已有 StateStore 实例仍绑定自己的 run，不会串写。
        with _file_lock(self.directory / ".current.lock"):
            self._write_current_pointer()
        return state

    def _read_path(self, path: Path) -> dict[str, Any]:
        try:
            state = json.loads(_read_text_no_follow(path, "状态文件"))
        except (StateError, json.JSONDecodeError) as exc:
            raise StateError(f"状态文件损坏：{path}") from exc
        if not isinstance(state, dict):
            raise StateError("状态文件根节点必须是对象")
        schema_version = state.get("schema_version")
        if schema_version not in {None, STATE_SCHEMA_VERSION}:
            raise StateError("状态 schema_version 不受支持")
        # v0.3.x 状态没有这些字段；只在内存/新 run 中补齐，不回写旧文件。
        state.setdefault("schema_version", STATE_SCHEMA_VERSION)
        state.setdefault("revision", 0)
        revision = state.get("revision")
        if (
            isinstance(revision, bool)
            or not isinstance(revision, int)
            or revision < 0
        ):
            raise StateError("revision 非法")
        if not _valid_step(state.get("current_step")):
            raise StateError("current_step 非法")
        if state.get("status") not in {
            "in_progress",
            "complete",
            "failed",
            "paused",
        }:
            raise StateError("status 非法")
        return state

    def _migrate_legacy_if_needed(self) -> None:
        if self.run_id:
            return
        with _file_lock(self.directory / ".migration.lock"):
            # 与新 run 初始化共用 current 锁，避免迁移与初始化互相覆盖指针。
            with _file_lock(self.directory / ".current.lock"):
                # 另一进程可能已完成迁移，锁内必须重查 current。
                if self.current_path.exists():
                    self._activate(self._read_current_pointer())
                    return
                if self.legacy_path.is_symlink():
                    raise StateError(
                        f"旧状态文件不得是符号链接：{self.legacy_path}"
                    )
                if not self.legacy_path.exists():
                    raise StateError(f"状态文件不存在：{self.legacy_path}")
                legacy_state = self._read_path(self.legacy_path)
                self._activate(_new_run_id())
                self._create_run_layout()
                migrated = dict(legacy_state)
                migrated["schema_version"] = STATE_SCHEMA_VERSION
                migrated["run_id"] = self.run_id
                migrated["revision"] = max(1, int(migrated.get("revision", 0)))
                migrated["migrated_from"] = "state.json"
                migrated["migrated_at"] = _now()
                _atomic_write(self.path, _serialize(migrated))
                self._write_task_summary(migrated)
                self._write_current_pointer()

    def _ensure_active(self) -> None:
        if not self.run_id:
            self._migrate_legacy_if_needed()
        if not self.path.exists():
            raise StateError(f"状态文件不存在：{self.path}")

    def read(self) -> dict[str, Any]:
        self._ensure_active()
        with _file_lock(self.run_directory / ".state.lock", exclusive=False):
            state = self._read_path(self.path)
        stored_run_id = state.get("run_id")
        if stored_run_id is not None and stored_run_id != self.run_id:
            raise StateError("状态文件 run_id 与目录不一致")
        state.setdefault("run_id", self.run_id)
        return state

    def check_session(self) -> Optional[dict[str, Any]]:
        if self.run_id:
            return self.read() if self.path.exists() else None
        if not self.current_path.exists() and not self.legacy_path.exists():
            return None
        return self.read()

    def update(
        self,
        step: Any = None,
        add_file: str | None = None,
        add_completed: Any = None,
        status: str | None = None,
        *,
        expected_revision: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        self._ensure_active()
        protected = _PROTECTED_UPDATE_FIELDS.intersection(extra)
        if protected:
            names = ", ".join(sorted(protected))
            raise StateError(f"这些字段必须通过专用参数更新：{names}")
        raw_content_fields = _find_raw_content_fields(extra)
        if raw_content_fields:
            names = ", ".join(raw_content_fields)
            raise StateError(
                "状态默认只保存结构化结论，不保存完整聊天、原始请求或 Prompt："
                + names
            )
        if expected_revision is not None and (
            isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int)
            or expected_revision < 0
        ):
            raise StateError("expected_revision 必须是非负整数")

        with _file_lock(self.run_directory / ".state.lock"):
            state = self._read_path(self.path)
            current_revision = int(state.get("revision", 0))
            if (
                expected_revision is not None
                and expected_revision != current_revision
            ):
                raise StateError(
                    "状态 revision 冲突："
                    f"期望 {expected_revision}，实际 {current_revision}"
                )
            if step is not None:
                if not _valid_step(step):
                    raise StateError(f"非法 current_step：{step!r}")
                state["current_step"] = step
            if add_file:
                files = state.setdefault("files_created", [])
                if add_file not in files:
                    files.append(add_file)
            if add_completed is not None:
                completed = state.setdefault("completed_steps", [])
                if add_completed not in completed:
                    completed.append(add_completed)
            if status:
                if status not in {"in_progress", "complete", "failed", "paused"}:
                    raise StateError(f"非法 status：{status!r}")
                state["status"] = status
                if status == "complete":
                    state["current_step"] = "complete"
            state.update(extra)
            state["run_id"] = self.run_id
            state["revision"] = current_revision + 1
            state["last_updated"] = _now()
            _atomic_write(self.path, _serialize(state))
        return state


_DEFAULT_STORE = StateStore()


def init_state(
    client: str,
    industry: str = "",
    stage: str = "",
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    global _DEFAULT_STORE
    _DEFAULT_STORE = StateStore(run_id=run_id)
    return _DEFAULT_STORE.initialize(client, industry, stage, run_id=run_id)


def check_session() -> Optional[dict[str, Any]]:
    return _DEFAULT_STORE.check_session()


def update(
    step: Any = None,
    add_file: str | None = None,
    add_completed: Any = None,
    status: str | None = None,
    *,
    expected_revision: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    return _DEFAULT_STORE.update(
        step=step,
        add_file=add_file,
        add_completed=add_completed,
        status=status,
        expected_revision=expected_revision,
        **extra,
    )
