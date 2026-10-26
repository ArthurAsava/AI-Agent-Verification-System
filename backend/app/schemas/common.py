
from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error: str
    message: str


class DemoRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    age: int = Field(ge=18, le=100)


class DemoResponse(BaseModel):
    message: str
    name: str
    age: int
