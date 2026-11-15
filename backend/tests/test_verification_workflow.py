
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
from app.services.verification.document_integrity import (
    calculate_sha256,
    DocumentIntegrityError,
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
        sha256_checksum=calculate_sha256(
            b"synthetic document"
        ),
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


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_modified_document_never_reaches_pipeline(
    mock_pipeline,
    mock_save,
):
    db = make_db()

    with pytest.raises(DocumentIntegrityError):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"modified document",
        )

    mock_pipeline.assert_not_called()
    mock_save.assert_not_called()



@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_missing_checksum_blocks_analysis(
    mock_pipeline,
    mock_save,
):
    db = make_db()

    # Retrieve the mocked query results without consuming
    # the iterator used by the workflow.
    query_results = list(db.execute.side_effect)

    # The second query result contains the KYC document.
    document = query_results[1].scalar_one_or_none.return_value

    # Simulate a document with no stored checksum.
    document.sha256_checksum = None

    # Restore the query results for the workflow.
    db.execute.side_effect = query_results

    with pytest.raises(DocumentIntegrityError):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    # The document must not reach OCR or persistence.
    mock_pipeline.assert_not_called()
    mock_save.assert_not_called()


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_cross_agent_document_access_blocked(
    mock_pipeline,
    mock_save,
):
    """
    Verify that an agent cannot process a KYC document
    that does not belong to them.
    """

    # Create a mocked database where the document
    # lookup returns no document for this agent.
    db = make_db(document_exists=False)

    # Simulate a different agent requesting the document.
    other_agent_id = uuid4()

    # The verification workflow must reject the request.
    with pytest.raises(VerificationIntegrityError):
        run_document_verification(
            db=db,
            agent_id=other_agent_id,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    # OCR and identity verification must never run.
    mock_pipeline.assert_not_called()

    # No verification result should be saved.
    mock_save.assert_not_called()


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_pipeline_failure_does_not_persist(
    mock_pipeline,
    mock_save,
):
    """
    Ensure a failed verification pipeline does not
    save a verification result.
    """

    # Create a valid mocked database.
    db = make_db()

    # Simulate an OCR or document analysis failure.
    mock_pipeline.side_effect = RuntimeError(
        "Synthetic OCR failure"
    )

    # The workflow should propagate the error.
    with pytest.raises(
        RuntimeError,
        match="Synthetic OCR failure",
    ):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    # The analysis pipeline was attempted.
    mock_pipeline.assert_called_once()

    # No verification result should be saved.
    mock_save.assert_not_called()


@patch(
    "app.services.verification.workflow."
    "save_document_analysis"
)
@patch(
    "app.services.verification.workflow."
    "analyze_kyc_document"
)
def test_persistence_failure_propagates(
    mock_pipeline,
    mock_save,
):
    """
    Ensure persistence failures are not silently
    converted into successful verification results.
    """

    db = make_db()

    # Simulate a completed verification analysis.
    mock_pipeline.return_value = SimpleNamespace(
        analysis=SimpleNamespace(
            outcome="needs_review"
        )
    )

    # Simulate a database failure during persistence.
    mock_save.side_effect = RuntimeError(
        "Synthetic database failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic database failure",
    ):
        run_document_verification(
            db=db,
            agent_id=AGENT_ID,
            document_id=DOCUMENT_ID,
            document_bytes=b"synthetic document",
        )

    # Both the pipeline and persistence were attempted.
    mock_pipeline.assert_called_once()
    mock_save.assert_called_once()
