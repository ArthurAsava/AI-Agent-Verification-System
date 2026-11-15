
from app.services.verification.decision_contracts import (
    CaseStatus,
)


ALLOWED_TRANSITIONS = {
    CaseStatus.PENDING: {
        CaseStatus.ANALYZING,
    },
    CaseStatus.ANALYZING: {
        CaseStatus.AWAITING_REVIEW,
        CaseStatus.ANALYSIS_FAILED,
    },
    CaseStatus.ANALYSIS_FAILED: {
        CaseStatus.ANALYZING,
    },
    CaseStatus.AWAITING_REVIEW: {
        CaseStatus.APPROVED,
        CaseStatus.REJECTED,
        CaseStatus.RESUBMISSION_REQUIRED,
    },
    CaseStatus.APPROVED: set(),
    CaseStatus.REJECTED: set(),
    CaseStatus.RESUBMISSION_REQUIRED: set(),
}


class InvalidVerificationTransition(ValueError):
    pass


def validate_transition(
    current: CaseStatus,
    target: CaseStatus,
) -> None:
    if (
        not isinstance(current, CaseStatus)
        or not isinstance(target, CaseStatus)
    ):
        raise InvalidVerificationTransition(
            "Invalid verification status."
        )

    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidVerificationTransition(
            f"Transition {current.value} "
            f"to {target.value} is not allowed."
        )
