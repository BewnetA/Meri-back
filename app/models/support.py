from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.chat import Conversation
    from app.models.platform import Platform
    from app.models.user import User


class SupportTicket(Base, TimestampMixin):
    __tablename__ = "support_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    subject: Mapped[str] = mapped_column(String(255), default="Human Assistance Request")
    status: Mapped[str] = mapped_column(
        String(50), default="open"
    )  # open, assigned, resolved, closed
    consent_share_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    screen_sharing_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    learner: Mapped[User] = relationship(
        "User", foreign_keys=[learner_id], back_populates="support_tickets"
    )
    assigned_agent: Mapped[User | None] = relationship("User", foreign_keys=[assigned_agent_id])
    conversation: Mapped[Conversation | None] = relationship("Conversation")
    platform: Mapped[Platform] = relationship("Platform")
    messages: Mapped[list[SupportMessage]] = relationship(
        "SupportMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportMessage.created_at",
    )


class SupportMessage(Base, TimestampMixin):
    __tablename__ = "support_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sender_role: Mapped[str] = mapped_column(String(50), nullable=False)  # learner, support_agent
    content: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[SupportTicket] = relationship("SupportTicket", back_populates="messages")
    sender: Mapped[User] = relationship("User")
