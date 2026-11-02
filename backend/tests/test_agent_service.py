
import uuid
from unittest.mock import MagicMock

from app.services.agent_service import get_agent_by_user_id


def test_agent_query_uses_authenticated_user_id():
    db = MagicMock()
    db.scalar.return_value = None

    user_id = uuid.uuid4()

    result = get_agent_by_user_id(db, user_id)

    assert result is None
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]

    assert statement.compile().params["user_id_1"] == user_id
