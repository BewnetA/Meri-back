import logging
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.job import Job
from app.models.platform import Platform
from app.models.user import TelegramAccount, User, UserPhone, UserPlatformMembership
from app.services.course_assistant import course_assistant_service

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Normalize phone numbers to international standard (e.g. +251...)."""
    cleaned = re.sub(r"[^\d+]", "", phone)
    if not cleaned.startswith("+") and cleaned.startswith("0"):
        # Assume Ethiopia (+251) if starting with 09
        cleaned = "+251" + cleaned[1:]
    elif not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    return cleaned


class TelegramService:
    @staticmethod
    async def send_telegram_message(
        chat_id: str,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram Bot Token is not configured. Message not sent.")
            return False

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            return False

    @classmethod
    async def handle_start(cls, chat_id: str, first_name: str) -> None:
        """Prompts learner to verify their phone number via contact sharing."""
        welcome_text = (
            f"👋 Welcome to <b>BridgeMate</b>, {first_name}!\n\n"
            "I am your unified AI learning and career assistant. "
            "To connect your verified student or job-seeker account, "
            "please share your phone number securely using the button below."
        )
        keyboard = {
            "keyboard": [[{"text": "📱 Share Contact to Verify Account", "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
        await cls.send_telegram_message(chat_id, welcome_text, reply_markup=keyboard)

    @classmethod
    async def verify_contact_and_link(
        cls,
        db: AsyncSession,
        chat_id: str,
        tg_user_id: str,
        phone_number: str,
        first_name: str | None = None,
    ) -> str:
        """
        Matches shared contact against trusted platform learner phone records.
        Links telegram account and prompts for platform selection if multiple exist.
        """
        normalized = normalize_phone(phone_number)

        # 1. Lookup phone record
        stmt = (
            select(UserPhone, User)
            .join(User, UserPhone.user_id == User.id)
            .where(UserPhone.phone_number == normalized)
        )
        res = await db.execute(stmt)
        record = res.first()

        if not record:
            return (
                "❌ We could not find a registered learner account matching this phone number.\n\n"
                "Please verify that you registered on your learning platform with this number, "
                "or contact your platform administrator."
            )

        phone_obj, user = record

        # 2. Find learner's linked platform memberships
        mem_stmt = (
            select(UserPlatformMembership, Platform)
            .join(Platform, UserPlatformMembership.platform_id == Platform.id)
            .where(UserPlatformMembership.user_id == user.id, Platform.enabled == True)
        )
        mem_res = await db.execute(mem_stmt)
        memberships = mem_res.all()

        if not memberships:
            return "⚠️ Your phone number was verified, but you have no active platform enrollments."

        # 3. Create or update TelegramAccount link
        tg_stmt = select(TelegramAccount).where(TelegramAccount.telegram_chat_id == str(chat_id))
        tg_res = await db.execute(tg_stmt)
        tg_acc = tg_res.scalar_one_or_none()

        default_platform_id = memberships[0][1].id

        if not tg_acc:
            tg_acc = TelegramAccount(
                user_id=user.id,
                telegram_chat_id=str(chat_id),
                telegram_username=first_name,
                phone_number=normalized,
                active_platform_id=default_platform_id,
                is_verified=True,
            )
            db.add(tg_acc)
        else:
            tg_acc.user_id = user.id
            tg_acc.phone_number = normalized
            tg_acc.active_platform_id = default_platform_id
            tg_acc.is_verified = True

        await db.commit()

        # If multiple platforms, show selection buttons
        if len(memberships) > 1:
            inline_buttons = [
                [{"text": f"🏫 {plat.name}", "callback_data": f"select_platform:{plat.id}"}]
                for _, plat in memberships
            ]
            msg = (
                f"✅ <b>Account Verified!</b> Hello {user.full_name}.\n\n"
                f"You have access to multiple platforms. Please choose your active platform:"
            )
            await cls.send_telegram_message(
                chat_id,
                msg,
                reply_markup={"inline_keyboard": inline_buttons},
            )
            return "Verified with multiple platforms."

        platform_name = memberships[0][1].name
        success_msg = (
            f"✅ <b>Account Successfully Linked!</b>\n\n"
            f"👤 Learner: <b>{user.full_name}</b>\n"
            f"🏫 Active Platform: <b>{platform_name}</b>\n\n"
            "You can now:\n"
            "• Ask course questions\n"
            "• Type /jobs to browse current vacancies\n"
            "• Type /help to view commands"
        )
        remove_kb = {"remove_keyboard": True}
        await cls.send_telegram_message(chat_id, success_msg, reply_markup=remove_kb)
        return "Account successfully linked."

    @classmethod
    async def process_user_query(
        cls,
        db: AsyncSession,
        chat_id: str,
        text: str,
    ) -> None:
        """Processes inquiries from verified Telegram users using shared backend services."""
        # Find active telegram link
        tg_stmt = select(TelegramAccount).where(
            TelegramAccount.telegram_chat_id == str(chat_id),
            TelegramAccount.is_verified == True,
        )
        res = await db.execute(tg_stmt)
        tg_acc = res.scalar_one_or_none()

        if not tg_acc or not tg_acc.active_platform_id:
            await cls.send_telegram_message(
                chat_id,
                "⚠️ Please share your contact or type /start to link your learner account before asking questions.",
            )
            return

        # Check for commands
        cmd = text.strip().lower()
        if cmd == "/jobs":
            # List platform jobs
            job_stmt = (
                select(Job)
                .where(
                    Job.platform_id == tg_acc.active_platform_id,
                    Job.is_active == True,
                )
                .limit(5)
            )
            job_res = await db.execute(job_stmt)
            jobs = job_res.scalars().all()
            if not jobs:
                await cls.send_telegram_message(
                    chat_id, "No active job listings found for your platform right now."
                )
                return

            job_list_text = "<b>💼 Available Job Openings:</b>\n\n"
            for j in jobs:
                job_list_text += (
                    f"📌 <b>{j.title}</b> at {j.company}\n"
                    f"📍 {j.location}\n"
                    f"Required: {', '.join(j.skills[:4])}\n\n"
                )
            await cls.send_telegram_message(chat_id, job_list_text)
            return

        # Course / General AI Assistant response
        # Query course assistant service
        resp_text, provider, citations = await course_assistant_service.answer_course_question(
            db=db,
            platform_id=tg_acc.active_platform_id,
            question=text,
            language="en",
        )

        citation_text = ""
        if citations:
            citation_text = "\n\n<b>📚 Sources:</b>\n" + "\n".join(
                [f"• {c.document_title}" for c in citations[:2]]
            )

        final_msg = f"{resp_text}{citation_text}\n\n<i>(Answered via {provider})</i>"
        await cls.send_telegram_message(chat_id, final_msg)


telegram_service = TelegramService()
