"""Requested prompt contract: optional archives never become a write path."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ExecutionProfileReuseTests(unittest.TestCase):
    def test_three_execution_skills_offer_read_only_attributed_opt_out(self):
        for skill in ("siyu-pyq", "siyu-qunfa", "siyu-huashu"):
            for base in (ROOT / "plugins/siyu-execution/skills",
                         ROOT / "skillhub/majia-siyu/modules"):
                path = base / skill / "SKILL.md"
                text = path.read_text()
                with self.subTest(path=path):
                    self.assertIn("只读", text)
                    self.assertIn("哪天的哪份档案", text)
                    self.assertIn("用户说不用", text)
                    self.assertIn("路径越界", text)
                    self.assertLessEqual(path.stat().st_size, 8192)


if __name__ == "__main__":
    unittest.main()
