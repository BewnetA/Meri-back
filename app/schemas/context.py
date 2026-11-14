from typing import Any

from pydantic import BaseModel, Field


class PageContextPayload(BaseModel):
    page_type: str = Field(
        ..., examples=["job"]
    )  # course, lesson, assignment, job, application, general
    url: str = Field(..., examples=["/jobs/junior-python-developer"])
    title: str = Field(..., examples=["Junior Python Developer"])
    content: dict[str, Any] | str = Field(default_factory=dict)
    metadata: dict[str, Any] | None = Field(default_factory=dict)
    course_id: str | None = None
    lesson_id: str | None = None
    job_id: str | None = None


class ContextAnalyzeRequest(BaseModel):
    context: PageContextPayload
    language: str | None = "en"


class ContextValidationResult(BaseModel):
    is_valid: bool
    page_type: str
    sanitized_content: dict[str, Any]
    detected_entities: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class PageTypeInfo(BaseModel):
    type_name: str
    description: str
    extracted_fields: list[str]
    suggested_quick_actions: list[str]
