#!/usr/bin/env python3
"""从 L0/L1 Markdown 生成 growth-layers.draft.jsonl（KnowledgeAtomV2 draft）。"""
from __future__ import annotations

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
    Metric,
    Privacy,
    Quality,
    Scope,
    SourceRef,
)

SECTION_RE = re.compile(r"^### (L0-\d+|L1-C\d+|L1-\d+)\s+(.+)$", re.M)
FIELD_RE = re.compile(r"^- \*\*(.+?)：\*\*\s*(.+)$", re.M)


def _parse_sections(text: str) -> list[dict[str, str]]:
    matches = list(SECTION_RE.finditer(text))
    out: list[dict[str, str]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        fields = {"id": m.group(1), "title": m.group(2).strip()}
        # 判断
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
                line = re.sub(r"^\*\*判断：\*\*\s*", "", line)
                if line.startswith("**判断**"):
                    line = re.sub(r"^\*\*判断\*\*[：:]\s*", "", line)
                if line:
                    fields["statement"] = line
                    break
        # final clean
        if "statement" in fields:
            s = fields["statement"]
            s = re.sub(r"^\*\*判断：\*\*\s*", "", s)
            s = re.sub(r"^\*\*判断\*\*[：:]\s*", "", s)
            fields["statement"] = s.strip()
        for fm in FIELD_RE.finditer(body):
            key, val = fm.group(1).strip(), fm.group(2).strip()
            fields[key] = val
        if fields.get("statement"):
            out.append(fields)
    return out


def _type_of(title: str, body_fields: dict[str, str]) -> str:
    t = title + body_fields.get("statement", "")
    if "反面" in title or "不是核心" in t or "禁止" in t[:20]:
        return "anti-pattern"
    if title.startswith("L1-C") or "原则" in title:
        return "principle"
    return "method"


def _skills_from(text: str) -> list[str]:
    # lightweight defaults
    skills = ["siyu-wenzhen"]
    blob = text
    if any(k in blob for k in ("拉新", "渠道", "实验", "断点", "活动")):
        skills.append("ops-as-ad-funnel")
    if any(k in blob for k in ("成本", "指标", "转化", "贡献", "口径")):
        skills.append("conversion-caliber")
    if any(k in blob for k in ("召回", "沉默", "休眠")):
        skills.append("reactivation-playbook")
    if any(k in blob for k in ("合规", "分享")):
        skills.append("wechat-compliance-redlines")
    if any(k in blob for k in ("群", "分群", "社群")):
        skills.append("siyu-qunfa")
    # unique keep order
    seen = []
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
    observed_at: str = "2026-08-06",
) -> KnowledgeAtomV2:
    locator = fields["id"]
    statement = fields["statement"]
    title = fields.get("title", "")
    action = fields.get("怎么干", fields.get("建议动作", ""))
    failure = fields.get("失效", fields.get("常见翻车", ""))
    boundary = fields.get("边界", fields.get("失效边界", ""))
    why = fields.get("原始依据", fields.get("来源", ""))
    atom_type = _type_of(title, fields)
    preconditions = []
    if why:
        preconditions.append(f"依据：{why[:120]}")
    if industry:
        preconditions.append(f"业态层：{industry}")
    else:
        preconditions.append("业态：通用（L0）")
    recommended = [action] if action else []
    failure_modes = [failure] if failure else []
    counterexamples = [boundary] if boundary else []
    metrics = []
    # optional metric line not structured — skip
    scope_industry = industry
    return KnowledgeAtomV2(
        id=growth_atom_id(doc_path, locator, 0),
        statement=statement,
        type=atom_type,
        topics=(layer_topic, "用户增长"),
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
            industry=scope_industry,
            business_model="franchise" if industry == "catering" else "",
            channels=("wecom_friend", "wecom_group", "instore") if industry else (),
            scenarios=("user_growth",),
        ),
        applicability=Applicability(
            preconditions=tuple(preconditions),
            recommended_action=tuple(recommended),
            metrics=tuple(metrics),
            failure_modes=tuple(failure_modes),
            counterexamples=tuple(counterexamples),
        ),
        quality=Quality(
            evidence_grade="C1",
            confidence="medium",
            review_status="draft",
        ),
        lifecycle=Lifecycle(valid_from=observed_at),
        privacy=Privacy(exportable=False),
    )


def main() -> int:
    l0_path = ROOT / L0_DOC
    l1_path = ROOT / L1_CATERING_DOC
    l0_sections = _parse_sections(l0_path.read_text(encoding="utf-8"))
    l1_sections = _parse_sections(l1_path.read_text(encoding="utf-8"))
    atoms: list[KnowledgeAtomV2] = []
    for sec in l0_sections:
        atoms.append(
            build_atom(doc_path=L0_DOC, fields=sec, layer_topic=L0_TOPIC, industry="")
        )
    for sec in l1_sections:
        atoms.append(
            build_atom(
                doc_path=L1_CATERING_DOC,
                fields=sec,
                layer_topic=L1_CATERING_TOPIC,
                industry="catering",
            )
        )
    out = ROOT / "knowledge" / "04-atoms" / "growth-layers.draft.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(a.to_dict(), ensure_ascii=False, separators=(",", ":")) for a in atoms]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} atoms={len(atoms)} l0={len(l0_sections)} l1={len(l1_sections)}")
    # print sample ids
    for a in atoms[:3]:
        print(a.source.locator, a.id, a.statement[:40])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
