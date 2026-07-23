from __future__ import annotations

import unittest

from siyu_team.eval.engine import composite
from siyu_team.eval.judge import build_judge_batch, parse_judge_scores
from siyu_team.eval.monte_carlo import reliability, wilson_interval
from siyu_team.eval.rubrics import ANCHORS, DIMENSION_WEIGHTS


class JudgeLayerTests(unittest.TestCase):
    """B 路径判官层：脚本构造 prompt / 解析宿主评分 / 加权合成。"""

    def test_all_dimensions_have_anchors(self) -> None:
        # 每个维度都要有锚点，否则 judge prompt 会 fallback 到「待补」。
        for dim in DIMENSION_WEIGHTS:
            self.assertIn(dim, ANCHORS, dim)

    def test_batch_covers_all_dimensions(self) -> None:
        batch = build_judge_batch("测试方案：会员日到店 8 折")
        self.assertEqual(set(batch), set(DIMENSION_WEIGHTS))
        for prompt in batch.values():
            self.assertIn("待评方案", prompt)

    def test_parse_accepts_number_and_object_forms(self) -> None:
        raw = {dim: 0.7 for dim in DIMENSION_WEIGHTS}
        raw["合规安全"] = {"score": 0.9, "why": "合规闭环"}
        scores = parse_judge_scores(raw)
        self.assertEqual(scores["合规安全"], 0.9)
        self.assertEqual(len(scores), len(DIMENSION_WEIGHTS))

    def test_parse_rejects_unknown_dim_and_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            parse_judge_scores({"不存在的维度": 0.5})
        with self.assertRaises(ValueError):
            parse_judge_scores({"合规安全": 1.5})
        with self.assertRaises(ValueError):
            parse_judge_scores({"合规安全": "高"})

    def test_composite_is_weighted_and_penalized(self) -> None:
        scores = {dim: 1.0 for dim in DIMENSION_WEIGHTS}
        self.assertEqual(composite(scores, static_penalty=1.0)["score"], 100.0)
        self.assertEqual(composite(scores, static_penalty=0.9)["score"], 90.0)


class MonteCarloTests(unittest.TestCase):
    """B 路径蒙卡层：宿主生成 N 份，脚本统计一致性。"""

    def test_reliability_rewards_stable_hits(self) -> None:
        samples = [{"score": 0.9, "hit": True, "length": 500}] * 5
        result = reliability(samples)
        self.assertEqual(result["hit_rate"], 1.0)
        self.assertEqual(result["crash_rate"], 0.0)
        self.assertGreaterEqual(result["reliability"], 0.9)

    def test_reliability_flags_instability(self) -> None:
        samples = [
            {"score": 0.9, "hit": True, "length": 500},
            {"score": 0.1, "hit": False, "crashed": True, "length": 100},
        ]
        result = reliability(samples)
        self.assertEqual(result["hit_rate"], 0.5)
        self.assertEqual(result["crash_rate"], 0.5)
        self.assertLess(result["reliability"], 0.6)

    def test_reliability_empty_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            reliability([])

    def test_wilson_interval_stays_in_unit_range(self) -> None:
        low, high = wilson_interval(5, 10)
        self.assertTrue(0.0 <= low <= high <= 1.0)
        self.assertEqual(wilson_interval(0, 0), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
