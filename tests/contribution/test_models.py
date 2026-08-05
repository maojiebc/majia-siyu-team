from __future__ import annotations

import json
import unittest

from siyu_team.contribution.models import (
    AuthorizationScope,
    ContributionAuthorization,
    ContributionCandidate,
    ContributionPromptState,
    ContributionSignal,
    ContributionSubmission,
    ContributionValidationError,
)
from siyu_team.contribution.preview import build_preview


def candidate(**overrides: object) -> ContributionCandidate:
    values: dict[str, object] = {
        "signal": ContributionSignal.FIRSTHAND_CASE,
        "user_facts": ("我们在高峰期试过四步加微流程，执行率很快回落。",),
        "summary": "高峰期多步加微流程难以持续执行。",
        "scene": "加盟餐饮门店高峰期",
        "actions": ("把店员额外动作压缩为一步",),
        "result": "执行门店覆盖率提高",
        "boundaries": ("低客流门店可能允许更多人工讲解",),
        "model_inferences": ("流程复杂度可能是主要原因",),
        "existing_knowledge": ("已有门店执行原则 ka_example",),
    }
    values.update(overrides)
    return ContributionCandidate(**values)  # type: ignore[arg-type]


class ContributionModelTests(unittest.TestCase):
    def test_prompt_state_allows_at_most_once_after_primary_answer(self) -> None:
        state = ContributionPromptState(primary_answer_delivered=True)
        self.assertTrue(state.can_prompt)
        prompted = state.mark_prompted()
        self.assertFalse(prompted.can_prompt)
        with self.assertRaises(ContributionValidationError):
            prompted.mark_prompted()
        self.assertFalse(state.decline().can_prompt)

    def test_candidate_requires_user_fact_and_rejects_full_chat(self) -> None:
        with self.assertRaises(ContributionValidationError):
            candidate(user_facts=())
        with self.assertRaises(ContributionValidationError):
            candidate(include_full_chat=True)

    def test_submission_payload_excludes_inference_and_existing_knowledge(self) -> None:
        preview = build_preview(candidate())
        authorization = ContributionAuthorization(
            AuthorizationScope.ANONYMOUS_PUBLIC,
            confirmed=True,
            confirmed_at="2026-08-05T16:00:00+08:00",
        )
        submission = ContributionSubmission(preview, authorization, "idem-001")
        payload = json.loads(submission.to_json())
        serialized = submission.to_json()
        self.assertFalse(payload["include_full_chat"])
        self.assertNotIn("model_inferences", serialized)
        self.assertNotIn("existing_knowledge", serialized)
        self.assertEqual(payload["preview_hash"], preview.preview_hash)

    def test_unconfirmed_or_unsafe_preview_cannot_be_submitted(self) -> None:
        safe_preview = build_preview(candidate())
        with self.assertRaises(ContributionValidationError):
            ContributionSubmission(
                safe_preview,
                ContributionAuthorization(AuthorizationScope.INTERNAL_ONLY),
                "idem-002",
            )
        unsafe_preview = build_preview(
            candidate(user_facts=("联系人手机号是 13800138000。",))
        )
        confirmed = ContributionAuthorization(
            AuthorizationScope.INTERNAL_ONLY,
            confirmed=True,
            confirmed_at="2026-08-05T16:00:00+08:00",
        )
        with self.assertRaises(ContributionValidationError):
            ContributionSubmission(unsafe_preview, confirmed, "idem-003")

    def test_named_and_contact_authorizations_require_identity_fields(self) -> None:
        with self.assertRaises(ContributionValidationError):
            ContributionAuthorization(AuthorizationScope.NAMED_PUBLIC)
        with self.assertRaises(ContributionValidationError):
            ContributionAuthorization(AuthorizationScope.CONTACT_BEFORE_USE)


if __name__ == "__main__":
    unittest.main()
