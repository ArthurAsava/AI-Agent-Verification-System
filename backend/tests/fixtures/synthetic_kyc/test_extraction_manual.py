
from pathlib import Path

from app.services.verification.ocr_service import (
    extract_document_text,
)

from app.services.verification.identity_extractor import (
    extract_identity_fields,
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

print("\n=== IDENTITY EXTRACTION ===")

print("Document type:", identity.document_type)
print("ID number:", identity.id_number)
print("Full name:", identity.full_name)
print("Date of birth:", identity.date_of_birth)
print("Sex:", identity.sex)
print("Warnings:", identity.warnings)
