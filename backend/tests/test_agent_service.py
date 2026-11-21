
import uuid
from unittest.mock import MagicMock

from app.models.entities import Agent, AgentStatus
from app.schemas.agent import AgentCreate, AgentUpdate
from app.services.agent_service import (
    create_agent,
    get_agent_by_user_id,
    update_agent,
)


def test_agent_query_uses_authenticated_user_id():
    db = MagicMock()
    db.scalar.return_value = None

    user_id = uuid.uuid4()

    result = get_agent_by_user_id(db, user_id)

    assert result is None
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    assert statement.compile().params["user_id_1"] == user_id


def test_active_administrator_profile_is_auto_approved_on_creation():
    db = MagicMock()
    user_id = uuid.uuid4()
    payload = AgentCreate(
        first_name="Admin",
        last_name="User",
        date_of_birth="1990-01-01",
        primary_residence="Nairobi",
        nationality="Kenyan",
        avatar_variant="male",
    )

    create_agent(db, user_id, payload, auto_approve=True)

    agent = db.add.call_args_list[0].args[0]
    assert agent.status is AgentStatus.APPROVED
    assert db.flush.called
    assert db.commit.called


def test_active_administrator_profile_is_auto_approved_on_update():
    db = MagicMock()
    agent = Agent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        first_name="Admin",
        last_name="User",
        status=AgentStatus.PENDING,
    )

    update_agent(
        db,
        agent,
        AgentUpdate(primary_residence="Nairobi"),
        auto_approve=True,
    )

    assert agent.status is AgentStatus.APPROVED
    assert db.add.called
    assert db.commit.called
