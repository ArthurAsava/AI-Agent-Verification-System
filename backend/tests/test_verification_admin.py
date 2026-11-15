from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.services.verification import admin_service as module


def scalar_result(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def test_dashboard_summary_contains_only_aggregate_counts():
    db = MagicMock()
    db.execute.side_effect = [
        scalar_result(3),
        scalar_result(2),
        scalar_result(4),
        scalar_result(5),
        scalar_result(6),
    ]

    summary = module.get_admin_dashboard_summary(db)

    assert summary.awaiting_review_cases == 3
    assert summary.elevated_risk_cases == 2
    assert summary.new_cases_last_24_hours == 4
    assert summary.agents_under_review == 5
    assert summary.active_reviewers == 6


def test_administrator_cannot_remove_own_access():
    user_id = uuid4()

    with pytest.raises(module.ReviewerAccessValidationError):
        module.update_reviewer_access(
            db=MagicMock(),
            administrator_user_id=user_id,
            target_user_id=user_id,
            is_active=True,
            is_admin=False,
        )


def test_last_active_administrator_cannot_be_removed():
    administrator_id = uuid4()
    agent = SimpleNamespace(id=uuid4(), user_id=administrator_id)
    reviewer = SimpleNamespace(
        user_id=administrator_id,
        is_active=True,
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )
    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = agent
    reviewer_result = MagicMock()
    reviewer_result.scalar_one_or_none.return_value = reviewer
    administrator_result = MagicMock()
    administrator_result.scalars.return_value.all.return_value = [reviewer]
    db = MagicMock()
    db.execute.side_effect = [
        agent_result,
        reviewer_result,
        administrator_result,
    ]

    with pytest.raises(module.ReviewerAccessValidationError):
        module.update_reviewer_access(
            db=db,
            administrator_user_id=uuid4(),
            target_user_id=administrator_id,
            is_active=False,
            is_admin=True,
        )

    db.rollback.assert_called_once()
    db.add.assert_not_called()


def test_admin_can_create_reviewer_for_registered_agent():
    administrator_id = uuid4()
    target_user_id = uuid4()
    target_agent = SimpleNamespace(id=uuid4(), user_id=target_user_id)
    agent_result = MagicMock()
    agent_result.scalar_one_or_none.return_value = target_agent
    reviewer_result = MagicMock()
    reviewer_result.scalar_one_or_none.return_value = None
    db = MagicMock()
    db.execute.side_effect = [agent_result, reviewer_result]

    result = module.update_reviewer_access(
        db=db,
        administrator_user_id=administrator_id,
        target_user_id=target_user_id,
        is_active=True,
        is_admin=False,
    )

    assert result.user_id == target_user_id
    assert result.is_active is True
    assert result.is_admin is False
    assert db.add.call_count == 2
    db.flush.assert_called_once()
    db.commit.assert_called_once()
