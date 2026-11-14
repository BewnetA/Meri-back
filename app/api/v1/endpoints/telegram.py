import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.services.telegram_service import telegram_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        None, alias="X-Telegram-Bot-Api-Secret-Token"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Receives incoming updates from Telegram webhook.
    Enforces webhook secret verification if configured.
    """
    if settings.TELEGRAM_WEBHOOK_SECRET and x_telegram_bot_api_secret_token:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret token"
            )

    body = await request.json()
    logger.info(f"Incoming Telegram webhook: {body}")

    # Handle message update
    if "message" in body:
        msg = body["message"]
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id"))
        from_user = msg.get("from", {})
        first_name = from_user.get("first_name", "Learner")

        # Check if contact shared
        if "contact" in msg:
            contact = msg["contact"]
            phone_num = contact.get("phone_number", "")
            tg_uid = str(contact.get("user_id", from_user.get("id")))

            await telegram_service.verify_contact_and_link(
                db=db,
                chat_id=chat_id,
                tg_user_id=tg_uid,
                phone_number=phone_num,
                first_name=first_name,
            )
            return {"status": "ok"}

        # Check if text command or message
        text = msg.get("text", "")
        if text.startswith("/start"):
            await telegram_service.handle_start(chat_id, first_name)
            return {"status": "ok"}

        if text:
            await telegram_service.process_user_query(db, chat_id, text)
            return {"status": "ok"}

    # Handle callback query (e.g. platform selection button clicks)
    if "callback_query" in body:
        cb = body["callback_query"]
        cb_data = cb.get("data", "")
        chat_id = str(cb.get("message", {}).get("chat", {}).get("id"))
        if cb_data.startswith("select_platform:"):
            platform_id = cb_data.split(":", 1)[1]
            from app.api.v1.endpoints.auth import select_telegram_platform
            from app.schemas.auth import TelegramSelectPlatformRequest

            try:
                await select_telegram_platform(
                    TelegramSelectPlatformRequest(
                        telegram_chat_id=chat_id, platform_id=platform_id
                    ),
                    db=db,
                )
                await telegram_service.send_telegram_message(
                    chat_id,
                    "✅ Active platform updated! You can now ask questions about your courses.",
                )
            except Exception as e:
                logger.error(f"Error selecting platform via Telegram callback: {e}")

        return {"status": "ok"}

    return {"status": "ignored"}


@router.post("/link")
async def telegram_link(payload: dict[str, Any]):
    return {"status": "success", "message": "Telegram link handler ready"}


@router.post("/phone/verify")
async def telegram_phone_verify(
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    chat_id = str(payload.get("chat_id", ""))
    phone = str(payload.get("phone", ""))
    result = await telegram_service.verify_contact_and_link(
        db=db,
        chat_id=chat_id,
        tg_user_id=str(payload.get("user_id", "")),
        phone_number=phone,
        first_name=payload.get("first_name", "Learner"),
    )
    return {"status": "success", "message": result}
