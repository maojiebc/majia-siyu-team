"""任务、原子和双版本 Prompt 包的离线准备。"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from siyu_team.knowledge import KnowledgeAtomV2, KnowledgeValidationError

from .models import GenerationManifest, PilotTask, PilotValidationError, THEMES, canonical_json


PROMPT_MARKER = "<!-- SIYU-PILOT-PROMPT：请用模型答案完整替换本文件后再 blind -->"
BASE_PROTOCOL = """你是连锁加盟餐饮私域经营助手。请只回答当前问题。
要求：先判断第一断点，考虑总部、区域、加盟商、店员和用户约束；给出可核验指标、成立条件和失效边界；不得编造行业阈值、政策或客户事实。"""
KNOWLEDGE_HEADER = """## 本次可使用的行业知识

以下内容只作为条件性证据，不是绝对规则。
每条包含成立条件和失效边界。不得超出证据范围。"""
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def write_private_text(path: Path, content: str) -> None:
    _private_dir(path.parent)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    finally:
        try:
            path.chmod(0o600)
        except OSError:
            pass


def _read_json_lines(path: Path) -> list[tuple[int, Mapping[str, Any]]]:
    if not path.is_file():
        raise PilotValidationError(f"找不到 JSONL：{path}")
    result: list[tuple[int, Mapping[str, Any]]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PilotValidationError(f"{path}:{line_number} JSON 非法：{exc.msg}") from exc
        if not isinstance(data, Mapping):
            raise PilotValidationError(f"{path}:{line_number} 必须是对象")
        result.append((line_number, data))
    if not result:
        raise PilotValidationError(f"{path} 为空")
    return result


def load_tasks(path: Path) -> tuple[PilotTask, ...]:
    tasks: list[PilotTask] = []
    for line_number, data in _read_json_lines(path):
        try:
            tasks.append(PilotTask.from_dict(data))
        except PilotValidationError as exc:
            raise PilotValidationError(f"{path}:{line_number} {exc}") from exc
    return tuple(tasks)


def load_atoms(path: Path) -> tuple[KnowledgeAtomV2, ...]:
    atoms: list[KnowledgeAtomV2] = []
    for line_number, data in _read_json_lines(path):
        try:
            atoms.append(KnowledgeAtomV2.from_dict(data))
        except KnowledgeValidationError as exc:
            raise PilotValidationError(f"{path}:{line_number} {exc}") from exc
    return tuple(atoms)


def validate_tasks(tasks: Sequence[PilotTask], *, expected_count: int = 30) -> None:
    if len(tasks) != expected_count:
        raise PilotValidationError(f"Golden Tasks 必须为 {expected_count} 个，当前 {len(tasks)}")
    ids = [task.id for task in tasks]
    if len(ids) != len(set(ids)):
        raise PilotValidationError("Task ID 必须唯一")
    counts = Counter(task.theme for task in tasks)
    expected_per_theme = expected_count // len(THEMES)
    if expected_count % len(THEMES) or any(
        counts.get(theme, 0) != expected_per_theme for theme in THEMES
    ):
        raise PilotValidationError(
            f"三个主题必须均衡，当前：{dict(sorted(counts.items()))}"
        )


def _atom_themes(atom: KnowledgeAtomV2) -> set[str]:
    return set(atom.topics).intersection(THEMES)


def validate_atoms(
    atoms: Sequence[KnowledgeAtomV2],
    *,
    atoms_path: Path,
    fixture_mode: bool = False,
    today: date | None = None,
) -> None:
    if not atoms:
        raise PilotValidationError("试验原子为空")
    if not fixture_mode and atoms_path.stat().st_mode & 0o077:
        raise PilotValidationError("私有原子文件权限必须为 0600")
    current = (today or date.today()).isoformat()
    ids: set[str] = set()
    counts: Counter[str] = Counter()
    for atom in atoms:
        if atom.id in ids:
            raise PilotValidationError(f"重复 Atom ID：{atom.id}")
        ids.add(atom.id)
        if atom.quality.review_status != "approved":
            raise PilotValidationError(f"非 Approved Atom 被拒绝：{atom.id}")
        if atom.scope.visibility == "client_private":
            raise PilotValidationError(f"客户私有 Atom 被拒绝：{atom.id}")
        if atom.lifecycle.valid_until and atom.lifecycle.valid_until < current:
            raise PilotValidationError(f"过期 Atom 被拒绝：{atom.id}")
        themes = _atom_themes(atom)
        if len(themes) != 1:
            raise PilotValidationError(f"Atom 必须且只能属于一个试验主题：{atom.id}")
        counts.update(themes)
    for theme in THEMES:
        if counts[theme] < 8:
            raise PilotValidationError(f"主题 {theme} 至少需要 8 条 Atom，当前 {counts[theme]}")


def load_mapping(path: Path) -> Mapping[str, tuple[str, ...]]:
    if not path.is_file():
        raise PilotValidationError(f"找不到 task-atom mapping：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PilotValidationError(f"mapping JSON 非法：{exc.msg}") from exc
    if not isinstance(data, Mapping):
        raise PilotValidationError("mapping 必须是 task_id → atom_id[] 对象")
    result: dict[str, tuple[str, ...]] = {}
    for task_id, atom_ids in data.items():
        if isinstance(atom_ids, str) or not isinstance(atom_ids, Sequence):
            raise PilotValidationError(f"mapping[{task_id}] 必须是 Atom ID 数组")
        cleaned = tuple(str(atom_id).strip() for atom_id in atom_ids)
        if not cleaned or any(not value for value in cleaned):
            raise PilotValidationError(f"mapping[{task_id}] 不能为空")
        result[str(task_id)] = cleaned
    return result


def validate_mapping(
    tasks: Sequence[PilotTask],
    atoms: Sequence[KnowledgeAtomV2],
    mapping: Mapping[str, tuple[str, ...]],
) -> None:
    task_by_id = {task.id: task for task in tasks}
    atom_by_id = {atom.id: atom for atom in atoms}
    unknown_tasks = set(mapping).difference(task_by_id)
    if unknown_tasks:
        raise PilotValidationError(f"mapping 含未知 Task：{', '.join(sorted(unknown_tasks))}")
    for task in tasks:
        atom_ids = mapping.get(task.id)
        if not atom_ids:
            raise PilotValidationError(f"Task 未映射 Atom：{task.id}")
        for atom_id in atom_ids:
            atom = atom_by_id.get(atom_id)
            if atom is None:
                raise PilotValidationError(f"mapping 含未知 Atom：{atom_id}")
            if task.theme not in _atom_themes(atom):
                raise PilotValidationError(f"Task 与 Atom 主题不匹配：{task.id} → {atom_id}")


def render_task(task: PilotTask) -> str:
    return "\n".join(
        [
            f"## 用户问题\n{task.request}",
            f"## 业务背景\n```json\n{json.dumps(dict(task.context), ensure_ascii=False, indent=2, sort_keys=True)}\n```",
            "## 必须处理\n" + "\n".join(f"- {item}" for item in task.must_address),
            "## 禁止断言\n" + "\n".join(f"- {item}" for item in task.forbidden_claims),
            "## 风险检查\n" + "\n".join(f"- {item}" for item in task.risk_checks),
        ]
    )


def render_ledger(atoms: Iterable[KnowledgeAtomV2]) -> str:
    blocks: list[str] = [KNOWLEDGE_HEADER]
    for atom in atoms:
        metrics = [
            f"{metric.name}：{metric.definition}"
            + (f"（{metric.time_window}）" if metric.time_window else "")
            for metric in atom.applicability.metrics
        ]
        blocks.append(
            "\n".join(
                [
                    f"[{atom.id}]",
                    f"判断：{atom.statement}",
                    "成立条件：" + "；".join(atom.applicability.preconditions or ("未提供",)),
                    "建议动作：" + "；".join(atom.applicability.recommended_action or ("未提供",)),
                    "验证指标：" + "；".join(metrics or ("未提供",)),
                    "失效边界：" + "；".join(atom.applicability.counterexamples or ("未提供",)),
                ]
            )
        )
    return "\n\n".join(blocks)


def _prompt(task: PilotTask, atoms: Sequence[KnowledgeAtomV2] = ()) -> str:
    parts = [PROMPT_MARKER, BASE_PROTOCOL, render_task(task)]
    if atoms:
        parts.append(render_ledger(atoms))
    parts.append("## 输出要求\n直接给出判断、动作顺序、验证方法与边界。")
    return "\n\n".join(parts) + "\n"


def _is_inside_repository(path: Path) -> bool:
    resolved = path.resolve()
    if any((candidate / ".git").exists() for candidate in (resolved, *resolved.parents)):
        return True
    try:
        resolved.relative_to(REPOSITORY_ROOT.resolve())
        return True
    except ValueError:
        return False


def prepare_run(
    *,
    tasks: Sequence[PilotTask],
    atoms: Sequence[KnowledgeAtomV2],
    mapping: Mapping[str, tuple[str, ...]],
    output: Path,
    seed: int,
    model_name: str = "",
    host: str = "",
    generated_at: str = "",
    temperature: str = "",
    max_output: int = 0,
    limit: int | None = None,
) -> Path:
    if limit is not None and limit <= 0:
        raise PilotValidationError("limit 必须是正整数")
    selected = tuple(tasks[:limit] if limit is not None else tasks)
    if not selected:
        raise PilotValidationError("prepare 至少需要一个 Task")
    if _is_inside_repository(output):
        raise PilotValidationError("包含私有 Atom 的试验包禁止写入 Git 仓库目录")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PilotValidationError(
            "输出目录非空；请使用新的 run 目录避免覆盖"
        )
    selected_mapping = {task.id: mapping[task.id] for task in selected if task.id in mapping}
    validate_mapping(selected, atoms, selected_mapping)
    atom_by_id = {atom.id: atom for atom in atoms}
    _private_dir(output)
    baseline_dir = output / "generation" / "baseline"
    knowledge_dir = output / "generation" / "knowledge"
    for directory in (baseline_dir, knowledge_dir, output / "blind" / "pairs", output / "results"):
        _private_dir(directory)
    for task in selected:
        mapped = tuple(atom_by_id[atom_id] for atom_id in selected_mapping[task.id])
        write_private_text(baseline_dir / f"{task.id}.md", _prompt(task))
        write_private_text(knowledge_dir / f"{task.id}.md", _prompt(task, mapped))

    task_payload = [task.to_dict() for task in selected]
    atom_payload = [atom.to_dict() for atom in sorted(atoms, key=lambda item: item.id)]
    template_hash = _sha256_text(BASE_PROTOCOL + "\n" + KNOWLEDGE_HEADER)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    manifest = GenerationManifest(
        run_id=output.name,
        model_name=model_name,
        host=host,
        generated_at=timestamp,
        task_hash=_sha256_text(canonical_json(task_payload)),
        atom_corpus_hash=_sha256_text(canonical_json(atom_payload)),
        prompt_template_hash=template_hash,
        temperature=temperature,
        max_output=max_output,
    )
    payload = {
        "manifest": manifest.to_dict(),
        "seed": seed,
        "tasks": task_payload,
        "task_atom_counts": {task.id: len(selected_mapping[task.id]) for task in selected},
    }
    write_private_text(output / "manifest.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return output
