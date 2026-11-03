
from app.services.onboarding_service import (
    calculate_progress,
)


def test_empty_profile_progress():
    result = calculate_progress({})

    assert result.percentage == 0
    assert result.completed_fields == 0
    assert len(result.missing_fields) == 5


def test_partially_complete_profile():
    result = calculate_progress({
        "first_name": "Jane",
        "last_name": "Doe",
        "phone_number": "+254712345678",
        "county": None,
        "city": None,
    })

    assert result.percentage == 60
    assert result.completed_fields == 3
    assert result.profile_complete is False


def test_complete_profile():
    result = calculate_progress({
        "first_name": "Jane",
        "last_name": "Doe",
        "phone_number": "+254712345678",
        "county": "Nairobi",
        "city": "Nairobi",
    })

    assert result.percentage == 100
    assert result.profile_complete is True
    assert result.missing_fields == []


def test_whitespace_does_not_count():
    result = calculate_progress({
        "first_name": " ",
        "last_name": "Doe",
        "phone_number": " ",
        "county": "Nairobi",
        "city": "Nairobi",
    })

    assert result.percentage == 60
    assert "first_name" in result.missing_fields
    assert "phone_number" in result.missing_fields
