from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
import unittest

from siyu_team.pilot.blind import create_blind_pairs
from siyu_team.pilot.models import PilotValidationError, SCORE_DIMENSIONS
from siyu_team.pilot.packets import (
    load_atoms,
    load_mapping,
    load_tasks,
    prepare_run,
    validate_atoms,
    validate_mapping,
    validate_tasks,
)
from siyu_team.pilot.scoring import score_run


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "pilot"


class PilotPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks = load_tasks(FIXTURES / "golden-tasks.jsonl")
        cls.atoms = load_atoms(FIXTURES / "synthetic-approved-atoms.jsonl")
        cls.mapping = load_mapping(FIXTURES / "task-atom-map.json")

    def test_fixture_contract(self) -> None:
        validate_tasks(self.tasks)
        validate_atoms(
            self.atoms,
            atoms_path=FIXTURES / "synthetic-approved-atoms.jsonl",
            fixture_mode=True,
        )
        validate_mapping(self.tasks, self.atoms, self.mapping)

    def test_private_atom_permissions_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            atom_path = Path(temporary) / "atoms.jsonl"
            atom_path.write_text(
                (FIXTURES / "synthetic-approved-atoms.jsonl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            atom_path.chmod(0o644)
            with self.assertRaisesRegex(PilotValidationError, "0600"):
                validate_atoms(self.atoms, atoms_path=atom_path)

    def test_five_task_one_reviewer_dry_run_is_tool_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run-005"
            prepare_run(
                tasks=self.tasks,
                atoms=self.atoms,
                mapping=self.mapping,
                output=run,
                seed=20260805,
                model_name="fixture-model",
                host="unittest",
                temperature="0",
                max_output=800,
                limit=5,
            )
            self.assertEqual(os.stat(run).st_mode & 0o777, 0o700)
            manifest = run / "manifest.json"
            self.assertEqual(os.stat(manifest).st_mode & 0o777, 0o600)

            for task in self.tasks[:5]:
                for version in ("baseline", "knowledge"):
                    answer = run / "generation" / version / f"{task.id}.md"
                    answer.write_text(
                        f"答案 {task.id}：先验证第一断点，再记录指标与边界。",
                        encoding="utf-8",
                    )
                    answer.chmod(0o600)
            blind_map = create_blind_pairs(run)
            self.assertEqual(os.stat(blind_map).st_mode & 0o777, 0o600)

            ratings = Path(temporary) / "reviewer-a.csv"
            fields = ["reviewer_id", "task_id"]
            fields.extend(f"left_{dimension}" for dimension in SCORE_DIMENSIONS)
            fields.extend(f"right_{dimension}" for dimension in SCORE_DIMENSIONS)
            fields.extend(("preference", "reason"))
            with ratings.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for task in self.tasks[:5]:
                    row = {
                        "reviewer_id": "reviewer-a",
                        "task_id": task.id,
                        "preference": "tie",
                        "reason": "两侧都给出了可验证的动作与适用边界",
                    }
                    row.update({f"left_{dimension}": 4 for dimension in SCORE_DIMENSIONS})
                    row.update({f"right_{dimension}": 4 for dimension in SCORE_DIMENSIONS})
                    writer.writerow(row)
            result = score_run(run, [ratings])
            self.assertEqual(result["scope"]["task_count"], 5)
            self.assertEqual(result["scope"]["reviewer_count"], 1)
            self.assertFalse(result["scope"]["eligible_for_h1"])
            self.assertEqual(result["h1"]["status"], "not_evaluated")
            self.assertIn("仅验证工具链", result["h1"]["note"])

    def test_blind_rejects_unreplaced_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run-placeholder"
            prepare_run(
                tasks=self.tasks,
                atoms=self.atoms,
                mapping=self.mapping,
                output=run,
                seed=7,
                limit=1,
            )
            with self.assertRaisesRegex(PilotValidationError, "尚未"):
                create_blind_pairs(run)

    def test_thirty_tasks_three_reviewers_can_reach_preregistered_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run-full"
            prepare_run(
                tasks=self.tasks,
                atoms=self.atoms,
                mapping=self.mapping,
                output=run,
                seed=20260805,
            )
            for task in self.tasks:
                for version in ("baseline", "knowledge"):
                    answer = run / "generation" / version / f"{task.id}.md"
                    answer.write_text("已生成的测试答案。", encoding="utf-8")
            map_path = create_blind_pairs(run)
            blind_map = json.loads(map_path.read_text(encoding="utf-8"))["pairs"]
            rating_paths: list[Path] = []
            fields = ["reviewer_id", "task_id"]
            fields.extend(f"left_{dimension}" for dimension in SCORE_DIMENSIONS)
            fields.extend(f"right_{dimension}" for dimension in SCORE_DIMENSIONS)
            fields.extend(("preference", "reason"))
            for reviewer_index in range(3):
                path = Path(temporary) / f"reviewer-{reviewer_index}.csv"
                rating_paths.append(path)
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    for task in self.tasks:
                        knowledge_side = (
                            "left"
                            if blind_map[task.id]["left"] == "knowledge"
                            else "right"
                        )
                        baseline_side = "right" if knowledge_side == "left" else "left"
                        row: dict[str, object] = {
                            "reviewer_id": f"reviewer-{reviewer_index}",
                            "task_id": task.id,
                            "preference": knowledge_side,
                            "reason": "该侧先拆分第一断点，并给出了组织责任、指标和失效边界",
                        }
                        row.update(
                            {
                                f"{knowledge_side}_{dimension}": 5
                                for dimension in SCORE_DIMENSIONS
                            }
                        )
                        row.update(
                            {
                                f"{baseline_side}_{dimension}": 3
                                for dimension in SCORE_DIMENSIONS
                            }
                        )
                        writer.writerow(row)
            result = score_run(run, rating_paths)
            self.assertTrue(result["scope"]["eligible_for_h1"])
            self.assertEqual(result["h1"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()
