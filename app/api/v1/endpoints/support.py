from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_session_context
from app.models.platform import Platform
from app.models.support import SupportMessage, SupportTicket
from app.models.user import User
from app.schemas.support import (
    SupportMessageCreate,
    SupportMessageResponse,
    SupportTicketCreate,
    SupportTicketResponse,
)
from app.services.websocket_manager import ws_manager

router = APIRouter()


@router.post("/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    payload: SupportTicketCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Submits a human assistance request.
    Respects consent rules for sharing conversation history and screen sharing flag.
    """
    user_id = session.get("user_id")
    platform_id = session.get("platform_id")

    if not user_id:
        # Create or fetch guest user
        guest_res = await db.execute(select(User).where(User.email == "guest@bridgemate.internal"))
        guest = guest_res.scalar_one_or_none()
        if not guest:
            guest = User(
                email="guest@bridgemate.internal", full_name="Guest Learner", role="learner"
            )
            db.add(guest)
            await db.flush()
        user_id = guest.id

    if not platform_id:
        plat_res = await db.execute(select(Platform.id).limit(1))
        platform_id = plat_res.scalar_one_or_none() or ""

    ticket = SupportTicket(
        platform_id=platform_id,
        learner_id=user_id,
        conversation_id=payload.conversation_id if payload.consent_share_history else None,
        subject=payload.subject,
        status="open",
        consent_share_history=payload.consent_share_history,
        screen_sharing_active=payload.screen_sharing_active,
    )
    db.add(ticket)
    await db.flush()

    if payload.initial_message:
        msg = SupportMessage(
            ticket_id=ticket.id,
            sender_id=user_id,
            sender_role="learner",
            content=payload.initial_message,
        )
        db.add(msg)

    await db.commit()
    await db.refresh(ticket)

    # Reload with messages
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.id == ticket.id)
    )
    res = await db.execute(stmt)
    return res.scalar_one()


@router.get("/tickets", response_model=list[SupportTicketResponse])
async def list_support_tickets(
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = session.get("user_id")
    platform_id = session.get("platform_id")
    role = session.get("role", "learner")

    stmt = select(SupportTicket).options(selectinload(SupportTicket.messages))
    if role in ["admin", "support_agent"]:
        if platform_id:
            stmt = stmt.where(SupportTicket.platform_id == platform_id)
    elif user_id:
        stmt = stmt.where(SupportTicket.learner_id == user_id)

    stmt = stmt.order_by(SupportTicket.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/tickets/{id}", response_model=SupportTicketResponse)
async def get_support_ticket(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.id == id)
    )
    res = await db.execute(stmt)
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found"
        )
    return ticket


@router.post("/tickets/{id}/messages", response_model=SupportMessageResponse)
async def post_support_message(
    id: str,
    payload: SupportMessageCreate,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SupportTicket).where(SupportTicket.id == id)
    res = await db.execute(stmt)
    ticket = res.scalar_one_or_none()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Support ticket not found"
        )

    user_id = session.get("user_id")
    role = session.get("role", "learner")
    sender_role = "support_agent" if role in ["admin", "support_agent"] else "learner"

    if not user_id:
        user_id = ticket.learner_id

    message = SupportMessage(
        ticket_id=ticket.id,
        sender_id=user_id,
        sender_role=sender_role,
        content=payload.content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Broadcast via websocket to ticket room
    await ws_manager.broadcast(
        f"support_{ticket.id}",
        {
            "type": "support_message",
            "message_id": message.id,
            "sender_role": sender_role,
            "content": payload.content,
        },
    )

    return message
