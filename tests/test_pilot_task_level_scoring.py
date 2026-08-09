from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from siyu_team.pilot.blind import _rating_sheet, create_blind_pairs
from siyu_team.pilot.models import (
    RATING_AUDIT_FIELDS,
    GenerationManifest,
    PilotTask,
    PilotValidationError,
    SCORE_DIMENSIONS,
)
from siyu_team.pilot.packets import (
    load_atoms,
    load_mapping,
    load_tasks,
    prepare_run,
)
from siyu_team.pilot.scoring import render_score_report, score_run


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "pilot"


class PilotTaskLevelScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tasks = load_tasks(FIXTURES / "golden-tasks.jsonl")
        cls.atoms = load_atoms(FIXTURES / "synthetic-approved-atoms.jsonl")
        cls.mapping = load_mapping(FIXTURES / "task-atom-map.json")

    def _make_run(
        self,
        root: Path,
        *,
        task_count: int,
        complete_config: bool = True,
    ) -> tuple[Path, tuple[PilotTask, ...]]:
        run = root / f"run-{task_count:03d}"
        selected = self.tasks[:task_count]
        task_payload = [task.to_dict() for task in selected]
        manifest = GenerationManifest(
            run_id=run.name,
            model_name="fixture-model" if complete_config else "",
            host="unittest" if complete_config else "",
            generated_at="2026-08-09T12:00:00+08:00",
            task_hash="a" * 64,
            atom_corpus_hash="b" * 64,
            prompt_template_hash="c" * 64,
            temperature="0" if complete_config else "",
            max_output=800 if complete_config else 0,
            commit_sha="d" * 40 if complete_config else "",
            model_config={"top_p": 1},
        )
        run.mkdir(parents=True)
        (run / "manifest.json").write_text(
            json.dumps(
                {
                    "manifest": manifest.to_dict(),
                    "seed": 20260809,
                    "run_mode": (
                        "formal_evaluation"
                        if task_count == 30
                        else "tooling_dry_run"
                    ),
                    "tasks": task_payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        for task in selected:
            for version in ("baseline", "knowledge"):
                answer = run / "generation" / version / f"{task.id}.md"
                answer.parent.mkdir(parents=True, exist_ok=True)
                answer.write_text(
                    f"{version} answer for {task.id}\n", encoding="utf-8"
                )
        create_blind_pairs(run)
        return run, tuple(selected)

    def _write_ratings(
        self,
        root: Path,
        run: Path,
        tasks: tuple[PilotTask, ...],
        *,
        reviewer_count: int,
        overrides: dict[tuple[int, str], str] | None = None,
        include_audit: bool = True,
        baseline_claims: int = 1,
        knowledge_claims: int = 0,
        claim_overrides: dict[tuple[int, str, str], int] | None = None,
        generic_reason_rows: set[tuple[int, str]] | None = None,
    ) -> list[Path]:
        blind_map = json.loads(
            (run / "blind" / "blind-map.json").read_text(encoding="utf-8")
        )["pairs"]
        fields = ["reviewer_id", "task_id"]
        fields.extend(f"left_{dimension}" for dimension in SCORE_DIMENSIONS)
        fields.extend(f"right_{dimension}" for dimension in SCORE_DIMENSIONS)
        if include_audit:
            fields.extend(RATING_AUDIT_FIELDS)
        fields.extend(("preference", "reason"))
        paths: list[Path] = []
        for reviewer_index in range(reviewer_count):
            path = root / f"reviewer-{reviewer_index}.csv"
            paths.append(path)
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for raw_task in tasks:
                    task_id = raw_task.id
                    pair = blind_map[task_id]
                    knowledge_side = (
                        "left" if pair["left"] == "knowledge" else "right"
                    )
                    baseline_side = "right" if knowledge_side == "left" else "left"
                    outcome = (overrides or {}).get(
                        (reviewer_index, task_id), "win"
                    )
                    preference = {
                        "win": knowledge_side,
                        "loss": baseline_side,
                        "tie": "tie",
                    }[outcome]
                    row: dict[str, object] = {
                        "reviewer_id": f"reviewer-{reviewer_index}",
                        "task_id": task_id,
                        "preference": preference,
                        "reason": (
                            "更好"
                            if (reviewer_index, task_id)
                            in (generic_reason_rows or set())
                            else "该侧明确了第一断点、组织责任、验证指标和失效边界"
                        ),
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
                    if include_audit:
                        row[
                            f"{knowledge_side}_unsupported_precise_claims"
                        ] = (claim_overrides or {}).get(
                            (reviewer_index, task_id, "knowledge"),
                            knowledge_claims,
                        )
                        row[
                            f"{baseline_side}_unsupported_precise_claims"
                        ] = (claim_overrides or {}).get(
                            (reviewer_index, task_id, "baseline"),
                            baseline_claims,
                        )
                    writer.writerow(row)
        return paths

    def test_primary_sample_is_30_tasks_not_90_ratings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            ratings = self._write_ratings(
                root, run, tasks, reviewer_count=3
            )
            result = score_run(run, ratings)
            repeated = score_run(run, ratings)

        primary = result["primary_task_level"]
        secondary = result["secondary_rating_level"]
        self.assertEqual(primary["independent_sample_count"], 30)
        self.assertEqual(primary["knowledge_wins"], 30)
        self.assertEqual(secondary["rating_count"], 90)
        self.assertEqual(secondary["knowledge_wins"], 90)
        self.assertLess(
            primary["wilson_95"]["lower"],
            secondary["wilson_95_descriptive_only"]["lower"],
        )
        self.assertEqual(result["scope"]["evaluation_state"], "evaluated")
        self.assertEqual(result["h1"]["status"], "pass")
        self.assertEqual(primary["unsupported_precise_claim_baseline"], 1.0)
        self.assertEqual(primary["unsupported_precise_claim_knowledge"], 0.0)
        self.assertEqual(
            primary["task_cluster_bootstrap_95"],
            repeated["primary_task_level"]["task_cluster_bootstrap_95"],
        )
        self.assertEqual(
            len(result["run_configuration"]["answer_hashes"]["per_task"]), 30
        )

    def test_strict_task_majority_and_tie_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=5)
            first_id = tasks[0].id
            second_id = tasks[1].id
            overrides = {
                (1, first_id): "loss",
                (2, first_id): "tie",
                (2, second_id): "tie",
            }
            ratings = self._write_ratings(
                root,
                run,
                tasks,
                reviewer_count=3,
                overrides=overrides,
            )
            result = score_run(run, ratings)

        primary = result["primary_task_level"]
        self.assertEqual(primary["knowledge_wins"], 4)
        self.assertEqual(primary["baseline_wins"], 0)
        self.assertEqual(primary["ties"], 1)
        self.assertEqual(primary["tie_sensitivity"]["tie_as_half"], 0.9)
        self.assertEqual(result["scope"]["evaluation_state"], "tooling_validated")
        self.assertEqual(result["h1"]["status"], "not_evaluated")

    def test_source_answer_change_after_blinding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=5)
            ratings = self._write_ratings(root, run, tasks, reviewer_count=1)
            answer = run / "generation" / "knowledge" / f"{tasks[0].id}.md"
            answer.write_text("盲化后被替换的答案\n", encoding="utf-8")

            with self.assertRaisesRegex(PilotValidationError, "源答案被修改"):
                score_run(run, ratings)

    def test_blind_pair_change_after_blinding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=5)
            ratings = self._write_ratings(root, run, tasks, reviewer_count=1)
            pair = run / "blind" / "pairs" / f"{tasks[0].id}.md"
            pair.write_text(
                pair.read_text(encoding="utf-8") + "\n篡改内容\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PilotValidationError, "盲测对被修改"):
                score_run(run, ratings)

    def test_legacy_blind_map_without_hashes_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=5)
            ratings = self._write_ratings(root, run, tasks, reviewer_count=1)
            map_path = run / "blind" / "blind-map.json"
            payload = json.loads(map_path.read_text(encoding="utf-8"))
            for field in (
                "hash_algorithm",
                "generation_answer_hashes",
                "blind_pair_hashes",
            ):
                payload.pop(field)
            map_path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(PilotValidationError, "完整性记录"):
                score_run(run, ratings)

    def test_formal_run_missing_claim_audit_stays_not_evaluated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            ratings = self._write_ratings(
                root,
                run,
                tasks,
                reviewer_count=3,
                include_audit=False,
            )
            result = score_run(run, ratings)

        self.assertFalse(result["scope"]["eligible_for_h1"])
        self.assertEqual(result["scope"]["evaluation_state"], "not_evaluated")
        self.assertEqual(result["h1"]["status"], "not_evaluated")
        self.assertTrue(
            any(
                issue.startswith("missing_unsupported_precise_claim_counts")
                for issue in result["scope"]["evaluation_issues"]
            )
        )

    def test_precise_claim_regression_can_fail_an_otherwise_winning_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            ratings = self._write_ratings(
                root,
                run,
                tasks,
                reviewer_count=3,
                baseline_claims=0,
                knowledge_claims=1,
            )
            result = score_run(run, ratings)

        self.assertEqual(result["scope"]["evaluation_state"], "evaluated")
        self.assertFalse(
            result["h1"]["criteria"][
                "unsupported_precise_claims_not_higher"
            ]
        )
        self.assertEqual(result["h1"]["status"], "fail")

    def test_occurrence_rate_not_mean_count_controls_precise_claim_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            overrides: dict[tuple[int, str, str], int] = {}
            for reviewer in range(3):
                overrides[(reviewer, tasks[0].id, "baseline")] = 10
                overrides[(reviewer, tasks[1].id, "knowledge")] = 1
                overrides[(reviewer, tasks[2].id, "knowledge")] = 1
            ratings = self._write_ratings(
                root,
                run,
                tasks,
                reviewer_count=3,
                baseline_claims=0,
                knowledge_claims=0,
                claim_overrides=overrides,
            )
            result = score_run(run, ratings)

        claims = result["primary_task_level"]["unsupported_precise_claims"]
        self.assertLess(
            claims["knowledge_mean_count_per_task"],
            claims["baseline_mean_count_per_task"],
        )
        self.assertGreater(
            claims["knowledge_task_occurrence_rate"],
            claims["baseline_task_occurrence_rate"],
        )
        self.assertFalse(
            result["h1"]["criteria"][
                "unsupported_precise_claims_not_higher"
            ]
        )

    def test_specific_reason_gate_uses_winning_ratings_not_task_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            generic: set[tuple[int, str]] = set()
            for task in tasks[:21]:
                generic.add((2, task.id))
            for task in tasks[21:]:
                for reviewer in range(3):
                    generic.add((reviewer, task.id))
            ratings = self._write_ratings(
                root,
                run,
                tasks,
                reviewer_count=3,
                generic_reason_rows=generic,
            )
            result = score_run(run, ratings)

        primary_rate = result["primary_task_level"][
            "specific_reason_rate_for_knowledge_winning_tasks"
        ]
        rating_rate = result["secondary_rating_level"][
            "specific_reason_rate_for_knowledge_wins"
        ]
        self.assertGreaterEqual(primary_rate, 0.70)
        self.assertLess(rating_rate, 0.70)
        self.assertFalse(
            result["h1"]["criteria"][
                "specific_knowledge_win_rating_reason_rate_gte_0_70"
            ]
        )

    def test_legacy_or_blank_run_mode_cannot_be_evaluated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            payload = json.loads(
                (run / "manifest.json").read_text(encoding="utf-8")
            )
            payload["run_mode"] = ""
            (run / "manifest.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
            ratings = self._write_ratings(
                root, run, tasks, reviewer_count=3
            )
            result = score_run(run, ratings)
        self.assertIn(
            "run_not_marked_formal_evaluation",
            result["scope"]["evaluation_issues"],
        )
        self.assertEqual(result["h1"]["status"], "not_evaluated")

    def test_two_reviewers_cannot_mark_full_run_evaluated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=30)
            ratings = self._write_ratings(
                root, run, tasks, reviewer_count=2
            )
            result = score_run(run, ratings)
        self.assertEqual(result["scope"]["evaluation_state"], "not_evaluated")
        self.assertEqual(result["h1"]["status"], "not_evaluated")

    def test_prepare_rejects_incomplete_formal_configuration_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "formal-run"
            with self.assertRaisesRegex(PilotValidationError, "完整记录配置"):
                prepare_run(
                    tasks=self.tasks,
                    atoms=self.atoms,
                    mapping=self.mapping,
                    output=output,
                    seed=7,
                )
            self.assertFalse(output.exists())

    def test_generated_rating_sheet_has_independent_claim_fields(self) -> None:
        header = next(csv.reader(_rating_sheet([self.tasks[0].id]).splitlines()))
        for field in RATING_AUDIT_FIELDS:
            self.assertIn(field, header)
        self.assertIn("left_unsupported_claim_control", header)
        self.assertIn("left_unsupported_precise_claims", header)

    def test_report_labels_primary_and_secondary_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, tasks = self._make_run(root, task_count=5)
            ratings = self._write_ratings(
                root, run, tasks, reviewer_count=1, include_audit=False
            )
            report = render_score_report(score_run(run, ratings))
        self.assertIn("主分析：任务级", report)
        self.assertIn("次要分析：评分级", report)
        self.assertIn("tooling_validated", report)
        self.assertIn("not_evaluated", report)

    def test_protocol_and_result_templates_keep_method_and_status_honest(self) -> None:
        protocol = (ROOT / "docs" / "pilot" / "protocol.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("主分析：任务级", protocol)
        self.assertIn("确定性 percentile bootstrap", protocol)
        self.assertIn("任务级出现率", protocol)
        self.assertIn("knowledge-win 评分", protocol)
        self.assertIn("unsupported_claim_control", protocol)
        self.assertIn("不得替代", protocol)
        for name in (
            "h1-knowledge-value.md",
            "h2-contribution-demand.md",
            "h3-editorial-throughput.md",
        ):
            text = (ROOT / "docs" / "pilot" / "results" / name).read_text(
                encoding="utf-8"
            )
            self.assertIn("状态：Not Evaluated", text)

if __name__ == "__main__":
    unittest.main()
