"""三个 CLI 入口的冒烟测试。

这里是 ``[project.scripts]`` 暴露的全部用户表面：任何输入（含损坏文件、
拼错参数、glob 展开的多文件）都必须得到中文错误与退出码，不允许裸 traceback。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from siyu_team import cli as plan_cli
from siyu_team.eval import cli as eval_cli
from siyu_team.pilot import cli as pilot_cli
from siyu_team.task import TaskValidationError, parse_task


class TestParseTaskHints(unittest.TestCase):
    def test_unknown_hint_key_rejected(self) -> None:
        # 拼错的 hint 键静默落默认值＝静默错路由，必须 fail-closed。
        with self.assertRaises(TaskValidationError):
            parse_task("帮我看看会员活动", {"industy": "catering"})

    def test_known_hint_keys_still_pass(self) -> None:
        task = parse_task("写周三会员日方案", {"industry": "catering", "stage": "冷启动"})
        self.assertEqual(task.industry, "catering")
        self.assertEqual(task.stage, "冷启动")


class TestPlanCli(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = plan_cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_plan_outputs_json(self) -> None:
        code, out, _ = self._run(["帮我写一条周三会员日朋友圈文案", "--no-trace"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("task", payload)
        self.assertIn("decision", payload)

    def test_missing_request_exits_2(self) -> None:
        code, _, err = self._run([])
        self.assertEqual(code, 2)
        self.assertIn("request", err)

    def test_trace_dir_is_wired(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            trace_dir = Path(tmp) / "custom-traces"
            code, _, _ = self._run(
                ["帮我写一条朋友圈文案", "--trace-dir", str(trace_dir)]
            )
            self.assertEqual(code, 0)
            written = list(trace_dir.rglob("*.jsonl"))
            self.assertTrue(written, "--trace-dir 应真实生效，而不是被静默忽略")

    def test_broken_knowledge_file_friendly_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            atoms_dir = Path(tmp) / "04-atoms"
            atoms_dir.mkdir(parents=True)
            (atoms_dir / "growth-layers.approved.jsonl").write_text(
                "{这不是合法JSON\n", encoding="utf-8"
            )
            old = os.environ.get("SIYU_KNOWLEDGE_HOME")
            os.environ["SIYU_KNOWLEDGE_HOME"] = tmp
            try:
                code, _, err = self._run(["为什么转化率低", "--no-trace"])
            finally:
                if old is None:
                    os.environ.pop("SIYU_KNOWLEDGE_HOME", None)
                else:
                    os.environ["SIYU_KNOWLEDGE_HOME"] = old
        self.assertEqual(code, 2)
        self.assertIn("知识文件损坏", err)


class TestEvalCli(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                eval_cli.main(argv)
        code = ctx.exception.code
        return (code if isinstance(code, int) else 1), out.getvalue()

    def test_score_single_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "01-方案.md"
            plan.write_text("周三会员日常规提醒，报名以实际到店为准。", encoding="utf-8")
            code, _ = self._run(["score", str(plan), "--threshold", "0"])
        self.assertEqual(code, 0)

    def test_score_multiple_files_glob_style(self) -> None:
        # 编排文档用 make eval FILE=.siyu-team/02*.md，shell 展开成多参数，
        # score 必须能吃多文件而不是 argparse 直接崩。
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name in ("02-公关官.md", "02-产品官.md"):
                path = Path(tmp) / name
                path.write_text("会员分层触达方案，先小范围试点再放量。", encoding="utf-8")
                paths.append(str(path))
            code, out = self._run(["score", *paths, "--threshold", "0"])
        self.assertEqual(code, 0)
        self.assertIn("整体结果", out)

    def test_score_missing_file_exits_2(self) -> None:
        code, _ = self._run(["score", "/nonexistent/没有这个文件.md"])
        self.assertEqual(code, 2)

    def test_judge_bad_samples_friendly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "plan.md"
            plan.write_text("会员召回方案，分三步执行。", encoding="utf-8")
            scores = Path(tmp) / "scores.json"
            scores.write_text(
                json.dumps({dim: 0.9 for dim in (
                    "转化口径严谨度", "合规安全", "可落地性", "SOP完整度",
                    "ROI可验证", "触发精准度", "资源校准", "风格一致",
                )}, ensure_ascii=False),
                encoding="utf-8",
            )
            bad_samples = Path(tmp) / "samples.json"
            bad_samples.write_text('[{"score": "abc"}]', encoding="utf-8")
            code, out = self._run(
                ["judge", str(plan), "--scores", str(scores), "--samples", str(bad_samples)]
            )
        self.assertEqual(code, 2)
        self.assertIn("蒙卡样本解析失败", out)


class TestPilotCli(unittest.TestCase):
    def test_validate_fixtures(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pilot_cli.main(["validate", "--fixtures"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
