# app/db/databases.py
# ──────────────────────────────────────────────
# Tortoise ORM 설정 및 초기화
#
# ⚠️ 중요:
#   이 프로젝트는 DDL로 테이블을 먼저 생성합니다.
#   Tortoise ORM은 기존 테이블에 매핑만 합니다.
#   generate_schemas(safe=True) 로 누락된 테이블만 보충합니다.
#   DDL에 정의된 CHECK, 트리거, 복합 FK는 DB 레벨에서 동작합니다.
# ──────────────────────────────────────────────


from app.core.config import get_settings

# ──────────────────────────────────────────────
# 모든 Tortoise 모델 모듈 목록
# 팀원이 새 모델을 추가하면 이 리스트에 등록하세요!
# ──────────────────────────────────────────────
MODELS: list[str] = [
    # ── 공통 ──
    "app.models.common_code",  # 공통 그룹코드 + 상세코드
    "app.models.ai_settings",  # AI 챗봇/LLM 설정
    "app.models.system_error_log",  # 시스템 오류 로그
    # ── 사용자 ──
    "app.models.user",  # 사용자 (황보수호)
    "app.models.user_lifestyle",  # 사용자 생활 습관 (황보수호)
    "app.models.user_allergy",  # 사용자 알레르기 (황보수호)
    "app.models.user_disease",  # 사용자 기저질환 (황보수호)
    "app.models.chat",  # 채팅방 · 메시지 · 북마크 (황보수호)
    # ── 관리자 ──
    "app.models.admin",  # 관리자 계정 (황보수호)
    # ── 의료 문서 분석 (이승원) ──
    "app.models.medical_doc",
    # ── 건강 가이드 (한지수) ──
    "app.models.guide",
]

# Aerich 마이그레이션 도구와 Tortoise ORM이 공유하는 설정
TORTOISE_ORM: dict = {
    "connections": {
        "default": get_settings().database_url,
    },
    "apps": {
        "models": {
            "models": MODELS,
            "default_connection": "default",
        },
    },
}


def get_tortoise_config() -> dict:
    """
    Aerich 마이그레이션 등 외부 도구에서 사용하는 설정을 반환합니다.
    런타임에서는 register_tortoise() 가 직접 설정하므로 이 함수는 호출되지 않습니다.
    """
    from app.core.config import get_settings

    settings = get_settings()
    return {
        "connections": {
            "default": settings.database_url,
        },
        "apps": {
            "models": {
                "models": MODELS,
                "default_connection": "default",
            },
        },
    }


# Aerich 전용 (pyproject.toml 에서 참조)
TORTOISE_ORM = get_tortoise_config
