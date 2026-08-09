"""Source and installed-bundle parity for execution compliance lints."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUGS = ("siyu-pyq", "siyu-qunfa", "siyu-huashu")
SCRIPT_NAMES = {
    "siyu-pyq": "pyq_lint.py",
    "siyu-qunfa": "qunfa_lint.py",
    "siyu-huashu": "huashu_lint.py",
}


class ExecutionLintParityTests(unittest.TestCase):
    def _run(self, path: Path, text: str, *, isolated: bool = False) -> int:
        command = [sys.executable]
        if isolated:
            # ``-I`` ignores PYTHONDONTWRITEBYTECODE from the parent process;
            # pair it with ``-B`` so an install-parity test never dirties the
            # committed SkillHub artifact before its byte-for-byte check.
            command.extend(("-I", "-B"))
        command.extend((str(path), "-"))
        result = subprocess.run(
            command,
            cwd=path.parents[3] if isolated else ROOT,
            input=text,
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        self.assertNotEqual(
            result.returncode,
            2,
            msg=f"{path} 环境错误：{result.stderr}\n{result.stdout}",
        )
        return result.returncode

    def test_source_lints_do_not_kill_normal_ordinals_or_negations(self) -> None:
        safe_cases = (
            "第一步，先说明真实优惠规则。",
            "第一周只做小范围验证。",
            "这不是最优方案，也不要诱导分享。",
        )
        for slug in SLUGS:
            path = (
                ROOT
                / "plugins/siyu-execution/skills"
                / slug
                / "scripts"
                / SCRIPT_NAMES[slug]
            )
            for text in safe_cases:
                with self.subTest(slug=slug, text=text):
                    self.assertEqual(self._run(path, text), 0)

    def test_source_lints_block_clear_claims_and_induced_share(self) -> None:
        risky = "本品牌全国销量第一，转发3个群领券。"
        for slug in SLUGS:
            path = (
                ROOT
                / "plugins/siyu-execution/skills"
                / slug
                / "scripts"
                / SCRIPT_NAMES[slug]
            )
            with self.subTest(slug=slug):
                self.assertEqual(self._run(path, risky), 1)

    def test_skillhub_lints_use_bundled_shared_scanner(self) -> None:
        bundle = ROOT / "skillhub/majia-siyu"
        for slug in SLUGS:
            path = bundle / "modules" / slug / "scripts" / SCRIPT_NAMES[slug]
            skill = (bundle / "modules" / slug / "SKILL.md").read_text(
                encoding="utf-8"
            )
            with self.subTest(slug=slug, case="path"):
                self.assertIn(
                    f"python3 modules/{slug}/scripts/{SCRIPT_NAMES[slug]}",
                    skill,
                )
            with self.subTest(slug=slug, case="safe"):
                self.assertEqual(
                    self._run(path, "第一步，先做小范围验证。", isolated=True),
                    0,
                )
            with self.subTest(slug=slug, case="risky"):
                self.assertEqual(
                    self._run(path, "本品牌全国销量第一。", isolated=True),
                    1,
                )


if __name__ == "__main__":
    unittest.main()
