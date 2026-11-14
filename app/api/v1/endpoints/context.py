from fastapi import APIRouter, Depends

from app.core.dependencies import get_session_context
from app.schemas.context import (
    ContextAnalyzeRequest,
    ContextValidationResult,
    PageTypeInfo,
)
from app.services.context_engine import PAGE_TYPE_SPECS, context_engine

router = APIRouter()


@router.post("/analyze")
async def analyze_page_context(
    payload: ContextAnalyzeRequest,
    session: dict = Depends(get_session_context),
):
    """
    Analyzes submitted page context, sanitizes sensitive data,
    detects page type, and returns suggested contextual quick actions.
    """
    validation = context_engine.validate_and_sanitize(payload.context)
    suggested_actions = context_engine.get_suggested_actions(validation.page_type)

    return {
        "is_valid": validation.is_valid,
        "page_type": validation.page_type,
        "detected_entities": validation.detected_entities,
        "suggested_quick_actions": suggested_actions,
        "sanitized_summary": validation.sanitized_content,
        "warnings": validation.warnings,
    }


@router.post("/validate", response_model=ContextValidationResult)
async def validate_page_context(
    payload: ContextAnalyzeRequest,
    session: dict = Depends(get_session_context),
):
    """Sanitizes raw context, scrubs PII, scripts, and passwords."""
    return context_engine.validate_and_sanitize(payload.context)


@router.get("/page-types", response_model=list[PageTypeInfo])
async def list_supported_page_types():
    """Lists supported page types, their expected extracted fields, and quick action templates."""
    return list(PAGE_TYPE_SPECS.values())
