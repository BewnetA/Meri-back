import logging
from typing import Any

from app.services.ai.orchestrator import ai_orchestrator

logger = logging.getLogger(__name__)


class InterviewPreparationService:
    @classmethod
    async def generate_practice_session(
        cls,
        question: str,
        job_details: dict[str, Any],
        language: str = "en",
    ) -> tuple[str, str]:
        """
        Conducts mock interview rounds and evaluates candidate practice responses.
        Clearly labels all prompts as practice simulations, never real employer predictions.
        """
        context_list = []
        if job_details:
            context_list.append(
                {
                    "title": f"Practice Simulation for {job_details.get('title', 'Role')}",
                    "content": f"Role: {job_details.get('title')}\n"
                    f"Requirements: {job_details.get('requirements')}\n"
                    f"Skills: {job_details.get('skills')}",
                }
            )

        system_instruction = (
            "You are conducting a friendly, constructive practice mock interview. "
            "IMPORTANT: All questions are for practice and simulation only; "
            "never claim they predict the actual employer's questions. "
            "If the learner is answering a practice question, provide supportive feedback using the STAR format "
            "(Situation, Task, Action, Result) and suggest areas of improvement. "
            "If asked for mock questions, offer 3 targeted, realistic practice questions."
        )

        response_text, provider = await ai_orchestrator.generate_response(
            question=question,
            context=context_list,
            language=language,
            system_instruction=system_instruction,
        )

        return response_text, provider


interview_prep_service = InterviewPreparationService()
