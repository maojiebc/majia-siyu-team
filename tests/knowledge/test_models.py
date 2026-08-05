from __future__ import annotations

import json
from pathlib import Path
import unittest

from siyu_team.knowledge.models import (
    Applicability,
    KnowledgeAtomV2,
    KnowledgeValidationError,
    Lifecycle,
    Metric,
    Privacy,
    Quality,
    Scope,
    SourceRef,
    generate_atom_id,
    generate_source_id,
    migrate_v1_atom,
)


def build_atom(*, visibility: str = "public", client_id: str = "") -> KnowledgeAtomV2:
    source_id = generate_source_id("fixtures/store-execution.md")
    return KnowledgeAtomV2(
        id=generate_atom_id(source_id, "L10-L20", 0),
        statement="加盟门店的执行验收应观察实际动作，而不只看培训签到。",
        type="method",
        topics=("门店执行",),
        skills=("siyu-wenzhen",),
        source=SourceRef(
            source_id=source_id,
            source_type="internal_case",
            label="脱敏复盘",
            path="fixtures/store-execution.md",
            locator="L10-L20",
            observed_at="2026-08-05",
        ),
        scope=Scope(
            visibility=visibility,
            client_id=client_id,
            industry="catering",
            subindustry="chain_franchise",
            business_model="franchise",
            roles=("headquarters", "store_staff"),
        ),
        applicability=Applicability(
            preconditions=("总部无法每日驻店监督",),
            recommended_action=("以门店级实际执行数据验收",),
            metrics=(
                Metric("执行门店覆盖率", "产生有效动作门店数 / 应执行门店数", "滚动7日"),
            ),
            failure_modes=("把培训签到当作执行完成",),
            counterexamples=("总部直营且现场督导充分时可增加过程指标",),
        ),
        quality=Quality("A2", "high", "approved", "maojiebc", "2026-08-05"),
        lifecycle=Lifecycle("2026-08-05"),
        privacy=Privacy(exportable=visibility == "public"),
    )


class KnowledgeModelTests(unittest.TestCase):
    def test_round_trip_preserves_atom(self) -> None:
        atom = build_atom()
        restored = KnowledgeAtomV2.from_json(atom.to_json())
        self.assertEqual(restored, atom)
        self.assertEqual(json.loads(restored.to_json())["schema_version"], "2.0")

    def test_ids_are_stable_and_source_sensitive(self) -> None:
        first_source = generate_source_id("cases/example.md")
        self.assertEqual(first_source, generate_source_id(Path("cases/example.md")))
        self.assertEqual(
            generate_atom_id(first_source, "L1-L3", 2),
            generate_atom_id(first_source, " L1-L3 ", 2),
        )
        self.assertNotEqual(
            generate_atom_id(first_source, "L1-L3", 2),
            generate_atom_id(first_source, "L1-L3", 3),
        )

    def test_approved_requires_human_review_metadata(self) -> None:
        with self.assertRaises(KnowledgeValidationError):
            Quality("A2", "high", "approved")

    def test_client_private_requires_client_and_cannot_export(self) -> None:
        with self.assertRaises(KnowledgeValidationError):
            Scope(visibility="client_private")
        with self.assertRaises(KnowledgeValidationError):
            atom = build_atom(visibility="client_private", client_id="client_a")
            KnowledgeAtomV2(
                **{**atom.__dict__, "privacy": Privacy(exportable=True)}
            )

    def test_unknown_fields_fail_closed(self) -> None:
        data = build_atom().to_dict()
        data["surprise"] = True
        with self.assertRaises(KnowledgeValidationError):
            KnowledgeAtomV2.from_dict(data)

    def test_v1_migration_is_draft_and_not_exportable(self) -> None:
        legacy = {
            "id": "2026Q3_001",
            "knowledge": "欢迎语应先说明身份和价值。",
            "original": "原始摘录",
            "source": "脱敏案例/欢迎语.md",
            "date": "2026-07-01",
            "topics": ["话术"],
            "skills": ["siyu-huashu"],
            "type": "method",
            "confidence": "medium",
        }
        migrated = migrate_v1_atom(legacy, local_index=1)
        self.assertEqual(migrated.quality.review_status, "draft")
        self.assertFalse(migrated.privacy.exportable)
        self.assertEqual(migrated.source.source_type, "legacy")
        self.assertEqual(migrated, migrate_v1_atom(legacy, local_index=1))


if __name__ == "__main__":
    unittest.main()
