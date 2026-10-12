"""Seasonal content must be available from the actual shipped skill links."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOC = "节点经营日历-2026Q4至2027春节.md"


class SeasonalKnowledgeTests(unittest.TestCase):
    def test_shipped_execution_skills_resolve_same_seasonal_document(self):
        source = ROOT / "knowledge/02-industry/catering" / DOC
        expected = source.read_bytes()
        for copy in (ROOT / "src/siyu_team/knowledge/data/02-industry/catering" / DOC,
                     ROOT / "skillhub/majia-siyu/modules/_knowledge/02-industry/catering" / DOC):
            self.assertEqual(copy.read_bytes(), expected)
        for skill in ("siyu-pyq", "siyu-qunfa", "siyu-huashu"):
            for path in (ROOT / "plugins/siyu-execution/skills" / skill / "SKILL.md",
                         ROOT / "skillhub/majia-siyu/modules" / skill / "SKILL.md"):
                targets = re.findall(r"\]\(([^)]+" + re.escape(DOC) + r")\)", path.read_text())
                self.assertEqual(len(targets), 1, path)
                self.assertEqual((path.parent / targets[0]).resolve().read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
