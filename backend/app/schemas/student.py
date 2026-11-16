from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudentCreate(BaseModel):
    """
    Fields required when creating a student, faculty, or staff record.

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

    role: Literal["student", "faculty", "staff", "admin"] = "student"

    year_of_study: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
    )

    @model_validator(mode="after")
    def validate_role_and_year(self) -> "StudentCreate":
        if self.role == "student":
            if self.year_of_study is None:
                raise ValueError("Year of study is required for students.")
        else:
            # Non-students do not use year of study
            self.year_of_study = None
        return self


class StudentUpdate(BaseModel):
    """
    Fields allowed when updating ordinary student or staff details.

    Every field is optional so the frontend can update
    individual properties without resending all details.
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

    role: Literal["student", "faculty", "staff", "admin"] | None = None

    year_of_study: int | None = Field(
        default=None,
        ge=1,
        le=4,
    )

    @model_validator(mode="after")
    def validate_role_and_year(self) -> "StudentUpdate":
        if self.role == "student" and self.year_of_study is not None:
            if self.year_of_study not in (1, 2, 3, 4):
                raise ValueError("Year of study must be between 1 and 4.")
        elif self.role and self.role != "student":
            self.year_of_study = None
        return self


class StudentStatusUpdate(BaseModel):
    """Activate or deactivate a record."""

    model_config = ConfigDict(extra="forbid")

    is_active: bool


class StudentResponse(BaseModel):
    """
    Complete information returned by the API.

    Includes ordinary details and enrollment metadata.
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