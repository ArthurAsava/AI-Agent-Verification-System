from app.models.entities import AvatarVariant


def avatar_variant_from_document_sex(
    document_sex: str | None,
) -> AvatarVariant | None:
    """Map the normalized document field to a supported visual variant."""
    if not isinstance(document_sex, str):
        return None

    normalized = document_sex.strip().upper()
    mapping = {
        "MALE": AvatarVariant.MALE,
        "FEMALE": AvatarVariant.FEMALE,
    }
    return mapping.get(normalized)
