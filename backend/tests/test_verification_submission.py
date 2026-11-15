from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.models.entities import AgentStatus
from app.services.verification import submission_service as module
from app.services.verification.decision_contracts import CaseStatus
from app.services.verification.submission_service import (
    VerificationSubmissionResult,
)


def query_result(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def session_context(db):
    context = MagicMock()
    context.__enter__.return_value = db
    context.__exit__.return_value = False
    return context


def test_new_submission_creates_analyzing_case(monkeypatch):
    user_id = uuid4()
    agent_id = uuid4()
    document_id = uuid4()
    case_id = uuid4()

    agent = SimpleNamespace(id=agent_id, status=AgentStatus.PENDING)
    document = SimpleNamespace(
        id=document_id,
        agent_id=agent_id,
        document_type="national_id_front",
        sha256_checksum="a" * 64,
    )
    db = MagicMock()
    db.execute.side_effect = [
        query_result(agent),
        query_result(document),
        query_result(None),
    ]

    def add(instance):
        instance.id = case_id

    db.add.side_effect = add
    monkeypatch.setattr(module, "SessionLocal", lambda: session_context(db))

    result = module._start_submission_sync(
        user_id=user_id,
        document_id=document_id,
    )

    assert result == VerificationSubmissionResult(
        case_id=case_id,
        status=CaseStatus.ANALYZING.value,
        started=True,
    )
    assert agent.status is AgentStatus.UNDER_REVIEW
    db.commit.assert_called_once()


def test_existing_final_case_is_reused_without_reanalysis(monkeypatch):
    user_id = uuid4()
    agent_id = uuid4()
    document_id = uuid4()
    case_id = uuid4()

    agent = SimpleNamespace(id=agent_id, status=AgentStatus.APPROVED)
    document = SimpleNamespace(
        id=document_id,
        agent_id=agent_id,
        document_type="passport",
        sha256_checksum="b" * 64,
    )
    existing = SimpleNamespace(
        id=case_id,
        status=CaseStatus.APPROVED.value,
    )
    db = MagicMock()
    db.execute.side_effect = [
        query_result(agent),
        query_result(document),
        query_result(existing),
    ]
    monkeypatch.setattr(module, "SessionLocal", lambda: session_context(db))

    result = module._start_submission_sync(
        user_id=user_id,
        document_id=document_id,
    )

    assert result == VerificationSubmissionResult(
        case_id=case_id,
        status=CaseStatus.APPROVED.value,
        started=False,
    )
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_submission_runs_analysis_then_returns_review_status(monkeypatch):
    user_id = uuid4()
    document_id = uuid4()
    case_id = uuid4()
    storage = object()

    async def immediate_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    async def complete(**kwargs):
        assert kwargs == {
            "user_id": user_id,
            "document_id": document_id,
            "storage": storage,
            "case_id": case_id,
        }

    monkeypatch.setattr(module, "run_in_threadpool", immediate_threadpool)
    monkeypatch.setattr(
        module,
        "_start_submission_sync",
        lambda **_: VerificationSubmissionResult(
            case_id=case_id,
            status=CaseStatus.ANALYZING.value,
            started=True,
        ),
    )
    monkeypatch.setattr(module, "run_complete_verification", complete)
    monkeypatch.setattr(
        module,
        "_get_case_status_sync",
        lambda _: CaseStatus.AWAITING_REVIEW.value,
    )

    result = await module.submit_document_for_verification(
        user_id=user_id,
        document_id=document_id,
        storage=storage,
    )

    assert result == VerificationSubmissionResult(
        case_id=case_id,
        status=CaseStatus.AWAITING_REVIEW.value,
        started=True,
    )


@pytest.mark.asyncio
async def test_failed_analysis_marks_case_as_failed(monkeypatch):
    case_id = uuid4()
    marked = []

    async def immediate_threadpool(function, *args, **kwargs):
        return function(*args, **kwargs)

    async def fail_analysis(**_):
        raise RuntimeError("Synthetic OCR failure")

    monkeypatch.setattr(module, "run_in_threadpool", immediate_threadpool)
    monkeypatch.setattr(
        module,
        "_start_submission_sync",
        lambda **_: VerificationSubmissionResult(
            case_id=case_id,
            status=CaseStatus.ANALYZING.value,
            started=True,
        ),
    )
    monkeypatch.setattr(module, "run_complete_verification", fail_analysis)
    monkeypatch.setattr(
        module,
        "_mark_analysis_failed_sync",
        lambda received_case_id: marked.append(received_case_id),
    )

    with pytest.raises(RuntimeError, match="Synthetic OCR failure"):
        await module.submit_document_for_verification(
            user_id=uuid4(),
            document_id=uuid4(),
            storage=object(),
        )

    assert marked == [case_id]
