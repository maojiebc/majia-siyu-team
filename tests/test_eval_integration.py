"""Integration coverage for the separated compliance and Judge semantics."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from siyu_team.eval import cli as eval_cli
from siyu_team.eval.engine import composite
from siyu_team.eval.models import JudgeReport
from siyu_team.eval.rubrics import DIMENSION_WEIGHTS


SAFE_PLAN = "会员触达方案：店长负责；按到店人数/触达人数计算到店率，先小范围验证。"


class EvalCliIntegrationTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as raised:
                eval_cli.main(argv)
        code = raised.exception.code
        return (code if isinstance(code, int) else 1), output.getvalue()

    def test_compliance_json_has_no_quality_score_or_badge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(SAFE_PLAN, encoding="utf-8")
            code, output = self._run(["compliance", str(plan), "--json"])

        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["report_type"], "compliance")
        self.assertNotIn("score", payload)
        self.assertNotIn("badge", payload)
        self.assertNotIn("penalty", payload)

    def test_compliance_output_excludes_roughness_heuristics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "short.md"
            plan.write_text("先小范围验证。", encoding="utf-8")
            code, output = self._run(["compliance", str(plan), "--json"])

        payload = json.loads(output)
        self.assertEqual(code, 0)
        report = payload["files"][0]
        self.assertEqual(report["flags"], [])
        self.assertEqual(report["hits"], [])

    def test_deprecated_score_is_a_compliance_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(SAFE_PLAN, encoding="utf-8")
            code, output = self._run(["score", str(plan)])

        self.assertEqual(code, 0)
        self.assertIn("deprecated", output)
        self.assertIn("静态合规检查", output)
        self.assertNotIn("Platinum", output)
        self.assertNotIn("Gold", output)

    def test_emit_prompts_does_not_create_judge_report_or_badge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(SAFE_PLAN, encoding="utf-8")
            code, output = self._run(["judge", str(plan), "--emit-prompts"])

        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(set(payload), set(DIMENSION_WEIGHTS))
        self.assertNotIn("score", payload)
        self.assertNotIn("badge", payload)

    def test_legacy_scores_cannot_create_quality_score_or_badge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(SAFE_PLAN, encoding="utf-8")
            scores = Path(tmp) / "legacy-scores.json"
            scores.write_text(
                json.dumps({dim: 0.9 for dim in DIMENSION_WEIGHTS}),
                encoding="utf-8",
            )
            code, output = self._run(
                ["judge", str(plan), "--scores", str(scores)]
            )

        payload = json.loads(output)
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "not_evaluated")
        self.assertIsNone(payload["score"])
        self.assertIsNone(payload["badge"])
        self.assertFalse(payload["config"]["metadata_complete"])

    def test_complete_independent_envelope_creates_judge_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text(SAFE_PLAN, encoding="utf-8")
            scores = Path(tmp) / "judge-scores.json"
            scores.write_text(
                json.dumps(
                    {
                        "model": "host-model-test",
                        "config": {"temperature": 0, "prompt_version": "1"},
                        "reviewed_at": "2026-08-09T08:00:00Z",
                        "review_method": "independent_host_judge",
                        "scores": {
                            dim: {"score": 0.9, "why": f"{dim} 有可核验依据"}
                            for dim in DIMENSION_WEIGHTS
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            code, output = self._run(
                ["judge", str(plan), "--scores", str(scores)]
            )

        payload = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(payload["status"], "passed")
        self.assertEqual(payload["score"], 90.0)
        self.assertIsNotNone(payload["badge"])
        self.assertNotIn("案例库", payload["badge"])
        self.assertNotIn("知识", payload["badge"])
        self.assertTrue(payload["config"]["metadata_complete"])
        self.assertFalse(
            payload["config"]["automatic_case_or_knowledge_approval"]
        )

    def test_partial_composite_has_neither_score_nor_badge(self) -> None:
        result = composite({"合规安全": 0.9})
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["score"])
        self.assertIsNone(result["badge"])

    def test_complete_scores_still_need_report_metadata_for_badge(self) -> None:
        result = composite({dim: 0.9 for dim in DIMENSION_WEIGHTS})
        self.assertEqual(result["score"], 90.0)
        self.assertIsNone(result["badge"])

    def test_completed_report_contract_rejects_missing_reasons(self) -> None:
        with self.assertRaises(ValueError):
            JudgeReport(
                status="passed",
                source="plan.md",
                model="test-model",
                config={"metadata_complete": True},
                reviewed_at="2026-08-09T08:00:00Z",
                review_method="independent_host_judge",
                scores={dim: 0.9 for dim in DIMENSION_WEIGHTS},
                reasons={},
                score=90.0,
                badge="Gold 独立评审通过",
            )


class OrchestrationContractTests(unittest.TestCase):
    def test_make_targets_have_separate_semantics(self) -> None:
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("compliance:", makefile)
        self.assertIn("judge:", makefile)
        self.assertIn("make eval 已 deprecated", makefile)
        self.assertIn("--mode knowledge", makefile)

    def test_orchestrator_orders_compliance_judge_then_host(self) -> None:
        command = Path(
            "plugins/_orchestrator/commands/siyu-onboard.md"
        ).read_text(encoding="utf-8")
        compliance = command.index("## Step 3a · 静态合规门")
        judge = command.index("## Step 3b · 独立 Judge")
        host = command.index("## Step 3c · 主持收口")
        self.assertLess(compliance, judge)
        self.assertLess(judge, host)
        self.assertIn("本轮未做独立质量评分", command)
        self.assertIn("禁止传 `00-intake.md`", command)
        self.assertIn("不得自动批准案例入库或知识原子", command)


if __name__ == "__main__":
    unittest.main()
