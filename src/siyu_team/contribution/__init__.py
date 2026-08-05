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
    "detect_contribution_signal",
]
