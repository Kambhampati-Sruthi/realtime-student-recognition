
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    """Fields required when registering a student."""

    roll_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    branch: str | None = Field(default=None, max_length=100)
    role: str = Field(default="student", min_length=1, max_length=50)


class StudentUpdate(BaseModel):
    """Fields allowed when updating student details."""

    roll_no: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=150)
    branch: str | None = Field(default=None, max_length=100)
    role: str = Field(min_length=1, max_length=50)


class StudentStatusUpdate(BaseModel):
    """Activate or deactivate a student."""

    is_active: bool


class StudentResponse(BaseModel):
    """Student data returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    roll_no: str
    name: str
    branch: str | None = None
    role: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
