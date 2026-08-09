from __future__ import annotations

import json
from pathlib import Path
import unittest

from siyu_team.eval.models import ScanMode, ScanResult
from siyu_team.eval.static import assert_compliant, scan, scan_result


ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "fixtures" / "compliance-context-cases.jsonl"
APPROVED_ATOMS = (
    ROOT / "knowledge" / "04-atoms" / "growth-layers.approved.jsonl"
)


class ComplianceContextFixtureTests(unittest.TestCase):
    def test_context_cases(self) -> None:
        cases = [
            json.loads(line)
            for line in CASES.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertGreaterEqual(len(cases), 16)

        for case in cases:
            with self.subTest(case=case["id"]):
                result = scan(case["text"], mode=ScanMode(case["mode"]))
                self.assertEqual(case["hard_fail"], result["hard_fail"])
                for flag in case["must_flags"]:
                    self.assertIn(flag, result["flags"])
                for flag in case["forbid_flags"]:
                    self.assertNotIn(flag, result["flags"])
                self._assert_explainable_hits(case["text"], case["mode"], result)

    def _assert_explainable_hits(
        self, text: str, mode: str, result: dict[str, object]
    ) -> None:
        details = result["details"]
        self.assertIsInstance(details, list)
        for detail in details:
            self.assertIsInstance(detail, dict)
            assert isinstance(detail, dict)
            for key in (
                "offset",
                "snippet",
                "rule",
                "mode",
                "severity",
                "hard",
                "soft",
            ):
                self.assertIn(key, detail)
            self.assertEqual(mode, detail["mode"])
            self.assertNotEqual(detail["hard"], detail["soft"])
            offset = detail["offset"]
            end = detail["end"]
            self.assertIsInstance(offset, int)
            self.assertIsInstance(end, int)
            if isinstance(offset, int) and isinstance(end, int) and offset >= 0:
                self.assertGreater(end, offset)
                self.assertIn(text[offset:end], detail["snippet"])

    def test_scan_result_is_typed_and_scan_remains_compatible(self) -> None:
        structured = scan_result("本品牌全国销量第一", ScanMode.CUSTOMER_COPY)
        self.assertIsInstance(structured, ScanResult)
        self.assertTrue(structured.hard_fail)
        self.assertEqual("customer_copy", structured.to_dict()["mode"])

        legacy = scan("本品牌全国销量第一")
        for key in ("flags", "details", "penalty", "hard_fail"):
            self.assertIn(key, legacy)

    def test_assert_compliant_accepts_mode(self) -> None:
        result = assert_compliant(
            "对方宣称全国第一，尚未核验", ScanMode.INTERNAL_REPORT
        )
        self.assertFalse(result["hard_fail"])

    def test_rules_are_shared_but_mode_policy_differs(self) -> None:
        text = "本品牌全国销量第一"
        customer = scan_result(text, ScanMode.CUSTOMER_COPY)
        knowledge = scan_result(text, ScanMode.KNOWLEDGE)

        self.assertTrue(customer.hard_fail)
        self.assertFalse(knowledge.hard_fail)
        customer_rules = {hit.rule for hit in customer.hits if hit.offset >= 0}
        knowledge_rules = {hit.rule for hit in knowledge.hits if hit.offset >= 0}
        self.assertEqual(customer_rules, knowledge_rules)


class ApprovedKnowledgeComplianceTests(unittest.TestCase):
    def test_all_approved_atoms_have_no_hard_knowledge_conflict(self) -> None:
        atoms = [
            json.loads(line)
            for line in APPROVED_ATOMS.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(35, len(atoms))

        conflicts: list[str] = []
        for atom in atoms:
            text = json.dumps(atom, ensure_ascii=False, sort_keys=True)
            result = scan(text, ScanMode.KNOWLEDGE)
            if result["hard_fail"]:
                hard_rules = [
                    detail["rule"]
                    for detail in result["details"]
                    if detail["hard"]
                ]
                conflicts.append(f"{atom['id']}: {hard_rules}")
        self.assertEqual([], conflicts)


if __name__ == "__main__":
    unittest.main()
