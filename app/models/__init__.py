from app.core.database import Base
from app.models.chat import Conversation, Message
from app.models.common import FAQEntry, IntegrationEvent
from app.models.course import Course, Document, DocumentChunk, Enrollment
from app.models.job import AccommodationRequest, Job, JobAlert
from app.models.platform import (
    Platform,
    PlatformConfiguration,
    PlatformDomain,
    PlatformIntegration,
)
from app.models.support import SupportMessage, SupportTicket
from app.models.user import TelegramAccount, User, UserPhone, UserPlatformMembership

__all__ = [
    "AccommodationRequest",
    "Base",
    "Conversation",
    "Course",
    "Document",
    "DocumentChunk",
    "Enrollment",
    "FAQEntry",
    "IntegrationEvent",
    "Job",
    "JobAlert",
    "Message",
    "Platform",
    "PlatformConfiguration",
    "PlatformDomain",
    "PlatformIntegration",
    "SupportMessage",
    "SupportTicket",
    "TelegramAccount",
    "User",
    "UserPhone",
    "UserPlatformMembership",
]
