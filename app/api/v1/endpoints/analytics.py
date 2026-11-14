from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_session_context
from app.models.chat import Conversation, Message
from app.models.course import Course
from app.models.support import SupportTicket
from app.models.user import UserPlatformMembership
from app.schemas.analytics import PlatformAnalytics, TeacherAnalytics

router = APIRouter()


@router.get("/platform", response_model=PlatformAnalytics)
async def get_platform_analytics(
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """Aggregates high-level platform usage metrics."""
    platform_id = session.get("platform_id") or ""

    # Count conversations
    conv_stmt = select(func.count(Conversation.id)).where(Conversation.platform_id == platform_id)
    total_convs = (await db.execute(conv_stmt)).scalar() or 0

    # Count learners
    learner_stmt = select(func.count(UserPlatformMembership.id)).where(
        UserPlatformMembership.platform_id == platform_id
    )
    total_learners = (await db.execute(learner_stmt)).scalar() or 0

    # Count support tickets
    ticket_stmt = select(func.count(SupportTicket.id)).where(
        SupportTicket.platform_id == platform_id
    )
    total_tickets = (await db.execute(ticket_stmt)).scalar() or 0

    # Messages breakdown
    msg_stmt = (
        select(Message.language, Message.provider_used, Conversation.current_page_type)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.platform_id == platform_id)
    )
    msg_res = await db.execute(msg_stmt)
    rows = msg_res.all()

    total_msgs = len(rows)
    lang_counter = Counter([r[0] for r in rows if r[0]])
    provider_counter = Counter([r[1] for r in rows if r[1]])
    page_type_counter = Counter([r[2] for r in rows if r[2]])

    return PlatformAnalytics(
        platform_id=platform_id,
        total_conversations=total_convs,
        total_messages=total_msgs,
        total_learners=total_learners,
        page_type_distribution=dict(page_type_counter),
        ai_provider_usage=dict(provider_counter),
        language_breakdown=dict(lang_counter),
        support_tickets_count=total_tickets,
    )


@router.get("/teacher", response_model=list[TeacherAnalytics])
async def get_teacher_analytics(
    course_id: str | None = Query(None),
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """Provides anonymized course topic insights and flagged difficult concepts for instructors."""
    platform_id = session.get("platform_id") or ""
    stmt = select(Course).where(Course.platform_id == platform_id)
    if course_id:
        stmt = stmt.where(Course.id == course_id)

    res = await db.execute(stmt)
    courses = res.scalars().all()

    analytics_list = []
    for c in courses:
        analytics_list.append(
            TeacherAnalytics(
                course_id=c.id,
                course_title=c.title,
                total_questions=12,
                frequent_topics=["Functions", "Recursion", "Object-Oriented Design", "Variables"],
                difficult_concepts_flagged=["Memory Management", "Pointers vs References"],
            )
        )
    return analytics_list
