"""贡献预览生成：只提交用户事实，模型推断与既有知识仅展示来源标签。"""
from __future__ import annotations

import hashlib
import json

from .models import ContributionCandidate, ContributionPreview
from .privacy import scan_fields


def build_preview(candidate: ContributionCandidate) -> ContributionPreview:
    fields: list[tuple[str, str]] = []
    for index, fact in enumerate(candidate.user_facts):
        fields.append((f"user_facts[{index}]", fact))
    fields.extend(
        [
            ("summary", candidate.summary),
            ("scene", candidate.scene),
            ("result", candidate.result),
        ]
    )
    fields.extend((f"actions[{index}]", value) for index, value in enumerate(candidate.actions))
    fields.extend(
        (f"boundaries[{index}]", value)
        for index, value in enumerate(candidate.boundaries)
    )
    scan = scan_fields(fields)
    canonical = json.dumps(
        candidate.submission_content(),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    preview_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ContributionPreview(
        candidate=candidate,
        safe=scan.safe,
        warnings=scan.warnings,
        redacted_fields=scan.affected_fields,
        preview_hash=preview_hash,
    )
