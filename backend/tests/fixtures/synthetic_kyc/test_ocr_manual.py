
from pathlib import Path

from app.services.verification.ocr_service import (
    extract_document_text,
)


FIXTURE = (
    Path(__file__).resolve().parent
    / "synthetic_national_id.png"
)

content = FIXTURE.read_bytes()

result = extract_document_text(
    content,
    "image/png",
)

print("\n=== OCR RESULT ===")

print(result.text)

print("\n=== WARNINGS ===")

print(result.warnings)
