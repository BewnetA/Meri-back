from fastapi import APIRouter

from app.api.v1.endpoints import (
    analytics,
    auth,
    chat,
    context,
    jobs,
    knowledge,
    platforms,
    plugin,
    support,
    telegram,
)

api_router = APIRouter()

api_router.include_router(plugin.router, prefix="/plugin", tags=["Plugin Configuration"])
api_router.include_router(platforms.router, prefix="/platforms", tags=["Platforms & Integrations"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Identity"])
api_router.include_router(context.router, prefix="/context", tags=["Context & Page Processing"])
api_router.include_router(knowledge.router, tags=["Courses & Knowledge Base"])
api_router.include_router(chat.router, prefix="/chat", tags=["Context-Aware Chat"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Career Gateway & Jobs"])
api_router.include_router(support.router, prefix="/support", tags=["Human Support"])
api_router.include_router(telegram.router, prefix="/telegram", tags=["Telegram Integration"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
