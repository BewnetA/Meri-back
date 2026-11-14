from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.job import Job


class Platform(Base, TimestampMixin):
    __tablename__ = "platforms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    public_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    secret_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    domains: Mapped[list[PlatformDomain]] = relationship(
        "PlatformDomain", back_populates="platform", cascade="all, delete-orphan"
    )
    configuration: Mapped[PlatformConfiguration | None] = relationship(
        "PlatformConfiguration",
        back_populates="platform",
        uselist=False,
        cascade="all, delete-orphan",
    )
    integrations: Mapped[list[PlatformIntegration]] = relationship(
        "PlatformIntegration", back_populates="platform", cascade="all, delete-orphan"
    )
    courses: Mapped[list[Course]] = relationship(
        "Course", back_populates="platform", cascade="all, delete-orphan"
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job", back_populates="platform", cascade="all, delete-orphan"
    )


class PlatformDomain(Base, TimestampMixin):
    __tablename__ = "platform_domains"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    platform: Mapped[Platform] = relationship("Platform", back_populates="domains")


class PlatformConfiguration(Base, TimestampMixin):
    __tablename__ = "platform_configurations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # Appearance and branding matching Frontend Specification section 4
    platform_name: Mapped[str] = mapped_column(String(255), default="BridgeMate Platform")
    theme: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "primary": "#16A34A",
            "secondary": "#14532D",
            "background": "#FFFFFF",
            "text": "#111827",
            "chat_button": "#16A34A",
        },
    )
    branding: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "logo_url": "https://bridgemate.example.com/logo.png",
        },
    )
    welcome_message: Mapped[str] = mapped_column(
        String(1000),
        default="Hello! I'm your BridgeMate AI learning and career assistant. How can I assist you today?",
    )
    language: Mapped[str] = mapped_column(String(10), default="en")  # en, am
    position: Mapped[str] = mapped_column(
        String(20), default="bottom-right"
    )  # bottom-right, bottom-left
    size: Mapped[str] = mapped_column(String(20), default="medium")  # medium, compact, large

    # Feature flags
    features: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "voice": True,
            "human_support": True,
            "simple_mode": True,
            "job_assistance": True,
            "course_assistant": True,
        },
    )

    # Custom DOM / Page Extraction rules for platforms
    context_extraction_rules: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {
            "selectors": {
                "course_title": "h1.course-title, .course-header h1, [data-testid='course-title']",
                "lesson_title": "h2.lesson-title, .lesson-header h2",
                "job_title": "h1.job-title, [data-testid='job-title']",
            },
            "allowed_schemes": ["http", "https"],
        },
    )

    platform: Mapped[Platform] = relationship("Platform", back_populates="configuration")


class PlatformIntegration(Base, TimestampMixin):
    __tablename__ = "platform_integrations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("platforms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    integration_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # lms_moodle, canvas, custom_webhook, direct_api
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, pending, disabled
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    platform: Mapped[Platform] = relationship("Platform", back_populates="integrations")
