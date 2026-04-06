# app/dtos/user_dto.py
# ──────────────────────────────────────────────
# 사용자 관련 DTO — DDL 구조에 정확히 대응
# 사용자 프로필, 생활습관, 알레르기, 기저질환 CRUD
# ──────────────────────────────────────────────

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field


# ============================================================
# 사용자 기본 정보
# ============================================================


class UserProfileResponseDTO(BaseModel):
    """
    사용자 프로필 조회 응답.
    users 테이블의 주요 컬럼을 반환합니다.
    """

    user_id: int
    email: str
    nickname: str
    name: str
    gender_code: str | None = None
    birth_date: date | None = None
    provider_code: str = "LOCAL"
    is_suspended: bool = False
    is_active: bool = True  # computed property
    agreed_personal_info: datetime | None = None
    agreed_sensitive_info: datetime | None = None
    agreed_medical_data: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserProfileUpdateDTO(BaseModel):
    """
    사용자 프로필 수정 요청.
    변경할 필드만 포함합니다 (PATCH 방식).
    """

    nickname: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    gender_code: str | None = Field(
        default=None,
        max_length=20,
        description="성별 코드 (MALE, FEMALE 등). 공통코드 GENDER 그룹.",
    )
    birth_date: date | None = Field(default=None, description="생년월일 (YYYY-MM-DD)")


class UserAgreementUpdateDTO(BaseModel):
    """
    동의 정보 업데이트 요청.
    True로 보내면 현재 시각으로 동의 일시를 기록합니다.
    False로 보내면 동의 일시를 NULL로 초기화합니다.
    """

    agreed_personal_info: bool | None = None
    agreed_sensitive_info: bool | None = None
    agreed_medical_data: bool | None = None


class UserDeleteRequestDTO(BaseModel):
    """
    회원 탈퇴 요청 (소프트 딜리트).
    OAuth 전용이므로 비밀번호 확인이 없습니다.
    확인용 문구 입력을 통해 실수 방지.
    """

    confirm_text: str = Field(
        description="탈퇴 확인 문구. '탈퇴합니다'를 정확히 입력해야 합니다.",
    )


# ============================================================
# 사용자 생활 습관
# ============================================================


class UserLifestyleResponseDTO(BaseModel):
    """
    생활 습관 조회 응답.
    user_lifestyle 테이블의 모든 컬럼을 반환합니다.
    code 값은 프론트엔드에서 공통코드 API로 label을 조회합니다.
    """

    height: Decimal | None = None
    weight: Decimal | None = None
    pregnancy_code: str | None = None
    smoking_code: str | None = None
    drinking_code: str | None = None
    exercise_code: str | None = None
    sleep_time_code: str | None = None

    class Config:
        from_attributes = True


class UserLifestyleUpdateDTO(BaseModel):
    """
    생활 습관 수정 요청 (PATCH).
    변경할 필드만 포함합니다.
    code 값은 공통코드 테이블에 존재해야 합니다.
    서비스 레이어에서 유효성을 검증합니다.
    """

    height: Decimal | None = Field(default=None, gt=0, le=300, description="키 (cm)")
    weight: Decimal | None = Field(
        default=None, gt=0, le=500, description="몸무게 (kg)"
    )
    pregnancy_code: str | None = Field(default=None, max_length=20)
    smoking_code: str | None = Field(default=None, max_length=20)
    drinking_code: str | None = Field(default=None, max_length=20)
    exercise_code: str | None = Field(default=None, max_length=20)
    sleep_time_code: str | None = Field(default=None, max_length=20)


# ============================================================
# 알레르기
# ============================================================


class UserAllergyResponseDTO(BaseModel):
    """알레르기 항목 응답"""

    allergy_id: int
    allergy_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserAllergyCreateDTO(BaseModel):
    """알레르기 추가 요청"""

    allergy_name: str = Field(min_length=1, max_length=100, description="알레르기 명칭")


class UserAllergyBulkCreateDTO(BaseModel):
    """알레르기 일괄 추가 요청 (여러 개 한꺼번에)"""

    allergy_names: list[str] = Field(
        min_length=1,
        description="알레르기 명칭 목록",
    )


# ============================================================
# 기저질환
# ============================================================


class UserDiseaseResponseDTO(BaseModel):
    """기저질환 항목 응답"""

    disease_id: int
    disease_name: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserDiseaseCreateDTO(BaseModel):
    """기저질환 추가 요청"""

    disease_name: str = Field(min_length=1, max_length=100, description="질환 명칭")


class UserDiseaseBulkCreateDTO(BaseModel):
    """기저질환 일괄 추가 요청"""

    disease_names: list[str] = Field(
        min_length=1,
        description="질환 명칭 목록",
    )


# ============================================================
# 사용자 전체 건강 정보 (프로필 + 생활습관 + 알레르기 + 기저질환)
# ============================================================


class UserFullHealthProfileDTO(BaseModel):
    """
    사용자 전체 건강 프로필 응답.
    채팅 AI가 사용자 컨텍스트를 구성할 때 활용합니다.
    """

    profile: UserProfileResponseDTO
    lifestyle: UserLifestyleResponseDTO | None = None
    allergies: list[UserAllergyResponseDTO] = []
    diseases: list[UserDiseaseResponseDTO] = []
