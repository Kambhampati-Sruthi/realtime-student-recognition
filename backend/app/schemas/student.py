
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    """
    Fields required when creating a student record.

    Face-photo and ID-card enrollment are handled separately
    by the face enrollment endpoint.
    """

    model_config = ConfigDict(extra="forbid")

    roll_no: str = Field(
        min_length=1,
        max_length=50,
    )

    name: str = Field(
        min_length=1,
        max_length=150,
    )

    branch: str = Field(
        min_length=1,
        max_length=100,
    )

    role: Literal["student", "admin"] = "student"

    year_of_study: int | None = Field(
        default=None,
        ge=1,
        le=4,
    )


class StudentUpdate(BaseModel):
    """
    Fields allowed when updating ordinary student details.

    Every field is optional so the frontend can update
    individual student properties without resending all details.

    Enrollment status, face embeddings, and recognition data
    cannot be modified through this schema.
    """

    model_config = ConfigDict(extra="forbid")

    roll_no: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    role: Literal["student", "admin"] | None = None

    year_of_study: int | None = Field(
        default=None,
        ge=1,
        le=4,
    )


class StudentStatusUpdate(BaseModel):
    """Activate or deactivate a student."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool


class StudentResponse(BaseModel):
    """
    Complete student information returned by the API.

    Includes ordinary student details and enrollment metadata.

    Face embeddings and private storage paths are deliberately
    excluded from the public student response.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="ignore",
    )

    id: UUID

    roll_no: str

    name: str

    branch: str | None = None

    role: str | None = None

    year_of_study: int | None = None

    is_active: bool | None = True

    enrollment_status: str = "pending"

    face_enrolled_at: datetime | None = None

    gallery_label: str | None = None

    created_at: datetime | None = None

    updated_at: datetime | None = None
