import pytest

from app.services.kyc_upload_service import (
    DOCUMENT_REQUIREMENTS_MESSAGE,
    has_complete_document_set,
)


@pytest.mark.parametrize(
    ("document_types", "complete"),
    [
        ((), False),
        (("national_id_front",), False),
        (("passport",), False),
        (("national_id_front", "national_id_back"), True),
        (("passport", "proof_of_address"), True),
        (
            ("national_id_front", "passport", "proof_of_address"),
            True,
        ),
    ],
)
def test_document_requirement_paths(document_types, complete):
    assert has_complete_document_set(document_types) is complete


def test_document_requirement_message_explains_both_paths():
    assert "both sides" in DOCUMENT_REQUIREMENTS_MESSAGE
    assert "passport" in DOCUMENT_REQUIREMENTS_MESSAGE
