# app/models/__init__.py
# ──────────────────────────────────────────────
# 모든 DB 모델을 여기서 re-export
# 다른 모듈에서 from app.models import User 형태로 사용 가능
# ──────────────────────────────────────────────
# ── 공통 코드 ──
from app.models.common_code import CommonGroupCode, CommonCode

# ── 사용자 관련 ──
from app.models.user import User
from app.models.user_lifestyle import UserLifestyle
from app.models.user_allergy import UserAllergy
from app.models.user_disease import UserDisease

# ── 관리자 ──
from app.models.admin import AdminUser

# 팀원들이 추가하는 모델도 여기에 등록
# from app.models.chat import ChatSession, ChatMessage
# from app.models.ai_settings import AISettings
# from app.models.medical_doc import MedicalDocument
# from app.models.guide import HealthGuide
# from app.models.pill import PillAnalysis
# from app.models.admin import AdminLog

__all__ = [
    "CommonGroupCode",
    "CommonCode",
    "AdminUser",
    "User",
    "UserLifestyle",
    "UserAllergy",
    "UserDisease",
]
