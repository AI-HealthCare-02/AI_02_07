# app/apis/v1/admin/system.py

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_admin
from app.dtos.admin_dto import LLMTestRequestDTO, SystemSettingsUpdateRequestDTO
from app.models.admin import AdminUser
from app.services import admin_service

router = APIRouter()


@router.get("/settings")
async def get_settings(admin: AdminUser = Depends(get_current_admin)):
    data = await admin_service.get_system_settings()
    return {"status": 200, "message": "조회 성공", "data": data.model_dump()}


@router.put("/settings")
async def update_settings(
    body: SystemSettingsUpdateRequestDTO,
    admin: AdminUser = Depends(get_current_admin),
):
    data = await admin_service.update_system_settings(body)
    return {"status": 200, "message": "설정이 저장되었습니다.", "data": data.model_dump()}


@router.post("/settings/test-llm")
async def test_llm(
    body: LLMTestRequestDTO,
    admin: AdminUser = Depends(get_current_admin),
):
    data = await admin_service.test_llm(body.apiModel, body.temperature, body.maxTokens)
    msg = "테스트 성공" if data.success else "테스트 실패"
    return {"status": 200, "message": msg, "data": data.model_dump()}
