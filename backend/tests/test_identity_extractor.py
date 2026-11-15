
import pytest

from app.services.verification.identity_extractor import (
    IdentityExtractionError,
    extract_identity_fields,
)

from app.services.verification.ocr_service import (
    OCRPageResult,
    OCRResult,
)


def make_ocr_result(text: str) -> OCRResult:
    return OCRResult(
        text=text,
        page_count=1,
        pages=[
            OCRPageResult(
                page_number=1,
                text=text,
            )
        ],
        warnings=[],
    )


def test_extract_complete_national_id():
    text = """
    REPUBLIC OF KENYA
    NATIONAL IDENTITY CARD
    ID NUMBER: 12345678
    FULL NAME: JOHN KAMAU MWANGI
    DATE OF BIRTH: 15/06/2000
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.id_number == "12345678"
    assert result.full_name == "JOHN KAMAU MWANGI"
    assert result.date_of_birth == "2000-06-15"
    assert result.sex == "MALE"
    assert result.warnings == []


def test_extract_national_id_front_preserves_storage_type():
    text = """
    ID NUMBER: 12345678
    FULL NAME: JOHN KAMAU MWANGI
    DATE OF BIRTH: 15/06/2000
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id_front",
    )

    assert result.document_type == "national_id_front"
    assert result.id_number == "12345678"


def test_extract_passport():
    text = """
    PASSPORT NUMBER: A12345678
    FULL NAME: JANE WANJIKU
    DATE OF BIRTH: 1999-05-20
    SEX: F
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "passport",
    )

    assert result.id_number == "A12345678"
    assert result.full_name == "JANE WANJIKU"
    assert result.date_of_birth == "1999-05-20"
    assert result.sex == "FEMALE"


def test_missing_id_number():
    text = """
    FULL NAME: JOHN KAMAU
    DATE OF BIRTH: 15/06/2000
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.id_number is None
    assert (
        "Document number could not be extracted."
        in result.warnings
    )


def test_invalid_birth_date():
    text = """
    ID NUMBER: 12345678
    FULL NAME: JOHN KAMAU
    DATE OF BIRTH: 35/13/2000
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.date_of_birth is None
    assert (
        "Date of birth could not be extracted."
        in result.warnings
    )


def test_future_birth_date():
    text = """
    ID NUMBER: 12345678
    FULL NAME: JOHN KAMAU
    DATE OF BIRTH: 2099-01-01
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.date_of_birth is None


def test_normalizes_name():
    text = """
    ID NUMBER: 12345678
    FULL NAME:   mary   njoki   kamau
    DATE OF BIRTH: 10-08-1998
    SEX: FEMALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.full_name == "MARY NJOKI KAMAU"


def test_invalid_id_number():
    text = """
    ID NUMBER: ABC123
    FULL NAME: JOHN KAMAU
    DATE OF BIRTH: 15/06/2000
    SEX: MALE
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.id_number is None


def test_unsupported_document_type():
    with pytest.raises(IdentityExtractionError):
        extract_identity_fields(
            make_ocr_result("SOME TEXT"),
            "driving_license",
        )


def test_empty_ocr_text():
    with pytest.raises(IdentityExtractionError):
        extract_identity_fields(
            make_ocr_result(""),
            "national_id",
        )


def test_partial_extraction():
    text = """
    FULL NAME: JOHN KAMAU
    SEX: M
    """

    result = extract_identity_fields(
        make_ocr_result(text),
        "national_id",
    )

    assert result.full_name == "JOHN KAMAU"
    assert result.sex == "MALE"
    assert result.id_number is None
    assert result.date_of_birth is None
    assert len(result.warnings) == 2
