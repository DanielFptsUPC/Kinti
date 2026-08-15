from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auth,
    care_team,
    companion,
    family,
    knowledge,
    notifications,
    operations,
    sync,
    voice,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(family.router)
api_router.include_router(care_team.router)
api_router.include_router(operations.router)
api_router.include_router(notifications.router)
api_router.include_router(companion.router)
api_router.include_router(assistant.router)
api_router.include_router(knowledge.router)
api_router.include_router(sync.router)
api_router.include_router(voice.router)
