"""离线盲测对生成；真值只保存在私有 blind-map.json。"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping

from .models import PilotTask, PilotValidationError, SCORE_DIMENSIONS
from .packets import PROMPT_MARKER, render_task, write_private_text


def _load_run_manifest(run: Path) -> Mapping[str, Any]:
    path = run / "manifest.json"
    if not path.is_file():
        raise PilotValidationError(f"找不到试验 manifest：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotValidationError(f"manifest JSON 非法：{exc.msg}") from exc
    if not isinstance(data, Mapping):
        raise PilotValidationError("manifest 必须是对象")
    if not isinstance(data.get("seed"), int):
        raise PilotValidationError("manifest.seed 必须是整数")
    tasks = data.get("tasks")
    if isinstance(tasks, (str, bytes)) or not isinstance(tasks, list) or not tasks:
        raise PilotValidationError("manifest.tasks 必须是非空数组")
    return data


def _read_answer(path: Path) -> str:
    if not path.is_file():
        raise PilotValidationError(f"缺少模型答案：{path}")
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise PilotValidationError(f"模型答案为空：{path}")
    if PROMPT_MARKER in content:
        raise PilotValidationError(f"尚未用模型答案替换 Prompt：{path}")
    return content


def _knowledge_on_left(seed: int, task_id: str) -> bool:
    digest = hashlib.sha256(f"{seed}:{task_id}".encode()).digest()
    return bool(digest[0] & 1)


def _rating_sheet(task_ids: list[str]) -> str:
    output = io.StringIO(newline="")
    fields = ["reviewer_id", "task_id"]
    fields.extend(f"left_{dimension}" for dimension in SCORE_DIMENSIONS)
    fields.extend(f"right_{dimension}" for dimension in SCORE_DIMENSIONS)
    fields.extend(("preference", "reason"))
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for task_id in task_ids:
        writer.writerow({"task_id": task_id})
    return output.getvalue()


def create_blind_pairs(run: Path) -> Path:
    """根据 seed 稳定随机化左右位置，生成盲测对与空评分表。"""
    data = _load_run_manifest(run)
    seed = int(data["seed"])
    pairs: dict[str, dict[str, str]] = {}
    themes: dict[str, str] = {}
    task_ids: list[str] = []
    for raw_task in data["tasks"]:
        if not isinstance(raw_task, Mapping):
            raise PilotValidationError("manifest.tasks 中的每项必须是对象")
        task = PilotTask.from_dict(raw_task)
        baseline = _read_answer(run / "generation" / "baseline" / f"{task.id}.md")
        knowledge = _read_answer(run / "generation" / "knowledge" / f"{task.id}.md")
        knowledge_left = _knowledge_on_left(seed, task.id)
        left = knowledge if knowledge_left else baseline
        right = baseline if knowledge_left else knowledge
        pairs[task.id] = {
            "left": "knowledge" if knowledge_left else "baseline",
            "right": "baseline" if knowledge_left else "knowledge",
        }
        themes[task.id] = task.theme
        task_ids.append(task.id)
        content = "\n\n".join(
            (
                f"# 盲测任务 {task.id}",
                render_task(task),
                f"## 左侧答案\n\n{left}",
                f"## 右侧答案\n\n{right}",
            )
        )
        write_private_text(run / "blind" / "pairs" / f"{task.id}.md", content + "\n")

    map_payload = {"seed": seed, "pairs": pairs, "task_themes": themes}
    map_path = run / "blind" / "blind-map.json"
    write_private_text(
        map_path,
        json.dumps(map_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_private_text(run / "blind" / "rating-sheet.csv", _rating_sheet(task_ids))
    return map_path
