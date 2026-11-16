import pytest

from app.models.entities import AvatarVariant
from app.services.profile_avatar_service import (
    avatar_variant_from_document_sex,
)


@pytest.mark.parametrize(
    ("document_sex", "expected"),
    [
        ("MALE", AvatarVariant.MALE),
        ("female", AvatarVariant.FEMALE),
        ("X", None),
        (None, None),
    ],
)
def test_avatar_variant_is_limited_to_supported_document_values(
    document_sex,
    expected,
):
    assert avatar_variant_from_document_sex(document_sex) is expected
