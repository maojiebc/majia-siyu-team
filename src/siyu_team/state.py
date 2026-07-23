"""运行状态的原子化读写、续跑与防重入。"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Optional


STATE_DIR = ".siyu-team"
STATE_PATH = os.path.join(STATE_DIR, "state.json")
STATE_SCHEMA_VERSION = "1.0"
_PROTECTED_UPDATE_FIELDS = frozenset(
    {
        "schema_version",
        "current_step",
        "status",
        "started_at",
        "last_updated",
        "files_created",
        "completed_steps",
    }
)


class StateError(RuntimeError):
    """状态缺失、损坏或转移非法。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _valid_step(step: Any) -> bool:
    return (
        isinstance(step, int)
        and not isinstance(step, bool)
        and step >= 0
        or isinstance(step, str)
        and (step == "complete" or step.startswith("checkpoint-"))
    )


class StateStore:
    def __init__(self, directory: str | Path = STATE_DIR) -> None:
        self.directory = Path(directory)
        self.path = self.directory / "state.json"

    def initialize(self, client: str, industry: str = "", stage: str = "") -> dict:
        if not client.strip():
            raise StateError("client 不能为空")
        state = {
            "schema_version": STATE_SCHEMA_VERSION,
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
            "started_at": _now(),
            "last_updated": _now(),
        }
        self._write(state)
        return state

    def read(self) -> dict:
        if not self.path.exists():
            raise StateError(f"状态文件不存在：{self.path}")
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateError(f"状态文件损坏：{self.path}") from exc
        if not isinstance(state, dict):
            raise StateError("状态文件根节点必须是对象")
        schema_version = state.get("schema_version")
        if schema_version not in {None, STATE_SCHEMA_VERSION}:
            raise StateError("状态 schema_version 不受支持")
        # v0.3.x 状态没有 schema_version；内存中补齐，下一次 update 原子迁移。
        state.setdefault("schema_version", STATE_SCHEMA_VERSION)
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

    def check_session(self) -> Optional[dict]:
        if not self.path.exists():
            return None
        return self.read()

    def update(
        self,
        step: Any = None,
        add_file: str | None = None,
        add_completed: Any = None,
        status: str | None = None,
        **extra: Any,
    ) -> dict:
        state = self.read()
        protected = _PROTECTED_UPDATE_FIELDS.intersection(extra)
        if protected:
            names = ", ".join(sorted(protected))
            raise StateError(f"这些字段必须通过专用参数更新：{names}")
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
        state["last_updated"] = _now()
        self._write(state)
        return state

    def _write(self, state: dict) -> None:
        try:
            serialized = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
        except (TypeError, ValueError) as exc:
            raise StateError("状态包含不可序列化字段") from exc
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.directory, 0o700)
        except OSError:
            pass
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".state-",
            suffix=".tmp",
            dir=self.directory,
            text=True,
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self.path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)


_DEFAULT_STORE = StateStore()


def init_state(client: str, industry: str = "", stage: str = "") -> dict:
    return _DEFAULT_STORE.initialize(client, industry, stage)


def check_session() -> Optional[dict]:
    return _DEFAULT_STORE.check_session()


def update(
    step: Any = None,
    add_file: str | None = None,
    add_completed: Any = None,
    status: str | None = None,
    **extra: Any,
) -> dict:
    return _DEFAULT_STORE.update(
        step=step,
        add_file=add_file,
        add_completed=add_completed,
        status=status,
        **extra,
    )
