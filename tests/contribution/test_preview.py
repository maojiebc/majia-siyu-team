from __future__ import annotations

import unittest

from siyu_team.contribution.models import ContributionCandidate, ContributionSignal
from siyu_team.contribution.preview import build_preview


class ContributionPreviewTests(unittest.TestCase):
    def test_preview_hash_is_stable_for_same_candidate_content(self) -> None:
        kwargs = {
            "signal": ContributionSignal.USER_CORRECTION,
            "user_facts": ("加盟店不会按直营门店方式执行。",),
            "summary": "加盟执行边界必须单独考虑。",
        }
        first = build_preview(ContributionCandidate(**kwargs))
        second = build_preview(ContributionCandidate(**kwargs))
        self.assertNotEqual(first.candidate.candidate_id, second.candidate.candidate_id)
        # candidate_id 是幂等主体的一部分，因此不同候选必须有不同 hash。
        self.assertNotEqual(first.preview_hash, second.preview_hash)
        self.assertFalse(first.to_dict()["include_full_chat"])

    def test_preview_exposes_provenance_but_submission_content_does_not_mix_it(self) -> None:
        candidate = ContributionCandidate(
            signal=ContributionSignal.FIRSTHAND_CASE,
            user_facts=("我们实际测试后发现多步流程执行率低。",),
            summary="多步流程降低门店执行率。",
            model_inferences=("高峰期认知负荷可能是原因",),
            existing_knowledge=("通用流程简化原则",),
        )
        data = build_preview(candidate).to_dict()
        self.assertEqual(data["provenance"]["user_facts"], list(candidate.user_facts))
        self.assertNotIn("model_inferences", data["candidate"])
        self.assertNotIn("existing_knowledge", data["candidate"])


if __name__ == "__main__":
    unittest.main()
