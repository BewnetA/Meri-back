import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.services.ai.orchestrator import ai_orchestrator

logger = logging.getLogger(__name__)


class JobAssistantService:
    @classmethod
    async def process_job_query(
        cls,
        db: AsyncSession,
        platform_id: str,
        question: str,
        job_id: str | None = None,
        language: str = "en",
        page_context: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        """
        Answers job-related queries, compares requirements, analyzes qualifications,
        and provides grounded guidance without overpromising employer outcomes.
        """
        job_info: dict[str, Any] = {}

        # 1. Check if job_id was passed and fetch verified record from database
        if job_id:
            result = await db.execute(
                select(Job).where(Job.id == job_id, Job.platform_id == platform_id)
            )
            job_obj = result.scalar_one_or_none()
            if job_obj:
                job_info = {
                    "title": job_obj.title,
                    "company": job_obj.company,
                    "location": job_obj.location,
                    "description": job_obj.description,
                    "requirements": job_obj.requirements,
                    "skills": job_obj.skills,
                    "application_instructions": job_obj.application_instructions,
                }

        # 2. If not found in DB or if plugin passed live page context, merge safely
        if not job_info and page_context and isinstance(page_context, dict):
            content = page_context.get("content", {})
            if isinstance(content, dict):
                job_info = {
                    "title": page_context.get("title", content.get("title", "Job Posting")),
                    "company": content.get("company", "Employer"),
                    "location": content.get("location", "Not specified"),
                    "description": content.get("description", ""),
                    "requirements": content.get("requirements", []),
                    "skills": content.get("skills", []),
                    "application_instructions": content.get("application_instructions", ""),
                }

        context_list = []
        if job_info:
            reqs_str = (
                ", ".join(job_info.get("requirements", []))
                if isinstance(job_info.get("requirements"), list)
                else str(job_info.get("requirements", ""))
            )
            skills_str = (
                ", ".join(job_info.get("skills", []))
                if isinstance(job_info.get("skills"), list)
                else str(job_info.get("skills", ""))
            )
            job_summary = (
                f"Position: {job_info.get('title')}\n"
                f"Company: {job_info.get('company')}\n"
                f"Location: {job_info.get('location')}\n"
                f"Description: {job_info.get('description')}\n"
                f"Key Requirements: {reqs_str}\n"
                f"Required Skills: {skills_str}\n"
                f"Application Instructions: {job_info.get('application_instructions')}"
            )
            context_list.append(
                {
                    "title": f"Verified Job Posting: {job_info.get('title')}",
                    "content": job_summary,
                }
            )

        system_instruction = (
            "You are an empathetic, practical career coach for BridgeMate. "
            "Guidelines: "
            "1. Explain job descriptions and break down complex technical requirements. "
            "2. If the learner asks 'Am I qualified?', compare their stated skills with the job requirements, "
            "   highlight strengths, and kindly point out gaps they can improve. "
            "3. NEVER predict or claim to know whether an employer will hire or accept an applicant. "
            "4. Remind learners that accommodations can be requested confidentially."
        )

        response_text, provider = await ai_orchestrator.generate_response(
            question=question,
            context=context_list,
            language=language,
            system_instruction=system_instruction,
        )

        return response_text, provider


job_assistant_service = JobAssistantService()
