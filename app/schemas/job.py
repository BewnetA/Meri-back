from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobCreate(BaseModel):
    title: str = Field(..., examples=["Junior Python Developer"])
    company: str = Field(..., examples=["Savanna Tech Hub"])
    location: str = Field(default="Addis Ababa")
    description: str = Field(..., examples=["We are looking for a motivated Python developer..."])
    requirements: list[str] = Field(
        default_factory=list, examples=[["Python", "Django", "FastAPI"]]
    )
    skills: list[str] = Field(default_factory=list, examples=[["Python", "REST APIs", "Git"]])
    application_instructions: str | None = "Submit CV and portfolio via platform"
    job_url: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform_id: str
    title: str
    company: str
    location: str
    description: str
    requirements: list[str]
    skills: list[str]
    application_instructions: str | None
    job_url: str | None
    is_active: bool
    created_at: datetime


class JobAlertCreate(BaseModel):
    keywords: str | None = None
    skills: list[str] = Field(default_factory=list)
    location: str | None = None
    notify_telegram: bool = True
    notify_sms: bool = False


class JobAlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    platform_id: str
    keywords: str | None
    skills: list[str]
    location: str | None
    notify_telegram: bool
    notify_sms: bool
    is_active: bool
    created_at: datetime


class AccommodationRequestCreate(BaseModel):
    job_id: str
    details: str = Field(
        ..., examples=["Screen reader accommodations and extended test duration requested."]
    )
    consent_given: bool = Field(..., examples=[True])


class AccommodationRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    user_id: str
    platform_id: str
    details: str
    status: str
    consent_given: bool
    created_at: datetime
