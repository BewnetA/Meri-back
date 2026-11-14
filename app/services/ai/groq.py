import logging
from typing import Any

import httpx

from app.core.config import settings
from app.services.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class GroqProvider(BaseAIProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(
        self,
        question: str,
        context: list[dict[str, Any]],
        language: str = "en",
        system_instruction: str | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("Groq API key is not configured.")

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

        system_msg = (
            "You are BridgeMate, an AI learning and career assistant embedded in an educational/job platform. "
            "You are helpful, empathetic, and grounded. "
            "Base your answers strictly on the provided grounded context. "
            "If the context does not contain enough information to answer reliably, state that clearly. "
            "Never invent facts or claim to know employer hiring decisions. "
            f"{lang_prompt}\n{system_instruction or ''}"
        )

        user_msg = f"{formatted_context}\nLearner's Question: {question}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
            "max_tokens": 1024,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(self.base_url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"Groq API error: {resp.status_code} - {resp.text}")
                raise RuntimeError(f"Groq API returned status {resp.status_code}")

            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()

            raise RuntimeError("Groq returned empty choices")
