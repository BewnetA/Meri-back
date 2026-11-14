import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )

    async def generate(
        self,
        question: str,
        context: list[dict[str, Any]],
        language: str = "en",
        system_instruction: str | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("Gemini API key is not configured.")

        # Build prompt with grounded context
        lang_prompt = (
            "You MUST respond in Amharic (አማርኛ) using clear and accessible language."
            if language == "am"
            else "You MUST respond in clear English."
        )

        formatted_context = ""
        if context:
            formatted_context = "--- GROUNDED CONTEXT FROM INSTITUTION ---\n"
            for i, c in enumerate(context, 1):
                title = c.get("title", f"Source {i}")
                content = c.get("content", "")
                page = c.get("page_number")
                page_str = f" (Page {page})" if page else ""
                formatted_context += f"[{i}] {title}{page_str}:\n{content}\n\n"
            formatted_context += "--- END CONTEXT ---\n"

        default_sys = (
            "You are BridgeMate, an AI learning and career assistant embedded in an educational/job platform. "
            "You are helpful, empathetic, highly accessible, and grounded. "
            "Base your answers strictly on the provided grounded context whenever available. "
            "If the context does not contain enough information to answer reliably, clearly state that you do not know. "
            "Never invent facts or claim to know employer hiring decisions. "
            f"{lang_prompt}"
        )
        sys_text = f"{default_sys}\n{system_instruction or ''}"

        full_prompt = f"{formatted_context}\nLearner's Question: {question}\n\nAssistant Response:"

        payload = {
            "system_instruction": {"parts": [{"text": sys_text}]},
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
            },
        }

        url = f"{self.base_url}?key={self.api_key}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.error(f"Gemini API error: {resp.status_code} - {resp.text}")
                raise RuntimeError(f"Gemini API returned status {resp.status_code}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()

            raise RuntimeError("Gemini returned empty candidate response")
