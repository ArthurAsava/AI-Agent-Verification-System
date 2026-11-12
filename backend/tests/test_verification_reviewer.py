
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.verification.reviewer_service import (
    record_verification_decision,
    ReviewerAuthorizationError,
    VerificationDecisionConflictError,
    VerificationDecisionValidationError,
)


def test_unauthorized_reviewer():
    db = MagicMock()

    with pytest.raises(ReviewerAuthorizationError):
        record_verification_decision(
            db=db,
            case_id=uuid.uuid4(),
            reviewer_user_id=uuid.uuid4(),
            action="approve",
            reason="Identity document has been reviewed.",
            expected_version=0,
        )

    db.commit.assert_not_called()


def test_invalid_reason():
    db = MagicMock()

    with pytest.raises(VerificationDecisionValidationError):
        record_verification_decision(
            db=db,
            case_id=uuid.uuid4(),
            reviewer_user_id=uuid.uuid4(),
            action="approve",
            reason="short",
            expected_version=0,
            reviewer_authorized=True,
        )

    db.commit.assert_not_called()


def test_stale_version():
    db = MagicMock()

    case = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        status="awaiting_review",
        version=3,
    )

    db.execute.return_value.scalar_one_or_none.return_value = case

    with pytest.raises(VerificationDecisionConflictError):
        record_verification_decision(
            db=db,
            case_id=case.id,
            reviewer_user_id=uuid.uuid4(),
            action="approve",
            reason="Identity document has been reviewed.",
            expected_version=2,
            reviewer_authorized=True,
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "action",
    ["approve", "reject", "request_resubmission"],
)
def test_valid_decision(action):
    db = MagicMock()

    reviewer_id = uuid.uuid4()
    agent_id = uuid.uuid4()

    case = SimpleNamespace(
        id=uuid.uuid4(),
        agent_id=agent_id,
        status="awaiting_review",
        version=0,
        reviewer_user_id=None,
        decision_reason=None,
        reviewed_at=None,
        updated_at=None,
    )

    agent = SimpleNamespace(
        id=agent_id,
        user_id=uuid.uuid4(),
    )

    db.execute.return_value.scalar_one_or_none.side_effect = [
        case,
        agent,
    ]

    result = record_verification_decision(
        db=db,
        case_id=case.id,
        reviewer_user_id=reviewer_id,
        action=action,
        reason="Verification evidence was reviewed.",
        expected_version=0,
        reviewer_authorized=True,
    )

    assert result.case_id == case.id
    assert result.version == 1
    assert result.new_status in {
        "approved",
        "rejected",
        "resubmission_required",
    }

    db.commit.assert_called_once()
