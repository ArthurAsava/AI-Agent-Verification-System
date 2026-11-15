
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.verification.identity_matcher import (
    AgentIdentityReference,
    FieldMatchResult,
    IdentityMatchResult,
    MatchStatus,
)
from app.services.verification.identity_extractor import (
    IdentityExtractionResult,
)
from app.services.verification.ocr_service import (
    OCRPageResult,
    OCRResult,
)
from app.services.verification.document_quality import (
    DocumentQualityResult,
)
from app.services.verification.pipeline import (
    analyze_kyc_document,
)
from app.services.verification.contracts import (
    VerificationOutcome,
)


DOCUMENT_ID = uuid4()


def make_reference():
    return AgentIdentityReference(
        first_name="John",
        last_name="Mwangi",
    )


def make_ocr():
    return OCRResult(
        text="SYNTHETIC DOCUMENT TEXT",
        page_count=1,
        pages=[
            OCRPageResult(
                page_number=1,
                text="SYNTHETIC DOCUMENT TEXT",
            )
        ],
        warnings=[],
    )


def make_identity(warnings=None):
    return IdentityExtractionResult(
        document_type="national_id",
        id_number="12345678",
        full_name="JOHN KAMAU MWANGI",
        date_of_birth="2000-06-15",
        sex="MALE",
        warnings=warnings or [],
    )


def make_match(status):
    return IdentityMatchResult(
        overall_status=status,
        fields=[
            FieldMatchResult(
                field_name="full_name",
                status=status,
                reason="Synthetic comparison result.",
            )
        ],
        warnings=[],
    )


def make_quality(status="pass"):
    return DocumentQualityResult(
        score=90 if status == "pass" else 50,
        status=status,
        page_count=1,
        metrics=[],
        warnings=(
            [] if status == "pass"
            else ["Possible image blur."]
        ),
    )


def run_mocked_pipeline(
    match_status=MatchStatus.MATCH,
    quality_status="pass",
    identity_warnings=None,
):
    with (
        patch(
            "app.services.verification.pipeline."
            "process_document"
        ),
        patch(
            "app.services.verification.pipeline."
            "extract_document_text",
            return_value=make_ocr(),
        ),
        patch(
            "app.services.verification.pipeline."
            "extract_identity_fields",
            return_value=make_identity(identity_warnings),
        ),
        patch(
            "app.services.verification.pipeline."
            "match_agent_identity",
            return_value=make_match(match_status),
        ),
        patch(
            "app.services.verification.pipeline."
            "analyze_document_quality",
            return_value=make_quality(quality_status),
        ),
    ):
        return analyze_kyc_document(
            document_id=DOCUMENT_ID,
            document_type="national_id",
            content=b"synthetic document bytes",
            mime_type="image/png",
            agent_reference=make_reference(),
        )


def test_matching_document_passes():
    result = run_mocked_pipeline()

    assert (
        result.analysis.outcome
        == VerificationOutcome.PASS
    )


def test_name_mismatch_requires_review():
    result = run_mocked_pipeline(
        match_status=MatchStatus.MISMATCH,
    )

    assert (
        result.analysis.outcome
        == VerificationOutcome.NEEDS_REVIEW
    )


def test_unknown_match_requires_review():
    result = run_mocked_pipeline(
        match_status=MatchStatus.UNKNOWN,
    )

    assert (
        result.analysis.outcome
        == VerificationOutcome.NEEDS_REVIEW
    )


def test_low_quality_requires_review():
    result = run_mocked_pipeline(
        quality_status="needs_review",
    )

    assert (
        result.analysis.outcome
        == VerificationOutcome.NEEDS_REVIEW
    )


def test_extraction_warning_requires_review():
    result = run_mocked_pipeline(
        identity_warnings=["Document number unavailable."],
    )

    assert (
        result.analysis.outcome
        == VerificationOutcome.NEEDS_REVIEW
    )


def test_sensitive_identity_values_not_persisted():
    result = run_mocked_pipeline()

    serialized = result.analysis.model_dump_json()

    assert "JOHN KAMAU MWANGI" not in serialized
    assert "12345678" not in serialized
    assert "2000-06-15" not in serialized
    assert "SYNTHETIC DOCUMENT TEXT" not in serialized


def test_document_id_preserved():
    result = run_mocked_pipeline()

    assert result.analysis.document_id == DOCUMENT_ID


def test_pipeline_version_recorded():
    result = run_mocked_pipeline()

    assert (
        result.analysis.analyzer_version
        == "document-pipeline-v1"
    )
