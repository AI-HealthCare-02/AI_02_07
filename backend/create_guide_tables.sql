-- ============================================================
-- 건강 가이드 테이블 DDL
-- 담당: 한지수
-- ============================================================

-- 가이드 메인
CREATE TABLE IF NOT EXISTS guides (
    guide_id        SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title           VARCHAR(200) NOT NULL,
    diagnosis_name  VARCHAR(200) NOT NULL,
    hospital_name   VARCHAR(200),
    visit_date      DATE,
    med_start_date  DATE NOT NULL,
    med_end_date    DATE,
    patient_age     INTEGER NOT NULL,
    patient_gender  VARCHAR(20) NOT NULL,   -- GD_MALE | GD_FEMALE
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
    timing          VARCHAR(50),            -- 식전/식후
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

-- 복약 알림 설정 (가이드당 1개 — OneToOne)
-- repeat_type: RPT_DAILY | RPT_WEEKDAY | RPT_CUSTOM
-- ※ 1차 배포: 설정 저장만, Celery beat 스케줄러 미포함
-- ※ 카카오 알림톡 컬럼 미포함 (2차 배포에서 ALTER TABLE로 추가)
CREATE TABLE IF NOT EXISTS guide_reminders (
    reminder_id     SERIAL PRIMARY KEY,
    guide_id        INTEGER NOT NULL UNIQUE REFERENCES guides(guide_id) ON DELETE CASCADE,
    reminder_time   TIME NOT NULL,
    repeat_type     VARCHAR(20) NOT NULL DEFAULT 'RPT_DAILY',
    custom_days     JSONB,                  -- RPT_CUSTOM: [0,1,2,3,4] (0=월)
    is_browser_noti BOOLEAN NOT NULL DEFAULT FALSE,
    is_email_noti   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
