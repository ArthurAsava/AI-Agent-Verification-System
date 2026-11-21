from pydantic import BaseModel, SecretStr, field_validator


class AccountDeletionRequest(BaseModel):
    """Password confirmation required before an account is deleted."""

    password: SecretStr

    @field_validator("password")
    @classmethod
    def password_must_not_be_empty(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("Password is required")
        return value


class AccountDeletionEligibilityResponse(BaseModel):
    """Whether the signed-in account is eligible for self-service deletion."""

    eligible: bool


class AccountDeletionResponse(BaseModel):
    deleted: bool = True
