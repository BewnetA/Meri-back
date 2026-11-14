from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.common import IntegrationEvent
from app.models.platform import Platform
from app.schemas.platform import (
    BrandingConfig,
    FeaturesConfig,
    PluginConfigResponse,
    ThemeConfig,
)

router = APIRouter()


@router.get("/config/{public_key}", response_model=PluginConfigResponse)
async def get_plugin_configuration(
    public_key: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieved by the embeddable plugin script when initializing on the host website.
    Dynamically returns platform branding, colors, language, and feature flags.
    Matches Frontend Specification Section 3 & 4.
    """
    stmt = (
        select(Platform)
        .options(selectinload(Platform.configuration))
        .where(Platform.public_key == public_key, Platform.enabled == True)
    )
    result = await db.execute(stmt)
    platform = result.scalar_one_or_none()

    if not platform:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Platform with specified public key does not exist or is disabled",
        )

    # Log integration event
    event = IntegrationEvent(
        platform_id=platform.id,
        event_type="config_retrieved",
        payload={"public_key": public_key},
    )
    db.add(event)
    await db.commit()

    config = platform.configuration
    if not config:
        # Default configuration
        return PluginConfigResponse(
            platform_name=platform.name,
            theme=ThemeConfig(),
            branding=BrandingConfig(),
            welcome_message="Hello! I'm your BridgeMate AI learning and career assistant. How can I help you today?",
            language="en",
            position="bottom-right",
            size="medium",
            features=FeaturesConfig(),
            context_extraction_rules={},
            public_key=platform.public_key,
        )

    return PluginConfigResponse(
        platform_name=config.platform_name or platform.name,
        theme=ThemeConfig(**config.theme),
        branding=BrandingConfig(**config.branding),
        welcome_message=config.welcome_message,
        language=config.language,
        position=config.position,
        size=config.size,
        features=FeaturesConfig(**config.features),
        context_extraction_rules=config.context_extraction_rules or {},
        public_key=platform.public_key,
    )
