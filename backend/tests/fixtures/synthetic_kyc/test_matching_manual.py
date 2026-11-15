
from pathlib import Path

from app.services.verification.ocr_service import (
    extract_document_text,
)

from app.services.verification.identity_extractor import (
    extract_identity_fields,
)

from app.services.verification.identity_matcher import (
    AgentIdentityReference,
    match_agent_identity,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "synthetic_national_id.png"
)

content = FIXTURE.read_bytes()

ocr_result = extract_document_text(
    content,
    "image/png",
)

identity = extract_identity_fields(
    ocr_result,
    "national_id",
)

reference = AgentIdentityReference(
    first_name="John",
    last_name="Mwangi",
)

match_result = match_agent_identity(
    reference,
    identity,
)

print("\n=== IDENTITY MATCHING ===")

print("Overall status:", match_result.overall_status)

for field in match_result.fields:
    print(
        field.field_name,
        ":",
        field.status,
    )

print("Warnings:", match_result.warnings)
