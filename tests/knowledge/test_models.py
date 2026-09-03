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

    def test_optional_modifiers_default_and_missing_fields_stay_valid(self) -> None:
        atom = build_atom()
        self.assertEqual(atom.scope.business_model, "franchise")
        self.assertEqual(atom.scope.scale_band, ("any",))
        self.assertEqual(atom.scope.org_layers, "any")
        self.assertEqual(atom.applicability.execution_boundary, "any")

        payload = atom.to_dict()
        payload["scope"].pop("scale_band")
        payload["scope"].pop("org_layers")
        payload["applicability"].pop("execution_boundary")
        payload["scope"]["business_model"] = ""
        restored = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(restored.scope.business_model, "any")
        self.assertEqual(restored.scope.scale_band, ("any",))
        self.assertEqual(restored.scope.org_layers, "any")
        self.assertEqual(restored.applicability.execution_boundary, "any")

        payload["scope"]["business_model"] = "franchise"
        payload["scope"]["scale_band"] = ["1", "2-10"]
        payload["scope"]["org_layers"] = "regional"
        payload["applicability"]["execution_boundary"] = "hq_tools_incentives"
        scoped = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(scoped.scope.scale_band, ("1", "2-10"))
        self.assertEqual(scoped.scope.org_layers, "regional")
        self.assertEqual(scoped.applicability.execution_boundary, "hq_tools_incentives")

    def test_community_extensions_are_optional_and_round_trip(self) -> None:
        payload = build_atom().to_dict()
        payload["type"] = "platform_workaround"
        payload["source"]["source_type"] = "community"
        payload["quality"]["evidence_grade"] = "C"
        payload["quality"]["confirmations"] = [
            {
                "contributor_hash": "a" * 64,
                "company_hash": "b" * 64,
                "confirmed_at": "2026-09-01",
            }
        ]
        payload["quality"]["platform_rule_risk"] = "medium"
        payload["quality"]["review_notes"] = "类别未知，内测宽松收录"
        atom = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(atom.type, "platform_workaround")
        self.assertEqual(atom.quality.evidence_grade, "C")
        self.assertEqual(atom.quality.platform_rule_risk, "medium")
        self.assertEqual(atom.quality.review_notes, "类别未知，内测宽松收录")
        self.assertEqual(len(atom.quality.confirmations), 1)
        restored = KnowledgeAtomV2.from_json(atom.to_json())
        self.assertEqual(restored, atom)

    def test_invalid_modifier_enums_fail_closed(self) -> None:
        payload = build_atom().to_dict()
        payload["scope"]["business_model"] = "joint_venture"
        with self.assertRaises(KnowledgeValidationError):
            KnowledgeAtomV2.from_dict(payload)
        payload = build_atom().to_dict()
        payload["scope"]["scale_band"] = ["0-3"]
        with self.assertRaises(KnowledgeValidationError):
            KnowledgeAtomV2.from_dict(payload)
        payload = build_atom().to_dict()
        payload["scope"]["scale_band"] = ["300+"]
        with self.assertRaises(KnowledgeValidationError):
            KnowledgeAtomV2.from_dict(payload)
        payload = build_atom().to_dict()
        payload["scope"]["scale_band"] = ["5000+", "301-1000"]
        payload["scope"]["channels"] = ["wecom", "miniprogram_member"]
        payload["source"]["contributor_role"] = "hq"
        expanded = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(expanded.scope.scale_band, ("5000+", "301-1000"))
        self.assertEqual(expanded.scope.channels, ("wecom", "miniprogram_member"))
        self.assertEqual(expanded.source.contributor_role, "hq")
        payload = build_atom().to_dict()
        payload["source"].pop("contributor_role")
        restored = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(restored.source.contributor_role, "unknown")
        payload = build_atom().to_dict()
        payload["source"]["contributor_display_name"] = "江南茶社小林"
        payload["quality"]["confirmations"] = [
            {
                "contributor_hash": "a" * 64,
                "company_hash": "b" * 64,
                "confirmed_at": "2026-08-01",
                "display_name": "江南茶社小林",
            }
        ]
        named = KnowledgeAtomV2.from_dict(payload)
        self.assertEqual(named.source.contributor_display_name, "江南茶社小林")
        self.assertEqual(named.quality.confirmations[0].display_name, "江南茶社小林")
        self.assertNotIn("contributor_display_name", build_atom().to_dict()["source"])

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
