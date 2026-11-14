from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    course_code: str = Field(..., examples=["CS101"])
    title: str = Field(..., examples=["Introduction to Computer Science"])
    description: str | None = None
    instructor_name: str | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    platform_id: str
    course_code: str
    title: str
    description: str | None = None
    instructor_name: str | None = None
    is_active: bool
    created_at: datetime


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    course_id: str
    platform_id: str
    title: str
    file_type: str
    file_size: int
    is_processed: bool
    chunk_count: int
    created_at: datetime


class KnowledgeSearchRequest(BaseModel):
    query: str
    course_id: str | None = None
    top_k: int = 4


class KnowledgeChunkResult(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    content: str
    page_number: int | None = None
    section_title: str | None = None
    score: float
