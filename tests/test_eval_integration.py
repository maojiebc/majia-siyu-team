"""Integration coverage for the compliance CLI."""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from siyu_team.eval import cli as eval_cli


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

    def test_compliance_blocks_clear_red_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "copy.md"
            plan.write_text("全国销量第一，转发3个群领券", encoding="utf-8")
            code, output = self._run(["compliance", str(plan), "--json"])

        payload = json.loads(output)
        self.assertEqual(code, 1)
        self.assertFalse(payload["passed"])


class MakeTargetTests(unittest.TestCase):
    def test_compliance_target_never_scores(self) -> None:
        makefile = Path("Makefile").read_text(encoding="utf-8")
        self.assertIn("compliance:", makefile)
        self.assertIn("不产生质量分或徽章", makefile)
        self.assertNotIn("judge:", makefile)


if __name__ == "__main__":
    unittest.main()
