import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models.entities import CheckStatus
from app.services.verification.biometric_review_service import (
    BiometricReviewConflictError,
    BiometricReviewValidationError,
    record_biometric_review_decision,
)


def test_biometric_decision_rejects_short_reason():
    db = MagicMock()

    with pytest.raises(BiometricReviewValidationError):
        record_biometric_review_decision(
            db=db,
            check_id=uuid.uuid4(),
            reviewer_user_id=uuid.uuid4(),
            action="confirm_match",
            reason="short",
        )

    db.commit.assert_not_called()


def test_biometric_decision_does_not_change_agent_status():
    db = MagicMock()
    reviewer_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    original_agent_status = "under_review"
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=agent_id,
        status=CheckStatus.NEEDS_REVIEW,
        result_data={"selfie_document_id": str(uuid.uuid4())},
    )
    agent = SimpleNamespace(
        id=agent_id,
        user_id=uuid.uuid4(),
        status=original_agent_status,
    )
    db.execute.return_value.scalar_one_or_none.side_effect = [check, agent]

    result = record_biometric_review_decision(
        db=db,
        check_id=check.id,
        reviewer_user_id=reviewer_id,
        action="confirm_match",
        reason="Selfie visibly matches the available identity document.",
    )

    assert result.new_status == "passed"
    assert check.status == CheckStatus.PASSED
    assert check.result_data["manual_review_status"] == "confirm_match"
    assert agent.status == original_agent_status
    db.commit.assert_called_once()


def test_biometric_decision_conflicts_after_review():
    db = MagicMock()
    check = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        status=CheckStatus.PASSED,
    )
    db.execute.return_value.scalar_one_or_none.return_value = check

    with pytest.raises(BiometricReviewConflictError):
        record_biometric_review_decision(
            db=db,
            check_id=check.id,
            reviewer_user_id=uuid.uuid4(),
            action="confirm_match",
            reason="This decision should not be recorded twice.",
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
