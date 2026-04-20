# app/apis/v1/admin/auth.py

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dtos.admin_dto import AdminLoginRequestDTO
from app.services import admin_service

router = APIRouter()
_bearer = HTTPBearer()


@router.post("/login")
async def admin_login(body: AdminLoginRequestDTO):
    data = await admin_service.admin_login(body.adminEmail, body.password)
    return {"status": 200, "message": "로그인 성공", "data": data.model_dump()}


@router.post("/logout")
async def admin_logout(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    await admin_service.admin_logout(credentials.credentials)
    return {"status": 200, "message": "로그아웃되었습니다."}
