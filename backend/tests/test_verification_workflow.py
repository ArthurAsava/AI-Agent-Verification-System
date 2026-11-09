
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.verification.persistence import (
    VerificationIntegrityError,
)
from app.services.verification.workflow import (
    run_document_verification,
)


AGENT_ID = uuid4()
DOCUMENT_ID = uuid4()
CHECK_ID = uuid4()


def make_db(agent_exists=True, document_exists=True):
    db = MagicMock()

    agent = (
        SimpleNamespace(
            id=AGENT_ID,
            first_name="John",
            last_name="Mwangi",
        )
        if agent_exists else None
    )

    document = (
        SimpleNamespace(
            id=DOCUMENT_ID,
            agent_id=AGENT_ID,
            document_type="national_id",
            mime_type="image/png",
        )
        if document_exists else None
    )

    db.execute.side_effect = [
        MagicMock(
            scalar_one_or_none=MagicMock(
                return_value=agent
            )
        ),
        MagicMock(
            scalar_one_or_none=MagicMock(
                return_value=document
            )
        ),
    ]

    return db


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_workflow_saves_verification(
    mock_pipeline,
    mock_save,
):
    db = make_db()

    mock_pipeline.return_value = SimpleNamespace(
        analysis=SimpleNamespace(
            outcome="needs_review"
        )
    )

    mock_save.return_value = SimpleNamespace(
        id=CHECK_ID
    )

    result = run_document_verification(
        db=db,
        agent_id=AGENT_ID,
        document_id=DOCUMENT_ID,
        document_bytes=b"synthetic document",
    )

    assert result.check_id == CHECK_ID
    mock_pipeline.assert_called_once()
    mock_save.assert_called_once()


@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_missing_agent_rejected(mock_pipeline):
    db = make_db(agent_exists=False)

    with pytest.raises(VerificationIntegrityError):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    mock_pipeline.assert_not_called()


@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_missing_document_rejected(mock_pipeline):
    db = make_db(document_exists=False)

    with pytest.raises(VerificationIntegrityError):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    mock_pipeline.assert_not_called()


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_actor_user_id_forwarded(
    mock_pipeline,
    mock_save,
):
    db = make_db()
    actor_id = uuid4()

    mock_pipeline.return_value = SimpleNamespace(
        analysis=SimpleNamespace(
            outcome="needs_review"
        )
    )
    mock_save.return_value = SimpleNamespace(
        id=CHECK_ID
    )

    run_document_verification(
        db=db,
        agent_id=AGENT_ID,
        document_id=DOCUMENT_ID,
        document_bytes=b"synthetic document",
        actor_user_id=actor_id,
    )

    assert (
        mock_save.call_args.kwargs["actor_user_id"]
        == actor_id
    )
