from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.context import PageContextPayload


class CitationItem(BaseModel):
    document_title: str
    page_number: int | None = None
    section_or_lesson: str | None = None
    source_reference: str | None = None
    snippet: str | None = None


class ChatMessageRequest(BaseModel):
    message: str = Field(..., examples=["Can you explain this lesson in simple terms?"])
    conversation_id: str | None = None
    context: PageContextPayload | None = None
    language: str = Field(default="en", examples=["en"])  # en, am
    simple_mode: bool = False


class ChatMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    response: str
    language: str
    provider_used: str  # gemini, groq, offline_faq, human_agent
    citations: list[CitationItem] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    timestamp: datetime


class MessageItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    sender: str
    content: str
    language: str
    created_at: datetime
    citations: list[CitationItem] | None = None
    provider_used: str | None = None


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    platform_id: str
    session_source: str
    title: str | None = None
    created_at: datetime
    messages: list[MessageItem] = Field(default_factory=list)
