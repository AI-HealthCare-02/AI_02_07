from fastapi import APIRouter

api_v1_router = APIRouter(prefix="/api/v1")

from app.apis.v1.guide import router as guide_router
api_v1_router.include_router(guide_router)