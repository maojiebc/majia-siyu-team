"""同行知识共建的纯领域模型；不包含网络或飞书写入。"""

from .models import (
    AuthorizationScope,
    ContributionAuthorization,
    ContributionCandidate,
    ContributionPreview,
    ContributionPromptState,
    ContributionSignal,
    ContributionSubmission,
    ContributionValidationError,
)
from .preview import build_preview
from .signals import detect_contribution_signal
from .intake import (
    candidate_to_atom,
    dedupe,
    flag_conflicts,
    record_to_candidate,
    render_gift,
    run_intake,
)

__all__ = [
    "AuthorizationScope",
    "ContributionAuthorization",
    "ContributionCandidate",
    "ContributionPreview",
    "ContributionPromptState",
    "ContributionSignal",
    "ContributionSubmission",
    "ContributionValidationError",
    "build_preview",
    "candidate_to_atom",
    "dedupe",
    "detect_contribution_signal",
    "flag_conflicts",
    "record_to_candidate",
    "render_gift",
    "run_intake",
]
