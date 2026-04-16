-- ============================================================
-- 건강 가이드 테이블 DDL
-- 담당: 한지수
-- ============================================================

-- 가이드 메인
CREATE TABLE IF NOT EXISTS guides (
    guide_id        SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           VARCHAR(200) NOT NULL,
    diagnosis_name  VARCHAR(200),                  -- 약봉투 분석 시 null 허용
    hospital_name   VARCHAR(200),
    visit_date      DATE,
    med_start_date  DATE NOT NULL,
    med_end_date    DATE,
    patient_age     INTEGER,                -- Optional: 프론트 폼 미포함 시 NULL 허용
    patient_gender  VARCHAR(20),            -- GD_MALE | GD_FEMALE (Optional)
    guide_status    VARCHAR(20) NOT NULL DEFAULT 'GS_ACTIVE',  -- GS_ACTIVE | GS_COMPLETED
    input_method    VARCHAR(20) NOT NULL DEFAULT 'IM_MANUAL',  -- IM_MANUAL | IM_DOCUMENT
    is_deleted      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guides_user_id ON guides(user_id);
CREATE INDEX IF NOT EXISTS idx_guides_status  ON guides(guide_status);

-- 가이드 약물
CREATE TABLE IF NOT EXISTS guide_medications (
    medication_id   SERIAL PRIMARY KEY,
    guide_id        INTEGER NOT NULL REFERENCES guides(guide_id) ON DELETE CASCADE,
    medication_name VARCHAR(200) NOT NULL,
    dosage          VARCHAR(100),           -- 1회 용량
    frequency       VARCHAR(50),            -- 복용 횟수
    timing          VARCHAR(200),           -- 식전/식후 (복수 선택 시 쉼표 구분, 예: "아침 식전,저녁 식후")
    duration_days   INTEGER,                -- 투약 기간(일)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guide_medications_guide_id ON guide_medications(guide_id);

-- 기저질환·복용약·알레르기
-- condition_type: CT_DISEASE | CT_CURRENT_MED | CT_ALLERGY
CREATE TABLE IF NOT EXISTS guide_conditions (
    condition_id    SERIAL PRIMARY KEY,
    guide_id        INTEGER NOT NULL REFERENCES guides(guide_id) ON DELETE CASCADE,
    condition_type  VARCHAR(30) NOT NULL,
    name            VARCHAR(200) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guide_conditions_guide_id ON guide_conditions(guide_id);

-- AI 생성 결과
-- result_type: RT_MEDICATION | RT_LIFESTYLE | RT_CAUTION
-- status: COMPLETED | FAILED
CREATE TABLE IF NOT EXISTS guide_ai_results (
    ai_result_id    SERIAL PRIMARY KEY,
    guide_id        INTEGER NOT NULL REFERENCES guides(guide_id) ON DELETE CASCADE,
    result_type     VARCHAR(30) NOT NULL,
    content         JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'COMPLETED',
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_guide_ai_results_guide_id ON guide_ai_results(guide_id);
CREATE INDEX IF NOT EXISTS idx_guide_ai_results_type     ON guide_ai_results(result_type);

-- 복약 체크 기록
-- UNIQUE: guide_medication_id + check_date (동일 약물 당일 중복 불가)
CREATE TABLE IF NOT EXISTS guide_med_checks (
    check_id            SERIAL PRIMARY KEY,
    guide_id            INTEGER NOT NULL REFERENCES guides(guide_id) ON DELETE CASCADE,
    guide_medication_id INTEGER NOT NULL REFERENCES guide_medications(medication_id) ON DELETE CASCADE,
    check_date          DATE NOT NULL,
    is_taken            BOOLEAN NOT NULL DEFAULT TRUE,
    taken_at            TIMESTAMPTZ NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guide_medication_id, check_date)
);

CREATE INDEX IF NOT EXISTS idx_guide_med_checks_guide_date ON guide_med_checks(guide_id, check_date);

-- 복약 알림 설정 (가이드당 여러 개 — 다중 구조)
-- repeat_type: RPT_DAILY | RPT_WEEKDAY | RPT_CUSTOM
-- ※ 1차 배포: 설정 저장만, Celery beat 스케줄러 미포함
-- ※ 카카오 알림톡 컬럼 미포함 (2차 배포에서 ALTER TABLE로 추가)
CREATE TABLE IF NOT EXISTS guide_reminders (
    reminder_id     SERIAL PRIMARY KEY,
    guide_id        INTEGER NOT NULL REFERENCES guides(guide_id) ON DELETE CASCADE,
    reminder_time   TIME NOT NULL,
    repeat_type     VARCHAR(20) NOT NULL DEFAULT 'RPT_DAILY',
    custom_days     JSONB,                  -- RPT_CUSTOM: [0,1,2,3,4] (0=월)
    is_browser_noti BOOLEAN NOT NULL DEFAULT FALSE,
    is_email_noti   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 마이그레이션 (기존 DB에 이미 테이블이 있는 경우 실행)
-- 신규 설치 시에는 위 CREATE TABLE로 충분하므로 실행 불필요
-- ============================================================

-- 1. guides: patient_age / patient_gender / diagnosis_name NOT NULL → NULL 허용
ALTER TABLE guides ALTER COLUMN patient_age      DROP NOT NULL;
ALTER TABLE guides ALTER COLUMN patient_gender   DROP NOT NULL;
ALTER TABLE guides ALTER COLUMN diagnosis_name   DROP NOT NULL;   -- 약봉투 null 허용

-- 2. guide_medications: timing 컬럼 VARCHAR(50) → VARCHAR(200)
--    (복용 시점 복수 선택 저장을 위한 확장, 예: "아침 식전,저녁 식후")
ALTER TABLE guide_medications ALTER COLUMN timing TYPE VARCHAR(200);

-- 3. guide_reminders: UNIQUE(guide_id) 제약 제거 → 가이드당 다중 알림 허용
--    기존에 UNIQUE 제약이 있는 경우에만 실행 (제약명은 환경에 따라 다를 수 있음)
ALTER TABLE guide_reminders DROP CONSTRAINT IF EXISTS guide_reminders_guide_id_key;

-- 4. guide_dto 변경: MedicationDetailItem.medication_id → guide_medication_id
--    (DB 스키마 변경 없음 — 컬럼명은 medication_id 그대로, DTO 응답 필드명만 변경)
