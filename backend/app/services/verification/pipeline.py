
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.services.verification.contracts import (
    DocumentAnalysisResult,
    VerificationOutcome,
)
from app.services.verification.document_processor import (
    process_document,
)
from app.services.verification.ocr_service import (
    extract_document_text,
)
from app.services.verification.identity_extractor import (
    extract_identity_fields,
)
from app.services.verification.identity_matcher import (
    AgentIdentityReference,
    MatchStatus,
    match_agent_identity,
)
from app.services.verification.document_quality import (
    analyze_document_quality,
)


PIPELINE_VERSION = "document-pipeline-v1"


@dataclass(frozen=True)
class VerificationPipelineResult:
    analysis: DocumentAnalysisResult
    quality_score: int
    quality_status: str
    match_status: MatchStatus


def analyze_kyc_document(
    *,
    document_id: UUID,
    document_type: str,
    content: bytes,
    mime_type: str,
    agent_reference: AgentIdentityReference,
) -> VerificationPipelineResult:
    """
    Analyze a KYC document already retrieved by an
    authorized caller.

    Does not access storage or the database.
    Does not approve or reject an agent.
    """

    # 1. Validate the document.
    process_document(content, mime_type)

    # 2. Perform OCR.
    ocr_result = extract_document_text(
        content,
        mime_type,
    )

    # 3. Extract structured identity information.
    identity_result = extract_identity_fields(
        ocr_result,
        document_type,
    )

    # 4. Compare against the agent's reference details.
    match_result = match_agent_identity(
        agent_reference,
        identity_result,
    )

    # 5. Analyze document quality.
    quality_result = analyze_document_quality(
        content,
        mime_type,
        ocr_result,
    )

    # 6. Determine a conservative verification outcome.
    #
    # A mismatch, unknown comparison or quality concern
    # requires review. This pipeline does not issue an
    # automatic identity rejection.
    if (
        match_result.overall_status == MatchStatus.MATCH
        and quality_result.status == "pass"
        and not identity_result.warnings
    ):
        outcome = VerificationOutcome.PASS
    else:
        outcome = VerificationOutcome.NEEDS_REVIEW

    # 7. Combine explainable warnings.
    warnings = list(
        dict.fromkeys(
            identity_result.warnings
            + match_result.warnings
            + quality_result.warnings
        )
    )

    # 8. Create a Phase 8A-compatible result.
    #
    # Only non-sensitive diagnostic information is
    # included. Names, ID numbers, dates of birth
    # and raw OCR text are not persisted here.
    analysis = DocumentAnalysisResult(
        document_id=document_id,
        document_type=document_type,
        outcome=outcome,
        extracted_fields={
            "identity_fields_detected": {
                "full_name": identity_result.full_name is not None,
                "document_number": identity_result.id_number is not None,
                "date_of_birth": (
                    identity_result.date_of_birth is not None
                ),
                "sex": identity_result.sex is not None,
            },
            "matching": {
                item.field_name: item.status.value
                for item in match_result.fields
            },
            "overall_match_status": (
                match_result.overall_status.value
            ),
            "quality_score": quality_result.score,
            "quality_status": quality_result.status,
            "page_count": quality_result.page_count,
            "quality_analyzer_version": (
                quality_result.analyzer_version
            ),
            "matcher_version": (
                match_result.matcher_version
            ),
        },
        warnings=warnings,
        analyzer_version=PIPELINE_VERSION,
    )

    return VerificationPipelineResult(
        analysis=analysis,
        quality_score=quality_result.score,
        quality_status=quality_result.status,
        match_status=match_result.overall_status,
    )
