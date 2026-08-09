from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from siyu_team.knowledge.growth_layers import L0_DOC, L1_CATERING_DOC
from siyu_team.routing import route, route_task
from siyu_team.task import Task, TaskKind


ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class RepositoryContractTests(unittest.TestCase):
    def test_repository_markdown_links_exist(self) -> None:
        result = _run("tools/check_links.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_route_targets_and_knowledge_refs_exist(self) -> None:
        result = _run("tools/check_route_contracts.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generic_only_industries_never_emit_dead_pack_paths(self) -> None:
        for industry in ("retail", "edu"):
            legacy = route(industry, "cold")
            self.assertEqual(legacy["capability_status"], "generic_only")
            self.assertIsNone(legacy["industry_book"])
            decision = route_task(
                Task(
                    kind=TaskKind.STRATEGY_REVIEW,
                    source_text="整盘私域",
                    industry=industry,
                    stage="cold",
                )
            )
            self.assertIsNone(decision.industry_book)
            self.assertIn(L0_DOC, decision.knowledge_refs)
            if industry == "retail":
                self.assertIn(L1_CATERING_DOC, decision.knowledge_refs)
            else:
                self.assertNotIn(L1_CATERING_DOC, decision.knowledge_refs)

    def test_clean_skillhub_build_has_valid_links_and_routes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "majia-siyu"
            built = _run("tools/build_skillhub_bundle.py", "--output", str(bundle))
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            metadata = json.loads(built.stdout)
            self.assertEqual(
                Path(metadata["output"]).resolve(strict=False),
                bundle.resolve(strict=False),
            )
            links = _run("tools/check_links.py", "--root", str(bundle))
            self.assertEqual(links.returncode, 0, links.stdout + links.stderr)
            routes = _run(
                "tools/check_route_contracts.py",
                "--bundle",
                str(bundle),
            )
            self.assertEqual(routes.returncode, 0, routes.stdout + routes.stderr)


if __name__ == "__main__":
    unittest.main()
