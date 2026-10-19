"""A polished answer must not pass without a grounded, current review."""
from __future__ import annotations

import copy
import hashlib
import unittest

from siyu_team.eval.judge import build_judge_batch, build_judge_report
from siyu_team.eval.rubrics import DIMENSION_WEIGHTS


ANSWER = "甲方案有结算拖欠记录，未核实解决，暂停推荐。"
REQUEST = "10家直营火锅，只缺会员运营，优先考虑公私域衔接。"
EVIDENCE = "S1: 甲方案存在结算拖欠报道，无解决证据。未取得其他方案资料。"


def submission() -> dict:
    return {
        "model": "test-model",
        "config": {"temperature": 0},
        "reviewed_at": "2026-10-19T12:00:00Z",
        "review_method": "independent_host_judge",
        "scores": {dim: {"score": 1.0, "why": "仅评任务所需内容"}
                   for dim in DIMENSION_WEIGHTS},
    }


def grounded_submission() -> dict:
    result = submission()
    result["review_binding"] = {
        name: hashlib.sha256(text.encode()).hexdigest()
        for name, text in (("answer_sha256", ANSWER),
                           ("request_sha256", REQUEST),
                           ("evidence_sha256", EVIDENCE))
    }
    result["reliability_checks"] = {
        "factual_support": {"status": "pass", "reason": "仅引用S1，没有断言停服。"},
        "customer_fit": {"status": "pass", "reason": "仅初筛会员方案，没有扩张采购。"},
        "risk_screening": {"status": "pass", "reason": "S1未解决，明确暂停推荐。"},
        "option_coverage": {"status": "pass", "reason": "无完整候选覆盖，未声称最终比选。"},
    }
    return result


class GroundedReviewTests(unittest.TestCase):
    def review(self, raw: dict, **kwargs):
        return build_judge_report(raw, source="answer.md", plan=ANSWER,
                                  request=REQUEST, evidence=EVIDENCE, **kwargs)

    def test_high_scores_without_fact_review_cannot_pass(self):
        report = build_judge_report(submission(), source="answer.md")
        self.assertEqual(report.status, "not_evaluated")
        self.assertIsNone(report.score)
        self.assertIsNone(report.badge)

    def test_complete_grounded_review_can_pass(self):
        report = self.review(grounded_submission())
        self.assertEqual(report.status, "passed")
        self.assertEqual(report.score, 100.0)

    def test_critical_fail_is_not_averaged_away(self):
        raw = grounded_submission()
        raw["reliability_checks"]["risk_screening"] = {
            "status": "fail", "reason": "忽略S1的未解决结算风险。"}
        report = self.review(raw)
        self.assertEqual(report.status, "blocked")
        self.assertIsNone(report.score)
        self.assertIsNone(report.badge)

    def test_unknown_or_missing_gate_is_not_evaluated(self):
        for gate in ("factual_support", "customer_fit", "risk_screening", "option_coverage"):
            for missing in (False, True):
                raw = grounded_submission()
                if missing:
                    del raw["reliability_checks"][gate]
                else:
                    raw["reliability_checks"][gate]["status"] = "unknown"
                with self.subTest(gate=gate, missing=missing):
                    self.assertEqual(self.review(raw).status, "not_evaluated")

    def test_scores_cannot_be_reused_after_answer_or_context_changes(self):
        for name in ("answer_sha256", "request_sha256", "evidence_sha256"):
            raw = grounded_submission()
            raw["review_binding"][name] = "0" * 64
            with self.subTest(name=name):
                self.assertEqual(self.review(raw).status, "not_evaluated")

    def test_false_metadata_cannot_override_missing_binding(self):
        raw = grounded_submission()
        del raw["review_binding"]
        raw["config"]["metadata_complete"] = True
        self.assertEqual(self.review(raw).status, "not_evaluated")

    def test_malformed_gate_and_customer_fit_na_are_rejected(self):
        for value in (True, {"status": "pass", "reason": ""},
                      {"status": "not_applicable", "reason": "不想检查"},
                      {"status": "passed", "reason": "wrong status"}):
            raw = grounded_submission()
            raw["reliability_checks"]["customer_fit"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.review(raw)

    def test_non_vendor_answer_may_skip_risk_and_coverage_with_reason(self):
        raw = copy.deepcopy(grounded_submission())
        for gate in ("risk_screening", "option_coverage"):
            raw["reliability_checks"][gate] = {
                "status": "not_applicable", "reason": "仅为活动通知，不涉及选型。"}
        self.assertEqual(self.review(raw).status, "passed")

    def test_judge_receives_request_evidence_and_binding(self):
        prompts = build_judge_batch(ANSWER, request=REQUEST, evidence=EVIDENCE)
        self.assertIn("reliability_checks", prompts)
        for prompt in prompts.values():
            self.assertIn(REQUEST, prompt)
            self.assertIn(EVIDENCE, prompt)
        self.assertIn(hashlib.sha256(ANSWER.encode()).hexdigest(),
                      prompts["reliability_checks"])


if __name__ == "__main__":
    unittest.main()
