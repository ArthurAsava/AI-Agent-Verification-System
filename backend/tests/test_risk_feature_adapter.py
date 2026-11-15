
from uuid import uuid4

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    VerificationOutcome,
)
from app.services.verification.identity_matcher import MatchStatus
from app.services.verification.pipeline import (
    VerificationPipelineResult,
)
from app.services.verification.risk_feature_adapter import (
    extract_risk_features_from_analysis,
)


def make_result(
    match=MatchStatus.MATCH,
    quality="pass",
    name=True,
    number=True,
):
    return VerificationPipelineResult(
        analysis=DocumentAnalysisResult(
            document_id=uuid4(),
            document_type="national_id",
            outcome=VerificationOutcome.PASS,
            extracted_fields={
                "identity_fields_detected": {
                    "full_name": name,
                    "document_number": number,
                }
            },
            warnings=[],
            analyzer_version="document-pipeline-v1",
        ),
        quality_score=90,
        quality_status=quality,
        match_status=match,
    )


def test_matching_document():
    features = extract_risk_features_from_analysis(
        make_result()
    )
    assert features.identity_match == "match"
    assert features.document_quality == "pass"
    assert not features.missing_required_fields


def test_missing_identity_field():
    features = extract_risk_features_from_analysis(
        make_result(number=False)
    )
    assert features.missing_required_fields


def test_mismatch():
    features = extract_risk_features_from_analysis(
        make_result(match=MatchStatus.MISMATCH)
    )
    assert features.identity_match == "mismatch"


def test_unknown_quality_requires_caution():
    features = extract_risk_features_from_analysis(
        make_result(quality="unrecognized")
    )
    assert features.document_quality == "unknown"
