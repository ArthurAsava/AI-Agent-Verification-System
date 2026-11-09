
from pathlib import Path
from uuid import uuid4

from app.services.verification.identity_matcher import (
    AgentIdentityReference,
)

from app.services.verification.pipeline import (
    analyze_kyc_document,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "synthetic_national_id.png"
)

content = FIXTURE.read_bytes()

reference = AgentIdentityReference(
    first_name="John",
    last_name="Mwangi",
)

result = analyze_kyc_document(
    document_id=uuid4(),
    document_type="national_id",
    content=content,
    mime_type="image/png",
    agent_reference=reference,
)

print("\n=== VERIFICATION PIPELINE ===")

print(
    "Verification outcome:",
    result.analysis.outcome,
)

print(
    "Quality score:",
    result.quality_score,
)

print(
    "Quality status:",
    result.quality_status,
)

print(
    "Match status:",
    result.match_status,
)

print(
    "Warnings:",
    result.analysis.warnings,
)

print(
    "Analyzer version:",
    result.analysis.analyzer_version,
)
