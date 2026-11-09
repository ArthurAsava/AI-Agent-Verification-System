
import pytest

from app.services.verification.identity_extractor import (
    IdentityExtractionResult,
)

from app.services.verification.identity_matcher import (
    AgentIdentityReference,
    MatchStatus,
    match_agent_identity,
)


def make_extracted(
    name="JOHN KAMAU MWANGI",
    id_number="12345678",
    dob="2000-06-15",
):
    return IdentityExtractionResult(
        document_type="national_id",
        full_name=name,
        id_number=id_number,
        date_of_birth=dob,
        sex="MALE",
    )


def make_reference(
    first="John",
    last="Mwangi",
    number=None,
    dob=None,
):
    return AgentIdentityReference(
        first_name=first,
        last_name=last,
        document_number=number,
        date_of_birth=dob,
    )


def test_first_and_last_name_match():
    result = match_agent_identity(
        make_reference(),
        make_extracted(),
    )

    assert result.fields[0].status == MatchStatus.MATCH


def test_middle_name_is_allowed():
    result = match_agent_identity(
        make_reference(),
        make_extracted(name="JOHN PETER KAMAU MWANGI"),
    )

    assert result.fields[0].status == MatchStatus.MATCH


def test_case_insensitive_name_matching():
    result = match_agent_identity(
        make_reference(first="john", last="mwangi"),
        make_extracted(name="JOHN KAMAU MWANGI"),
    )

    assert result.fields[0].status == MatchStatus.MATCH


def test_name_mismatch():
    result = match_agent_identity(
        make_reference(first="Jane"),
        make_extracted(),
    )

    assert result.fields[0].status == MatchStatus.MISMATCH
    assert result.overall_status == MatchStatus.MISMATCH


def test_missing_name_is_unknown():
    result = match_agent_identity(
        make_reference(),
        make_extracted(name=None),
    )

    assert result.fields[0].status == MatchStatus.UNKNOWN


def test_document_number_exact_match():
    result = match_agent_identity(
        make_reference(number="12345678"),
        make_extracted(),
    )

    assert result.fields[1].status == MatchStatus.MATCH


def test_document_number_mismatch():
    result = match_agent_identity(
        make_reference(number="87654321"),
        make_extracted(),
    )

    assert result.fields[1].status == MatchStatus.MISMATCH


def test_missing_reference_number_is_unknown():
    result = match_agent_identity(
        make_reference(),
        make_extracted(),
    )

    assert result.fields[1].status == MatchStatus.UNKNOWN


def test_date_of_birth_match():
    result = match_agent_identity(
        make_reference(dob="2000-06-15"),
        make_extracted(),
    )

    assert result.fields[2].status == MatchStatus.MATCH


def test_date_of_birth_mismatch():
    result = match_agent_identity(
        make_reference(dob="1999-01-01"),
        make_extracted(),
    )

    assert result.fields[2].status == MatchStatus.MISMATCH


def test_all_fields_match():
    result = match_agent_identity(
        make_reference(
            number="12345678",
            dob="2000-06-15",
        ),
        make_extracted(),
    )

    assert result.overall_status == MatchStatus.MATCH


def test_partial_reference_is_unknown():
    result = match_agent_identity(
        make_reference(),
        make_extracted(),
    )

    assert result.overall_status == MatchStatus.UNKNOWN


def test_extraction_warnings_preserved():
    extracted = IdentityExtractionResult(
        document_type="national_id",
        full_name="JOHN KAMAU MWANGI",
        id_number=None,
        date_of_birth=None,
        warnings=["Document number could not be extracted."],
    )

    result = match_agent_identity(
        make_reference(),
        extracted,
    )

    assert (
        "Document number could not be extracted."
        in result.warnings
    )


def test_mismatch_produces_review_warning():
    result = match_agent_identity(
        make_reference(first="Jane"),
        make_extracted(),
    )

    assert "full_name requires manual review." in result.warnings
