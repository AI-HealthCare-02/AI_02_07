# app/dtos/admin_dto.py

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ── 공통 응답 래퍼 (명세서 형식) ──
class AdminResponse(BaseModel):
    status: int
    message: str
    data: Optional[dict] = None


# ── Auth ──
class AdminLoginRequestDTO(BaseModel):
    adminEmail: str
    password: str


class AdminInfoDTO(BaseModel):
    adminId: int
    adminEmail: str
    adminName: str
    roleCode: str


class AdminLoginDataDTO(BaseModel):
    accessToken: str
    admin: AdminInfoDTO


# ── Dashboard Summary ──
class FilterBlockedCountDTO(BaseModel):
    domainBlocked: int
    emergencyBlocked: int
    total: int


class DashboardSummaryDTO(BaseModel):
    totalUsers: int
    todayActiveUsers: int
    ocrUsageCount: int
    todayChatCount: int
    todayFilterBlockedCount: FilterBlockedCountDTO


# ── Dashboard Chart ──
class ChartDatasetDTO(BaseModel):
    label: str
    data: list[float]


class DashboardChartDTO(BaseModel):
    type: str
    period: str
    labels: list[str]
    datasets: list[ChartDatasetDTO]


# ── Users ──
class AdminUserItemDTO(BaseModel):
    userId: int
    name: str
    email: str
    createdAt: str
    providerCode: str
    providerName: str
    isSuspended: bool
    status: str


class AdminUserListDTO(BaseModel):
    totalCount: int
    page: int
    size: int
    items: list[AdminUserItemDTO]


class UserSuspendResultDTO(BaseModel):
    userId: int
    isSuspended: bool
    status: str


# ── System Settings ──
class AnswerModelConfigDTO(BaseModel):
    apiModel: str
    temperature: float
    maxTokens: int


class FilterModelConfigDTO(BaseModel):
    apiModel: str
    temperature: float
    maxTokens: int
    note: Optional[str] = None


class SystemSettingsDTO(BaseModel):
    answerModel: AnswerModelConfigDTO
    filterModel: FilterModelConfigDTO
    updatedAt: str


# ── System Settings PUT Request ──
class AnswerModelUpdateDTO(BaseModel):
    apiModel: str
    temperature: float = Field(ge=0.0, le=1.0)
    maxTokens: int = Field(ge=100, le=16384)


class FilterModelUpdateDTO(BaseModel):
    apiModel: str


class SystemSettingsUpdateRequestDTO(BaseModel):
    answerModel: AnswerModelUpdateDTO
    filterModel: FilterModelUpdateDTO


# ── LLM Test ──
class LLMTestRequestDTO(BaseModel):
    apiModel: str
    temperature: float = Field(ge=0.0, le=1.0)
    maxTokens: int = Field(ge=100, le=16384)


class LLMTestResultDTO(BaseModel):
    success: bool
    responseTime: Optional[int] = None
    testResponse: Optional[str] = None
    errorMessage: Optional[str] = None
