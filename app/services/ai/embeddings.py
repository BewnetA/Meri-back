import hashlib
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_fallback_embedding(text: str, dim: int = 768) -> list[float]:
    """
    Deterministic pseudo-embedding fallback of fixed dimension (768).
    Ensures vector storage and similarity math operate consistently
    even when running offline without an API key.
    """
    vector = [0.0] * dim
    words = text.lower().split()
    if not words:
        return vector

    for i, word in enumerate(words):
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        slot = h % dim
        vector[slot] += 1.0 / (1.0 + (i % 5))

    # Normalize vector to unit length
    magnitude = sum(x * x for x in vector) ** 0.5
    if magnitude > 0:
        vector = [x / magnitude for x in vector]
    return vector


async def get_embedding(text: str) -> list[float]:
    """
    Get 768-dimensional embedding from Gemini or fallback to deterministic embedding.
    """
    if settings.GEMINI_API_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.EMBEDDING_MODEL}:embedContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "model": f"models/{settings.EMBEDDING_MODEL}",
                "content": {"parts": [{"text": text}]},
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    values = data.get("embedding", {}).get("values", [])
                    if len(values) == 768:
                        return values
                    elif len(values) > 0:
                        # Pad or truncate to 768
                        if len(values) < 768:
                            return values + [0.0] * (768 - len(values))
                        return values[:768]
        except Exception as e:
            logger.warning(f"Failed to generate Gemini embedding, using fallback: {e}")

    return generate_fallback_embedding(text, 768)
