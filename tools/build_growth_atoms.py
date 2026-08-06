#!/usr/bin/env python3
"""从 L0/L1 Markdown 生成增长原子 JSONL（approved 正式集 + 可选 draft）。"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siyu_team.knowledge.growth_layers import (  # noqa: E402
    L0_DOC,
    L0_TOPIC,
    L1_CATERING_DOC,
    L1_CATERING_TOPIC,
    growth_atom_id,
    growth_source_id,
)
from siyu_team.knowledge.models import (  # noqa: E402
    Applicability,
    KnowledgeAtomV2,
    Lifecycle,
    Privacy,
    Quality,
    Scope,
    SourceRef,
)
from siyu_team.pilot.models import THEMES  # noqa: E402

SECTION_RE = re.compile(r"^### (L0-\d+|L1-C\d+|L1-\d+)\s+(.+)$", re.M)
FIELD_RE = re.compile(r"^- \*\*(.+?)：\*\*\s*(.+)$", re.M)

# 每个逻辑 id 绑定唯一 Pilot 主题（add_wechat / activity_increment / repurchase_recall）
PILOT_THEME_BY_LOCATOR: dict[str, str] = {
    # L0 → 拉新 / 活动 / 召回
    "L0-01": "add_wechat",
    "L0-02": "add_wechat",
    "L0-03": "add_wechat",
    "L0-04": "add_wechat",
    "L0-05": "repurchase_recall",
    "L0-06": "repurchase_recall",
    "L0-07": "repurchase_recall",
    "L0-08": "activity_increment",
    "L0-09": "activity_increment",
    "L0-10": "activity_increment",
    "L0-11": "activity_increment",
    "L0-12": "activity_increment",
    "L0-13": "repurchase_recall",
    "L0-14": "activity_increment",
    "L0-15": "add_wechat",
    "L0-16": "repurchase_recall",
    # L1 约束 + 方法
    "L1-C01": "add_wechat",
    "L1-C02": "add_wechat",
    "L1-C03": "activity_increment",
    "L1-C04": "repurchase_recall",
    "L1-C05": "repurchase_recall",
    "L1-01": "activity_increment",
    "L1-02": "add_wechat",
    "L1-03": "add_wechat",
    "L1-04": "add_wechat",
    "L1-05": "repurchase_recall",
    "L1-06": "activity_increment",
    "L1-07": "activity_increment",
    "L1-08": "repurchase_recall",
    "L1-09": "activity_increment",
    "L1-10": "repurchase_recall",
    "L1-11": "add_wechat",
    "L1-12": "repurchase_recall",
    "L1-13": "add_wechat",
    "L1-14": "repurchase_recall",
}


def _parse_sections(text: str) -> list[dict[str, str]]:
    matches = list(SECTION_RE.finditer(text))
    out: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        fields = {"id": m.group(1), "title": m.group(2).strip()}
        jm = re.search(r"^- \*\*判断：\*\*\s*(.+)$", body, re.M)
        if jm:
            fields["statement"] = jm.group(1).strip()
        else:
            for line in body.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("|"):
                    continue
                line = re.sub(r"^\*\*判断：\*\*\s*", "", line)
                line = line.lstrip("- ").strip()
                line = re.sub(r"^\*\*判断\*\*[：:]\s*", "", line)
                if line:
                    fields["statement"] = line
                    break
        for fm in FIELD_RE.finditer(body):
            fields[fm.group(1).strip()] = fm.group(2).strip()
        if fields.get("statement"):
            s = fields["statement"]
            s = re.sub(r"^\*\*判断：\*\*\s*", "", s)
            s = re.sub(r"^\*\*判断\*\*[：:]\s*", "", s)
            fields["statement"] = s.strip()
            out.append(fields)
    return out


def _type_of(title: str) -> str:
    if "反面" in title or "不是核心" in title:
        return "anti-pattern"
    if title.startswith("L1-C") or "原则" in title:
        return "principle"
    return "method"


def _skills_from(text: str) -> list[str]:
    skills = ["siyu-wenzhen"]
    if any(k in text for k in ("拉新", "渠道", "实验", "断点", "活动", "加微", "扫码")):
        skills.append("ops-as-ad-funnel")
    if any(k in text for k in ("成本", "指标", "转化", "贡献", "口径")):
        skills.append("conversion-caliber")
    if any(k in text for k in ("召回", "沉默", "休眠", "再来")):
        skills.append("reactivation-playbook")
    if any(k in text for k in ("合规", "分享")):
        skills.append("wechat-compliance-redlines")
    if any(k in text for k in ("群", "分群", "社群")):
        skills.append("siyu-qunfa")
    seen: list[str] = []
    for s in skills:
        if s not in seen:
            seen.append(s)
    return seen


def build_atom(
    *,
    doc_path: str,
    fields: dict[str, str],
    layer_topic: str,
    industry: str,
    approved: bool,
    observed_at: str = "2026-08-06",
    reviewer: str = "maojiebc",
) -> KnowledgeAtomV2:
    locator = fields["id"]
    if locator not in PILOT_THEME_BY_LOCATOR:
        raise SystemExit(f"locator 未映射 Pilot 主题：{locator}")
    pilot_theme = PILOT_THEME_BY_LOCATOR[locator]
    if pilot_theme not in THEMES:
        raise SystemExit(f"非法主题 {pilot_theme}")

    statement = fields["statement"]
    title = fields.get("title", "")
    action = fields.get("怎么干", fields.get("建议动作", ""))
    failure = fields.get("失效", fields.get("常见翻车", ""))
    boundary = fields.get("边界", fields.get("失效边界", ""))
    why = fields.get("原始依据", fields.get("来源", ""))
    atom_type = _type_of(locator + title)
    preconditions = []
    if why:
        preconditions.append(f"依据：{why[:160]}")
    preconditions.append("业态：通用（L0）" if not industry else f"业态层：{industry}")
    recommended = [action] if action else []
    failure_modes = [failure] if failure else []
    counterexamples = [boundary] if boundary else []

    quality = (
        Quality(
            evidence_grade="C1",
            confidence="medium",
            review_status="approved",
            reviewer=reviewer,
            reviewed_at=observed_at,
        )
        if approved
        else Quality(
            evidence_grade="C1",
            confidence="medium",
            review_status="draft",
        )
    )
    return KnowledgeAtomV2(
        id=growth_atom_id(doc_path, locator, 0),
        statement=statement,
        type=atom_type,
        # 恰好一个 Pilot 主题 + 分层标签
        topics=(pilot_theme, layer_topic, "用户增长"),
        skills=tuple(_skills_from(statement + action + title)),
        source=SourceRef(
            source_id=growth_source_id(doc_path),
            source_type="expert_judgment",
            label=Path(doc_path).name,
            path=doc_path,
            locator=locator,
            observed_at=observed_at,
        ),
        scope=Scope(
            visibility="public",
            industry=industry,
            business_model="franchise" if industry == "catering" else "",
            channels=("wecom_friend", "wecom_group", "instore") if industry else (),
            scenarios=("user_growth", pilot_theme),
        ),
        applicability=Applicability(
            preconditions=tuple(preconditions),
            recommended_action=tuple(recommended),
            metrics=(),
            failure_modes=tuple(failure_modes),
            counterexamples=tuple(counterexamples),
        ),
        quality=quality,
        lifecycle=Lifecycle(valid_from=observed_at),
        privacy=Privacy(exportable=bool(approved)),
    )


def _write_jsonl(path: Path, atoms: list[KnowledgeAtomV2]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(a.to_dict(), ensure_ascii=False, separators=(",", ":")) for a in atoms
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_task_map(atoms: list[KnowledgeAtomV2], tasks_path: Path) -> dict[str, list[str]]:
    """每个 Golden Task 映射同主题的 2～3 条增长原子。"""
    by_theme: dict[str, list[str]] = {t: [] for t in THEMES}
    for atom in atoms:
        for theme in THEMES:
            if theme in atom.topics:
                by_theme[theme].append(atom.id)
                break
    mapping: dict[str, list[str]] = {}
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        theme = task["theme"]
        pool = by_theme[theme]
        # stable pick 3 by hashing task id
        if not pool:
            continue
        idx = sum(ord(c) for c in task["id"]) % len(pool)
        picked = [pool[idx], pool[(idx + 1) % len(pool)], pool[(idx + 2) % len(pool)]]
        # unique preserve order
        seen: list[str] = []
        for a in picked:
            if a not in seen:
                seen.append(a)
        mapping[task["id"]] = seen
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewer", default="maojiebc")
    parser.add_argument("--date", default="2026-08-06")
    parser.add_argument("--keep-draft", action="store_true", help="同时写出 draft 副本")
    args = parser.parse_args()

    l0_sections = _parse_sections((ROOT / L0_DOC).read_text(encoding="utf-8"))
    l1_sections = _parse_sections((ROOT / L1_CATERING_DOC).read_text(encoding="utf-8"))

    approved: list[KnowledgeAtomV2] = []
    for sec in l0_sections:
        approved.append(
            build_atom(
                doc_path=L0_DOC,
                fields=sec,
                layer_topic=L0_TOPIC,
                industry="",
                approved=True,
                observed_at=args.date,
                reviewer=args.reviewer,
            )
        )
    for sec in l1_sections:
        approved.append(
            build_atom(
                doc_path=L1_CATERING_DOC,
                fields=sec,
                layer_topic=L1_CATERING_TOPIC,
                industry="catering",
                approved=True,
                observed_at=args.date,
                reviewer=args.reviewer,
            )
        )

    approved_path = ROOT / "knowledge" / "04-atoms" / "growth-layers.approved.jsonl"
    _write_jsonl(approved_path, approved)

    if args.keep_draft:
        draft = [
            build_atom(
                doc_path=a.source.path,
                fields={
                    "id": a.source.locator,
                    "title": "",
                    "statement": a.statement,
                    "怎么干": (a.applicability.recommended_action or ("",))[0],
                    "失效": (a.applicability.failure_modes or ("",))[0],
                    "边界": (a.applicability.counterexamples or ("",))[0],
                },
                layer_topic=L0_TOPIC if L0_TOPIC in a.topics else L1_CATERING_TOPIC,
                industry=a.scope.industry,
                approved=False,
                observed_at=args.date,
            )
            for a in approved
        ]
        _write_jsonl(ROOT / "knowledge" / "04-atoms" / "growth-layers.draft.jsonl", draft)
    else:
        # 正式集取代 draft：draft 指向说明文件或删除后写 stub 注释
        draft_path = ROOT / "knowledge" / "04-atoms" / "growth-layers.draft.jsonl"
        if draft_path.exists():
            draft_path.unlink()

    # Pilot 夹具：正式集副本 + task map
    fixture_atoms = ROOT / "tests" / "fixtures" / "pilot" / "growth-approved-atoms.jsonl"
    _write_jsonl(fixture_atoms, approved)
    tasks_path = ROOT / "tests" / "fixtures" / "pilot" / "golden-tasks.jsonl"
    mapping = build_task_map(approved, tasks_path)
    map_path = ROOT / "tests" / "fixtures" / "pilot" / "growth-task-atom-map.json"
    map_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # theme counts
    from collections import Counter

    c = Counter()
    for a in approved:
        for th in THEMES:
            if th in a.topics:
                c[th] += 1
    print(
        f"approved={approved_path} n={len(approved)} themes={dict(c)} "
        f"fixture={fixture_atoms.name} map={map_path.name}"
    )
    for a in approved[:2]:
        print(a.source.locator, a.id, a.quality.review_status, a.topics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
