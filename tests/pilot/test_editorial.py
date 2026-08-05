from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from siyu_team.pilot.editorial import render_editorial_report, summarize_editorial


FIELDS = [
    "submission_id",
    "status",
    "first_read_minutes",
    "followup_minutes",
    "atom_drafting_minutes",
    "privacy_minutes",
    "confirmation_minutes",
    "finalization_minutes",
    "followup_count",
    "draft_atom_count",
    "confirmed_atom_count",
    "case_card_delivered",
    "would_contribute_again",
    "value_exchange_score",
    "case_card_within_5_workdays",
    "pilot_invited_total",
    "complaint_count",
    "weekly_capacity_stable",
    "rework_count",
    "contributor_name",
    "contact",
]


class EditorialReportTest(unittest.TestCase):
    def _write(self, path: Path, rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_missing_time_is_not_zero_and_identifiers_do_not_leak(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "editorial.csv"
            self._write(
                path,
                [
                    {
                        "submission_id": "sub-001",
                        "status": "qualified",
                        "first_read_minutes": 3,
                        "followup_minutes": 2,
                        "atom_drafting_minutes": 6,
                        "privacy_minutes": 2,
                        "confirmation_minutes": 2,
                        "finalization_minutes": 2,
                        "followup_count": 1,
                        "draft_atom_count": 2,
                        "confirmed_atom_count": 2,
                        "case_card_delivered": "true",
                        "would_contribute_again": "true",
                        "value_exchange_score": 5,
                        "case_card_within_5_workdays": "true",
                        "pilot_invited_total": 10,
                        "complaint_count": 0,
                        "weekly_capacity_stable": "true",
                        "rework_count": 0,
                        "contributor_name": "不应输出的姓名",
                        "contact": "13800000000",
                    },
                    {
                        "submission_id": "sub-002",
                        "status": "qualified",
                        "first_read_minutes": 4,
                        "followup_minutes": "",
                        "atom_drafting_minutes": 5,
                        "privacy_minutes": 2,
                        "confirmation_minutes": 2,
                        "finalization_minutes": 1,
                        "followup_count": 0,
                        "draft_atom_count": 1,
                        "confirmed_atom_count": 1,
                    },
                    {
                        "submission_id": "sub-003",
                        "status": "rejected",
                        "first_read_minutes": 3,
                        "followup_minutes": 0,
                        "atom_drafting_minutes": 0,
                        "privacy_minutes": 0,
                        "confirmation_minutes": 0,
                        "finalization_minutes": 0,
                    },
                ],
            )
            result = summarize_editorial(path)
            qualified = result["human_cost"]["qualified"]
            self.assertEqual(qualified["complete_time_count"], 1)
            self.assertEqual(qualified["missing_time_count"], 1)
            self.assertIsNone(qualified["p75_minutes_nearest_rank"])
            self.assertEqual(result["human_cost"]["rejected"]["median_minutes"], 3)
            report = render_editorial_report(result)
            self.assertNotIn("不应输出的姓名", report)
            self.assertNotIn("13800000000", report)
            self.assertEqual(result["h2"]["status"], "not_evaluated")
            self.assertEqual(result["h3"]["status"], "not_evaluated")

    def test_p75_uses_nearest_rank_at_four_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "editorial.csv"
            rows: list[dict[str, object]] = []
            for index, total in enumerate((10, 20, 30, 40), 1):
                rows.append(
                    {
                        "submission_id": f"sub-{index:03d}",
                        "status": "qualified",
                        "first_read_minutes": total,
                        "followup_minutes": 0,
                        "atom_drafting_minutes": 0,
                        "privacy_minutes": 0,
                        "confirmation_minutes": 0,
                        "finalization_minutes": 0,
                    }
                )
            self._write(path, rows)
            result = summarize_editorial(path)
            self.assertEqual(
                result["human_cost"]["qualified"]["p75_minutes_nearest_rank"], 30
            )


if __name__ == "__main__":
    unittest.main()
