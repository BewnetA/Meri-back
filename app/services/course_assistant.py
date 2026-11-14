import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Document, DocumentChunk
from app.schemas.chat import CitationItem
from app.services.ai.embeddings import get_embedding
from app.services.ai.orchestrator import ai_orchestrator

logger = logging.getLogger(__name__)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = sum(a * a for a in v1) ** 0.5
    mag2 = sum(b * b for b in v2) ** 0.5
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


class CourseAssistantService:
    @classmethod
    async def retrieve_relevant_chunks(
        cls,
        db: AsyncSession,
        platform_id: str,
        query: str,
        course_id: str | None = None,
        top_k: int = 4,
    ) -> list[tuple[DocumentChunk, str, float]]:
        """
        Retrieves top-k relevant course chunks for the platform and authorized course.
        Returns list of (DocumentChunk, document_title, score).
        """
        query_vector = await get_embedding(query)

        # Build query
        stmt = (
            select(DocumentChunk, Document.title)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.platform_id == platform_id)
        )
        if course_id:
            stmt = stmt.where(DocumentChunk.course_id == course_id)

        result = await db.execute(stmt)
        rows = result.all()

        scored_chunks = []
        for chunk, doc_title in rows:
            chunk_vec = chunk.embedding
            score = 0.0
            if chunk_vec and isinstance(chunk_vec, list):
                score = cosine_similarity(query_vector, chunk_vec)
            else:
                # Text keyword overlap fallback
                words = set(query.lower().split())
                c_words = set(chunk.content.lower().split())
                overlap = len(words.intersection(c_words))
                score = overlap / max(1, len(words))

            scored_chunks.append((chunk, doc_title, score))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[2], reverse=True)
        return scored_chunks[:top_k]

    @classmethod
    async def answer_course_question(
        cls,
        db: AsyncSession,
        platform_id: str,
        question: str,
        course_id: str | None = None,
        language: str = "en",
        page_context: dict[str, Any] | None = None,
    ) -> tuple[str, str, list[CitationItem]]:
        """
        Answers course inquiry using grounded RAG and institution document records.
        Returns (response_text, provider_used, citations_list).
        """
        # Retrieve chunks
        relevant_items = await cls.retrieve_relevant_chunks(
            db=db,
            platform_id=platform_id,
            query=question,
            course_id=course_id,
            top_k=4,
        )

        context_list = []
        citations = []

        # If page_context contains live lesson text from frontend, include it with priority
        if page_context and isinstance(page_context, dict):
            content_desc = page_context.get("content", "")
            if content_desc:
                context_list.append(
                    {
                        "title": page_context.get("title", "Active Lesson Page"),
                        "content": str(content_desc),
                        "page_number": None,
                    }
                )

        for chunk, doc_title, score in relevant_items:
            context_list.append(
                {
                    "title": doc_title,
                    "content": chunk.content,
                    "page_number": chunk.page_number,
                    "section": chunk.section_title,
                }
            )
            citations.append(
                CitationItem(
                    document_title=doc_title,
                    page_number=chunk.page_number,
                    section_or_lesson=chunk.section_title or "Course Content",
                    source_reference=f"{doc_title} (Sec: {chunk.section_title or 'General'})",
                    snippet=chunk.content[:200] + ("..." if len(chunk.content) > 200 else ""),
                )
            )

        system_instruction = (
            "Focus on explaining concepts clearly, resolving doubts, and citing the provided lesson materials. "
            "If asked to summarize, provide a concise, structured bulleted summary. "
            "Explain difficult terminology in plain terms suitable for students."
        )

        response_text, provider = await ai_orchestrator.generate_response(
            question=question,
            context=context_list,
            language=language,
            system_instruction=system_instruction,
        )

        return response_text, provider, citations


course_assistant_service = CourseAssistantService()
