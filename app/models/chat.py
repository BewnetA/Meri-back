from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.platform import Platform
    from app.models.user import User


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    session_source: Mapped[str] = mapped_column(
        String(50), default="web_plugin"
    )  # web_plugin, telegram
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    current_page_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # course, lesson, assignment, job, application, general
    current_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="conversations")
    platform: Mapped[Platform] = relationship("Platform")
    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # learner, assistant, system, human_agent
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Context snapshots & AI responses
    page_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    provider_used: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # gemini, groq, offline_faq, human_agent

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
