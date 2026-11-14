import logging
import re
from typing import Any

from app.schemas.context import (
    ContextValidationResult,
    PageContextPayload,
    PageTypeInfo,
)

logger = logging.getLogger(__name__)

# Sensitive keywords to scrub
SCRUB_PATTERNS = [
    r"password\s*[:=]\s*\S+",
    r"token\s*[:=]\s*\S+",
    r"bearer\s+[A-Za-z0-9_\-\.]+",
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Emails in arbitrary text
    r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b",  # Phone numbers
    r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b",  # Credit cards
]

PAGE_TYPE_SPECS = {
    "course": PageTypeInfo(
        type_name="course",
        description="Course syllabus, description, and instructor overview",
        extracted_fields=["course_name", "description", "instructor", "modules"],
        suggested_quick_actions=[
            "Explain this course syllabus",
            "What are the prerequisites?",
            "Summarize the course goals",
            "Ask a question to tutor",
        ],
    ),
    "lesson": PageTypeInfo(
        type_name="lesson",
        description="Active lesson, learning content, and topic notes",
        extracted_fields=["lesson_title", "learning_content", "headings", "key_terms"],
        suggested_quick_actions=[
            "Explain this lesson",
            "Summarize this content",
            "Explain difficult terms",
            "Test my understanding",
        ],
    ),
    "assignment": PageTypeInfo(
        type_name="assignment",
        description="Assignment specifications, rubrics, and deadlines",
        extracted_fields=["instructions", "requirements", "deadline", "rubric"],
        suggested_quick_actions=[
            "Explain the instructions",
            "Break down the requirements",
            "Explain difficult concepts",
            "What is the expected output format?",
        ],
    ),
    "job": PageTypeInfo(
        type_name="job",
        description="Job posting, required skills, and qualification details",
        extracted_fields=["position", "company", "description", "skills", "requirements"],
        suggested_quick_actions=[
            "Explain this job",
            "Am I qualified for this position?",
            "Prepare me for the interview",
            "Start a mock interview",
            "Request interview accommodations",
        ],
    ),
    "application": PageTypeInfo(
        type_name="application",
        description="Job or course application workflow instructions",
        extracted_fields=["application_steps", "eligibility", "documents_needed"],
        suggested_quick_actions=[
            "Explain the application steps",
            "What documents are needed?",
            "How should I format my submission?",
        ],
    ),
    "general": PageTypeInfo(
        type_name="general",
        description="General platform content and informational pages",
        extracted_fields=["title", "url", "main_visible_text"],
        suggested_quick_actions=[
            "Summarize this page",
            "Where do I find my courses?",
            "Connect with support",
        ],
    ),
}


class ContextEngine:
    @staticmethod
    def sanitize_text(text: str) -> str:
        """Strip scripts, HTML tags, and private credentials."""
        if not text:
            return ""
        # Remove script and style tags
        cleaned = re.sub(
            r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        # Remove general HTML tags
        cleaned = re.sub(r"<[^>]+>", " ", cleaned)
        # Scrub sensitive patterns (passwords, tokens, credit cards)
        for pattern in SCRUB_PATTERNS:
            cleaned = re.sub(pattern, "[REDACTED_SENSITIVE_DATA]", cleaned, flags=re.IGNORECASE)
        # Collapse multiple spaces
        return re.sub(r"\s+", " ", cleaned).strip()

    @staticmethod
    def sanitize_dict(data: Any) -> Any:
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                # Drop obvious private or tracking fields
                if any(
                    bad in k.lower()
                    for bad in ["password", "secret", "cvv", "credit_card", "ssn", "auth_token"]
                ):
                    continue
                sanitized[k] = ContextEngine.sanitize_dict(v)
            return sanitized
        elif isinstance(data, list):
            return [ContextEngine.sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return ContextEngine.sanitize_text(data)
        return data

    @classmethod
    def validate_and_sanitize(
        cls,
        context: PageContextPayload | None,
        platform_domain: str | None = None,
    ) -> ContextValidationResult:
        if not context:
            return ContextValidationResult(
                is_valid=True,
                page_type="general",
                sanitized_content={},
                detected_entities={},
                warnings=["No context provided"],
            )

        warnings = []
        raw_type = context.page_type.lower() if context.page_type else "general"
        normalized_type = raw_type if raw_type in PAGE_TYPE_SPECS else "general"

        if raw_type not in PAGE_TYPE_SPECS:
            warnings.append(f"Unrecognized page type '{raw_type}', defaulted to 'general'")

        # Validate URL origin if domain provided
        if platform_domain and context.url:
            if context.url.startswith("http"):
                from urllib.parse import urlparse

                parsed = urlparse(context.url)
                if (
                    parsed.netloc
                    and platform_domain not in parsed.netloc
                    and parsed.netloc not in ["localhost", "127.0.0.1"]
                ):
                    warnings.append(
                        f"URL origin '{parsed.netloc}' differs from registered platform '{platform_domain}'"
                    )

        # Sanitize payload content
        sanitized_content = cls.sanitize_dict(context.content)
        if isinstance(sanitized_content, str):
            sanitized_content = {"text": sanitized_content}

        # Detect key entities (skills, course codes, deadlines)
        detected_entities = {}
        if normalized_type == "job":
            reqs = sanitized_content.get("requirements", [])
            skills = sanitized_content.get("skills", [])
            detected_entities["skills"] = list(
                set(
                    (reqs if isinstance(reqs, list) else [])
                    + (skills if isinstance(skills, list) else [])
                )
            )
            detected_entities["company"] = sanitized_content.get("company", "")
        elif normalized_type in ["course", "lesson"]:
            detected_entities["course_title"] = context.title
            detected_entities["lesson_title"] = sanitized_content.get("lesson_title", context.title)

        return ContextValidationResult(
            is_valid=True,
            page_type=normalized_type,
            sanitized_content=sanitized_content,
            detected_entities=detected_entities,
            warnings=warnings,
        )

    @staticmethod
    def get_suggested_actions(page_type: str) -> list[str]:
        spec = PAGE_TYPE_SPECS.get(page_type.lower())
        if spec:
            return spec.suggested_quick_actions
        return PAGE_TYPE_SPECS["general"].suggested_quick_actions


context_engine = ContextEngine()
