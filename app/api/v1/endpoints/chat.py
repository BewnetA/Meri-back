import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.dependencies import get_session_context
from app.models.chat import Conversation, Message
from app.models.platform import Platform
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    CitationItem,
    ConversationDetailResponse,
)
from app.services.ai.orchestrator import ai_orchestrator
from app.services.context_engine import context_engine
from app.services.course_assistant import course_assistant_service
from app.services.interview_prep import interview_prep_service
from app.services.job_assistant import job_assistant_service
from app.services.websocket_manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    payload: ChatMessageRequest,
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Primary chat endpoint for the embeddable plugin and Telegram bot.
    Receives learner inquiry and page context, applies security scrubbing,
    routes to appropriate specialized assistant service, and returns response with citations.
    """
    platform_id = session.get("platform_id")
    user_id = session.get("user_id")

    # If no platform_id in session, lookup default platform or platform from context
    if not platform_id:
        plat_res = await db.execute(select(Platform.id).where(Platform.enabled == True).limit(1))
        platform_id = plat_res.scalar_one_or_none()
        if not platform_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No active platform found"
            )

    # If guest user (not logged in on LMS yet), associate with a persistent guest user
    if not user_id:
        guest_res = await db.execute(select(User).where(User.email == "guest@bridgemate.internal"))
        guest_user = guest_res.scalar_one_or_none()
        if not guest_user:
            guest_user = User(
                email="guest@bridgemate.internal",
                full_name="Guest Learner",
                role="learner",
                is_active=True,
            )
            db.add(guest_user)
            await db.flush()
        user_id = guest_user.id

    # 1. Sanitize & validate page context
    validation = context_engine.validate_and_sanitize(payload.context)
    page_type = validation.page_type
    sanitized_content = validation.sanitized_content

    # 2. Get or create conversation
    conversation = None
    if payload.conversation_id:
        c_stmt = select(Conversation).where(
            Conversation.id == payload.conversation_id,
            Conversation.platform_id == platform_id,
        )
        c_res = await db.execute(c_stmt)
        conversation = c_res.scalar_one_or_none()

    if not conversation:
        conversation = Conversation(
            user_id=user_id,
            platform_id=platform_id,
            session_source="web_plugin",
            title=payload.message[:50] if payload.message else "Conversation",
            current_page_type=page_type,
            current_url=payload.context.url if payload.context else None,
        )
        db.add(conversation)
        await db.flush()

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        sender="learner",
        content=payload.message,
        language=payload.language,
        page_context=sanitized_content,
    )
    db.add(user_msg)
    await db.flush()

    # 3. Route to specialized assistant service based on page_type and query intent
    q_lower = payload.message.lower()
    citations: list[CitationItem] = []
    response_text = ""
    provider_used = "offline_faq"

    # Job / Interview Context
    if page_type == "job" or any(
        kw in q_lower for kw in ["job", "interview", "qualified", "hiring"]
    ):
        if any(kw in q_lower for kw in ["mock", "interview practice", "practice interview"]):
            response_text, provider_used = await interview_prep_service.generate_practice_session(
                question=payload.message,
                job_details=sanitized_content,
                language=payload.language,
            )
        else:
            response_text, provider_used = await job_assistant_service.process_job_query(
                db=db,
                platform_id=platform_id,
                question=payload.message,
                job_id=payload.context.job_id if payload.context else None,
                language=payload.language,
                page_context=payload.context.model_dump() if payload.context else None,
            )

    # Course / Lesson / Assignment Context
    elif (
        page_type in ["course", "lesson", "assignment"]
        or payload.context
        and payload.context.course_id
    ):
        course_id = payload.context.course_id if payload.context else None
        (
            response_text,
            provider_used,
            citations,
        ) = await course_assistant_service.answer_course_question(
            db=db,
            platform_id=platform_id,
            question=payload.message,
            course_id=course_id,
            language=payload.language,
            page_context=payload.context.model_dump() if payload.context else None,
        )

    # General Fallback Context
    else:
        context_items = []
        if sanitized_content:
            context_items.append(
                {
                    "title": payload.context.title if payload.context else "Page Content",
                    "content": str(sanitized_content),
                }
            )
        response_text, provider_used = await ai_orchestrator.generate_response(
            question=payload.message,
            context=context_items,
            language=payload.language,
        )

    # Save assistant response
    assistant_msg = Message(
        conversation_id=conversation.id,
        sender="assistant",
        content=response_text,
        language=payload.language,
        citations=[c.model_dump() for c in citations] if citations else None,
        provider_used=provider_used,
    )
    db.add(assistant_msg)
    await db.commit()

    suggested_actions = context_engine.get_suggested_actions(page_type)

    # Broadcast on WebSocket if active
    await ws_manager.broadcast(
        conversation.id,
        {
            "type": "new_message",
            "message_id": assistant_msg.id,
            "sender": "assistant",
            "content": response_text,
            "citations": [c.model_dump() for c in citations],
            "provider_used": provider_used,
        },
    )

    return ChatMessageResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        response=response_text,
        language=payload.language,
        provider_used=provider_used,
        citations=citations,
        suggested_actions=suggested_actions,
        timestamp=assistant_msg.created_at,
    )


@router.get("/conversations", response_model=list[ConversationDetailResponse])
async def list_conversations(
    session: dict = Depends(get_session_context),
    db: AsyncSession = Depends(get_db),
):
    user_id = session.get("user_id")
    platform_id = session.get("platform_id")

    stmt = select(Conversation).options(selectinload(Conversation.messages))
    if user_id:
        stmt = stmt.where(Conversation.user_id == user_id)
    if platform_id:
        stmt = stmt.where(Conversation.platform_id == platform_id)

    stmt = stmt.order_by(Conversation.created_at.desc()).limit(20)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/conversations/{id}", response_model=ConversationDetailResponse)
async def get_conversation_history(
    id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == id)
    )
    res = await db.execute(stmt)
    conv = res.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv


@router.websocket("/ws/{conversation_id}")
async def chat_websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str,
):
    """Real-time bidirectional WebSocket channel for conversation streaming & live updates."""
    await ws_manager.connect(conversation_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming ping / messages
            try:
                parsed = json.loads(data)
                if parsed.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(conversation_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(conversation_id, websocket)
