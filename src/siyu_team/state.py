"""state.json 读写 / 续跑 / 防重入。仿 wshobson full-stack-feature.md:23-58,127。

current_step 一个字段同时编码三态：普通步(int) / 卡点("checkpoint-N") / 完结("complete")。
"""
from __future__ import annotations
import json, os, datetime
from typing import Optional

STATE_DIR = ".siyu-team"
STATE_PATH = os.path.join(STATE_DIR, "state.json")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def init_state(client: str, industry: str = "", stage: str = "") -> dict:
    os.makedirs(STATE_DIR, exist_ok=True)
    st = {
        "client": client, "industry": industry, "stage": stage,
        "status": "in_progress", "current_step": 0,
        "completed_steps": [], "files_created": [],
        "officer_scores": {}, "compliance_flags": [], "host_rounds": 0,
        "started_at": _now(), "last_updated": _now(),
    }
    _save(st)
    return st


def check_session() -> Optional[dict]:
    """幂等入口：存在且 in_progress 则返回供续跑，否则 None。"""
    if not os.path.exists(STATE_PATH):
        return None
    st = json.load(open(STATE_PATH))
    return st if st.get("status") == "in_progress" else st


def update(step=None, add_file=None, add_completed=None, status=None, **extra) -> dict:
    st = json.load(open(STATE_PATH))
    if step is not None:
        st["current_step"] = step
    if add_file:
        st.setdefault("files_created", []).append(add_file)
    if add_completed:
        st.setdefault("completed_steps", []).append(add_completed)
    if status:
        st["status"] = status
    st.update(extra)
    st["last_updated"] = _now()
    _save(st)
    return st


def _save(st: dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st, open(STATE_PATH, "w"), ensure_ascii=False, indent=2)
