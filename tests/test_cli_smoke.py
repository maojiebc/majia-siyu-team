"""合规扫描 CLI 的冒烟测试。

任何输入（含缺失文件、glob 展开的多文件）都必须得到中文错误与退出码，
不允许裸 traceback。
"""
from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from siyu_team.eval import cli as eval_cli


class TestEvalCli(unittest.TestCase):
    def _run(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                eval_cli.main(argv)
        code = ctx.exception.code
        return (code if isinstance(code, int) else 1), out.getvalue()

    def test_compliance_single_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp) / "01-方案.md"
            plan.write_text("周三会员日常规提醒，报名以实际到店为准。", encoding="utf-8")
            code, _ = self._run(["compliance", str(plan)])
        self.assertEqual(code, 0)

    def test_compliance_multiple_files_glob_style(self) -> None:
        # shell 展开 FILE=*.md 成多参数时，必须能吃多文件而不是 argparse 直接崩。
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for name in ("02-公关官.md", "02-产品官.md"):
                path = Path(tmp) / name
                path.write_text("会员分层触达方案，先小范围试点再放量。", encoding="utf-8")
                paths.append(str(path))
            code, out = self._run(["compliance", *paths])
        self.assertEqual(code, 0)
        self.assertIn("整体结果", out)

    def test_compliance_missing_file_exits_2(self) -> None:
        code, _ = self._run(["compliance", "/nonexistent/没有这个文件.md"])
        self.assertEqual(code, 2)

    def test_validate_plugins(self) -> None:
        code, out = self._run(["validate", "plugins/"])
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
