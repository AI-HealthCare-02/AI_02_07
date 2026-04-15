-- =============================================================
-- AH_02_07 HealthGuide — 전체 테이블 생성 스크립트
-- 
-- ● IF NOT EXISTS 를 사용하여 이미 존재하는 테이블은 건너뜁니다.
-- ● 서버 시작 시 Python에서 자동 실행되므로 수동 실행하지 않아도 됩니다.
-- ● 수동 실행: psql -h localhost -U postgres -d healthguide -f scripts/sql/create_tables.sql
-- =============================================================

-- ============================================================
-- 0. 공통 코드 체계
-- ============================================================
CREATE TABLE IF NOT EXISTS common_group_code (
    group_code  VARCHAR(20)  PRIMARY KEY,
    group_name  VARCHAR(100) NOT NULL,
    description TEXT,
    is_used     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS common_code (
    code        VARCHAR(20)  NOT NULL,
    group_code  VARCHAR(20)  NOT NULL
                    REFERENCES common_group_code (group_code),
    code_name   VARCHAR(100) NOT NULL,
    sort_order  INT          NOT NULL DEFAULT 0,
    is_used     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (group_code, code)
);

-- ============================================================
-- 1. 사용자
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    user_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email       VARCHAR(100)  UNIQUE NOT NULL,
    password    VARCHAR(255),
    nickname    VARCHAR(50)   NOT NULL,
    name        VARCHAR(50)   NOT NULL,

    gender_grp    VARCHAR(20)  NOT NULL DEFAULT 'GENDER'
                      CHECK (gender_grp = 'GENDER'),
    gender_code   VARCHAR(20),
    birth_date DATE,
    provider_grp  VARCHAR(20)  NOT NULL DEFAULT 'PROVIDER'
                      CHECK (provider_grp = 'PROVIDER'),
    provider_code VARCHAR(20)  NOT NULL DEFAULT 'LOCAL',

    provider_id   VARCHAR(255),

    is_suspended BOOLEAN     NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMPTZ,

    agreed_personal_info  TIMESTAMPTZ,
    agreed_sensitive_info TIMESTAMPTZ,
    agreed_medical_data   TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (gender_grp, gender_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (provider_grp, provider_code)
        REFERENCES common_code (group_code, code)
);

-- OAuth 중복 방지 인덱스 (IF NOT EXISTS 지원)
CREATE UNIQUE INDEX IF NOT EXISTS uix_users_provider
    ON users (provider_code, provider_id)
    WHERE provider_id IS NOT NULL;

-- ============================================================
-- 2. 사용자 생활 습관
-- ============================================================
CREATE TABLE IF NOT EXISTS user_lifestyle (
    user_id  BIGINT PRIMARY KEY
                 REFERENCES users (user_id) ON DELETE CASCADE,

    height   DECIMAL(5,2),
    weight   DECIMAL(5,2),

    pregnancy_grp   VARCHAR(20) NOT NULL DEFAULT 'PREGNANCY'
                        CHECK (pregnancy_grp = 'PREGNANCY'),
    pregnancy_code  VARCHAR(20),

    smoking_grp     VARCHAR(20) NOT NULL DEFAULT 'SMOKING'
                        CHECK (smoking_grp = 'SMOKING'),
    smoking_code    VARCHAR(20),

    drinking_grp    VARCHAR(20) NOT NULL DEFAULT 'DRINKING'
                        CHECK (drinking_grp = 'DRINKING'),
    drinking_code   VARCHAR(20),

    exercise_grp    VARCHAR(20) NOT NULL DEFAULT 'EXERCISE'
                        CHECK (exercise_grp = 'EXERCISE'),
    exercise_code   VARCHAR(20),

    sleep_time_grp  VARCHAR(20) NOT NULL DEFAULT 'SLEEP_TIME'
                        CHECK (sleep_time_grp = 'SLEEP_TIME'),
    sleep_time_code VARCHAR(20),

    FOREIGN KEY (pregnancy_grp, pregnancy_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (smoking_grp, smoking_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (drinking_grp, drinking_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (exercise_grp, exercise_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (sleep_time_grp, sleep_time_code)
        REFERENCES common_code (group_code, code)
);

-- ============================================================
-- 3. 사용자 알레르기 정보
-- ============================================================
CREATE TABLE IF NOT EXISTS user_allergies (
    allergy_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT       NOT NULL
                     REFERENCES users (user_id) ON DELETE CASCADE,
    allergy_name VARCHAR(100) NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, allergy_name)
);

-- ============================================================
-- 4. 사용자 기저질환 정보
-- ============================================================
CREATE TABLE IF NOT EXISTS user_diseases (
    disease_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      BIGINT       NOT NULL
                     REFERENCES users (user_id) ON DELETE CASCADE,
    disease_name VARCHAR(100) NOT NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (user_id, disease_name)
);

-- ============================================================
-- 5. 채팅방
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_rooms (
    room_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT       NOT NULL
                   REFERENCES users (user_id) ON DELETE CASCADE,
    title      VARCHAR(200) NOT NULL DEFAULT '새로운 대화',
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_chat_rooms_user
    ON chat_rooms (user_id, is_active);

-- ============================================================
-- 6. 채팅 메시지
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_messages (
    message_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    room_id     BIGINT      NOT NULL
                    REFERENCES chat_rooms (room_id) ON DELETE CASCADE,

    sender_type_grp  VARCHAR(20) NOT NULL DEFAULT 'SENDER_TYPE'
                         CHECK (sender_type_grp = 'SENDER_TYPE'),
    sender_type_code VARCHAR(20) NOT NULL,

    content       TEXT        NOT NULL,
    filter_result VARCHAR(20),          -- 3단계 필터 결과: PASS | DOMAIN | EMERGENCY (사용자 메시지는 NULL)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (sender_type_grp, sender_type_code)
        REFERENCES common_code (group_code, code)
);

-- 이미 생성된 테이블에 filter_result 컬럼이 없는 경우 자동 추가
DO $$ BEGIN
    ALTER TABLE chat_messages ADD COLUMN filter_result VARCHAR(20);
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- prompt_tokens / completion_tokens 컬럼 추가
DO $$ BEGIN
    ALTER TABLE chat_messages ADD COLUMN prompt_tokens INT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE chat_messages ADD COLUMN completion_tokens INT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
DO $$ BEGIN
    ALTER TABLE chat_messages ADD COLUMN latency_ms INT;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- users 테이블에 last_active_at 컬럼 추가
DO $$ BEGIN
    ALTER TABLE users ADD COLUMN last_active_at TIMESTAMPTZ;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_chat_messages_room
    ON chat_messages (room_id, created_at);

-- ============================================================
-- 7. AI 응답 북마크
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_bookmarks (
    bookmark_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL
                            REFERENCES users (user_id) ON DELETE CASCADE,
    question_message_id BIGINT REFERENCES chat_messages (message_id) ON DELETE SET NULL,
    answer_message_id   BIGINT REFERENCES chat_messages (message_id) ON DELETE SET NULL,
    question_content    TEXT   NOT NULL,
    answer_content      TEXT   NOT NULL,
    memo                TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_bookmarks_user
    ON chat_bookmarks (user_id, created_at DESC);

-- ============================================================
-- 8. 관리자 계정
-- ============================================================
CREATE TABLE IF NOT EXISTS admin_users (
    admin_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    admin_email   VARCHAR(100) UNIQUE NOT NULL,
    password      VARCHAR(255) NOT NULL,
    admin_name    VARCHAR(50)  NOT NULL,

    role_grp      VARCHAR(20)  NOT NULL DEFAULT 'ADMIN_ROLE'
                      CHECK (role_grp = 'ADMIN_ROLE'),
    role_code     VARCHAR(20)  NOT NULL DEFAULT 'MANAGER',

    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (role_grp, role_code)
        REFERENCES common_code (group_code, code)
);

-- ============================================================
-- 9. AI 챗봇 및 LLM 설정
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_settings (
    setting_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    config_name  VARCHAR(50) UNIQUE NOT NULL,

    api_model          VARCHAR(50) NOT NULL DEFAULT 'gpt-4',
    system_prompt      TEXT        NOT NULL,
    emergency_keywords TEXT,

    temperature       DECIMAL(3,2) NOT NULL DEFAULT 0.70
                          CHECK (temperature BETWEEN 0.00 AND 2.00),
    max_tokens        INT          NOT NULL DEFAULT 1000
                          CHECK (max_tokens > 0),

    min_threshold     DECIMAL(3,2) NOT NULL DEFAULT 0.50
                          CHECK (min_threshold BETWEEN 0.00 AND 1.00),
    auto_retry_count  INT          NOT NULL DEFAULT 3
                          CHECK (auto_retry_count >= 0),

    is_active  BOOLEAN     NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 10. 시스템 오류 로그
-- ============================================================
CREATE TABLE IF NOT EXISTS system_error_logs (
    log_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       BIGINT,
    error_type    VARCHAR(100),
    error_message TEXT         NOT NULL,
    stack_trace   TEXT,
    request_url   VARCHAR(2048),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_logs_created
    ON system_error_logs (created_at);
CREATE INDEX IF NOT EXISTS idx_error_logs_type
    ON system_error_logs (error_type);

-- ============================================================
-- 11. updated_at 자동 갱신 트리거
-- ============================================================
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;

$$ LANGUAGE plpgsql;

-- 트리거는 IF NOT EXISTS 가 없으므로 DROP IF EXISTS 후 CREATE
DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
    CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_chat_rooms_updated_at ON chat_rooms;
    CREATE TRIGGER trg_chat_rooms_updated_at
        BEFORE UPDATE ON chat_rooms
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_ai_settings_updated_at ON ai_settings;
    CREATE TRIGGER trg_ai_settings_updated_at
        BEFORE UPDATE ON ai_settings
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ============================================================
-- 13. 의료문서 vLLM 분석 작업  ★ 수정: 파일 컬럼 제거
-- ============================================================
-- 기존 테이블이 있다면 DROP 후 재생성하거나,
-- 처음 생성이라면 아래를 사용합니다.
-- (운영 중이라면 ALTER TABLE로 컬럼 삭제하세요)
-- ============================================================
CREATE TABLE IF NOT EXISTS doc_analysis_job (
    job_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT       NOT NULL
                        REFERENCES users (user_id) ON DELETE CASCADE,

    status_grp      VARCHAR(20)  NOT NULL DEFAULT 'JOB_STATUS'
                        CHECK (status_grp = 'JOB_STATUS'),
    status_code     VARCHAR(20)  NOT NULL DEFAULT 'JOB_PENDING',

    doc_type_grp    VARCHAR(20)  NOT NULL DEFAULT 'DOC_TYPE'
                        CHECK (doc_type_grp = 'DOC_TYPE'),
    doc_type_code   VARCHAR(20),

    -- ★ file_name, file_path, file_size 제거
    -- → uploaded_file + file_entity_map (entity_type_code = 'DOC_JOB') 으로 관리

    error_message   TEXT,
    processing_time FLOAT,
    is_deleted      BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (status_grp, status_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (doc_type_grp, doc_type_code)
        REFERENCES common_code (group_code, code)
);

CREATE INDEX IF NOT EXISTS idx_doc_analysis_job_user
    ON doc_analysis_job (user_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_doc_analysis_job_status
    ON doc_analysis_job (status_code);

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_doc_analysis_job_updated_at ON doc_analysis_job;
    CREATE TRIGGER trg_doc_analysis_job_updated_at
        BEFORE UPDATE ON doc_analysis_job
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ============================================================
-- 14. 복약 가이드 메인
-- ============================================================
CREATE TABLE IF NOT EXISTS health_guide (
    guide_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT       NOT NULL
                        REFERENCES users (user_id) ON DELETE CASCADE,
    title           VARCHAR(200),
    hospital_name   VARCHAR(200),
    diagnosis_name  VARCHAR(500),
    visit_date      DATE,
    med_start_date  DATE,
    med_end_date    DATE,

    guide_status_grp  VARCHAR(20) NOT NULL DEFAULT 'GUIDE_STATUS'
                          CHECK (guide_status_grp = 'GUIDE_STATUS'),
    guide_status_code VARCHAR(20) NOT NULL,

    input_method_grp  VARCHAR(20) NOT NULL DEFAULT 'INPUT_METHOD'
                          CHECK (input_method_grp = 'INPUT_METHOD'),
    input_method_code VARCHAR(20) NOT NULL,

    patient_age       INT,

    patient_gender_grp  VARCHAR(20) NOT NULL DEFAULT 'GENDER'
                            CHECK (patient_gender_grp = 'GENDER'),
    patient_gender_code VARCHAR(20),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (guide_status_grp, guide_status_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (input_method_grp, input_method_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (patient_gender_grp, patient_gender_code)
        REFERENCES common_code (group_code, code)
);

CREATE INDEX IF NOT EXISTS idx_health_guide_user
    ON health_guide (user_id);

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_health_guide_updated_at ON health_guide;
    CREATE TRIGGER trg_health_guide_updated_at
        BEFORE UPDATE ON health_guide
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ============================================================
-- 15. 의료문서 분석 결과  ★ 수정: 파일 컬럼 제거
-- ============================================================
CREATE TABLE IF NOT EXISTS doc_analysis_result (
    doc_result_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id             BIGINT NOT NULL UNIQUE
                           REFERENCES doc_analysis_job (job_id) ON DELETE CASCADE,
    guide_id           BIGINT,
    user_id            BIGINT NOT NULL
                           REFERENCES users (user_id) ON DELETE CASCADE,

    doc_type_grp       VARCHAR(20) NOT NULL DEFAULT 'DOC_TYPE'
                           CHECK (doc_type_grp = 'DOC_TYPE'),
    doc_type_code      VARCHAR(20) NOT NULL,

    -- ★ file_name, file_url, file_size 제거
    -- → uploaded_file + file_entity_map (entity_type_code = 'DOC_RESULT') 으로 관리

    ocr_status_grp     VARCHAR(20) NOT NULL DEFAULT 'OCR_STATUS'
                           CHECK (ocr_status_grp = 'OCR_STATUS'),
    ocr_status_code    VARCHAR(20) NOT NULL DEFAULT 'OCR_PENDING',

    ocr_raw_text       TEXT,
    ocr_confidence     INT          CHECK (ocr_confidence BETWEEN 0 AND 100),
    overall_confidence FLOAT        CHECK (overall_confidence BETWEEN 0.0 AND 1.0),
    raw_summary        TEXT,
    is_deleted         BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (doc_type_grp, doc_type_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (ocr_status_grp, ocr_status_code)
        REFERENCES common_code (group_code, code)
);

DO $$ BEGIN
    ALTER TABLE doc_analysis_result
        ADD CONSTRAINT fk_doc_analysis_result_guide
            FOREIGN KEY (guide_id) REFERENCES health_guide (guide_id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_doc_analysis_result_user
    ON doc_analysis_result (user_id, is_deleted);

-- guide_id FK (health_guide 가 이 시점에 이미 존재)
DO $$ BEGIN
    ALTER TABLE doc_analysis_result
        ADD CONSTRAINT fk_doc_analysis_result_guide
            FOREIGN KEY (guide_id) REFERENCES health_guide (guide_id) ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_doc_analysis_result_user
    ON doc_analysis_result (user_id, is_deleted);

-- ============================================================
-- 16. 환자 기저질환·복용약·알레르기 (가이드별)
-- ============================================================
CREATE TABLE IF NOT EXISTS health_condition (
    condition_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guide_id       BIGINT      NOT NULL
                       REFERENCES health_guide (guide_id) ON DELETE CASCADE,

    condition_type_grp  VARCHAR(20) NOT NULL DEFAULT 'CONDITION_TYPE'
                            CHECK (condition_type_grp = 'CONDITION_TYPE'),
    condition_type_code VARCHAR(20) NOT NULL,

    condition_name VARCHAR(200),
    sort_order     INT          NOT NULL DEFAULT 0,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (condition_type_grp, condition_type_code)
        REFERENCES common_code (group_code, code)
);

-- ============================================================
-- 17. 처방전 기본 정보
-- ============================================================
CREATE TABLE IF NOT EXISTS prescription (
    prescription_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_result_id     BIGINT NOT NULL UNIQUE
                          REFERENCES doc_analysis_result (doc_result_id) ON DELETE CASCADE,
    prescription_date DATE,
    pharmacy_name     VARCHAR(200),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_prescription_updated_at ON prescription;
    CREATE TRIGGER trg_prescription_updated_at
        BEFORE UPDATE ON prescription
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ============================================================
-- 18. 가이드 처방 약물 상세
-- ============================================================
CREATE TABLE IF NOT EXISTS guide_medication (
    guide_medication_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guide_id            BIGINT       NOT NULL
                            REFERENCES health_guide (guide_id) ON DELETE CASCADE,
    prescription_id     BIGINT
                            REFERENCES prescription (prescription_id) ON DELETE SET NULL,

    med_category_grp    VARCHAR(20) NOT NULL DEFAULT 'MED_CATEGORY'
                            CHECK (med_category_grp = 'MED_CATEGORY'),
    med_category_code   VARCHAR(20),

    medication_name     VARCHAR(200) NOT NULL,
    dosage              VARCHAR(100),
    frequency           VARCHAR(100),

    timing_grp          VARCHAR(20) NOT NULL DEFAULT 'MED_TIMING'
                            CHECK (timing_grp = 'MED_TIMING'),
    timing_code         VARCHAR(20),

    duration_days       INT,
    purpose             TEXT,
    side_effect         TEXT,
    missed_dose_guide   TEXT,
    emergency_sign      TEXT,
    confidence          FLOAT        CHECK (confidence BETWEEN 0.0 AND 1.0),
    sort_order          INT          NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (med_category_grp, med_category_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (timing_grp, timing_code)
        REFERENCES common_code (group_code, code)
);

-- ============================================================
-- 19. LLM AI 생성 가이드 결과
-- ============================================================
CREATE TABLE IF NOT EXISTS guide_ai_result (
    ai_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guide_id     BIGINT      NOT NULL
                     REFERENCES health_guide (guide_id) ON DELETE CASCADE,

    result_type_grp  VARCHAR(20) NOT NULL DEFAULT 'RESULT_TYPE'
                         CHECK (result_type_grp = 'RESULT_TYPE'),
    result_type_code VARCHAR(20) NOT NULL,

    content      TEXT,
    version      INT          NOT NULL DEFAULT 1,
    is_latest    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (result_type_grp, result_type_code)
        REFERENCES common_code (group_code, code),

    UNIQUE (guide_id, result_type_code, version)
);

-- ============================================================
-- 20. 복약 체크 기록
-- ============================================================
CREATE TABLE IF NOT EXISTS med_check_log (
    check_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guide_id            BIGINT NOT NULL
                            REFERENCES health_guide (guide_id) ON DELETE CASCADE,
    guide_medication_id BIGINT NOT NULL
                            REFERENCES guide_medication (guide_medication_id) ON DELETE CASCADE,
    check_date          DATE   NOT NULL,
    is_taken            BOOLEAN NOT NULL DEFAULT FALSE,
    taken_at            TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (guide_id, guide_medication_id, check_date),
    CHECK (is_taken = TRUE OR taken_at IS NULL)
);

CREATE INDEX IF NOT EXISTS idx_med_check_log_guide_date
    ON med_check_log (guide_id, check_date);

-- ============================================================
-- 21. 복약 알림 설정
-- ============================================================
CREATE TABLE IF NOT EXISTS med_reminder (
    reminder_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guide_id        BIGINT NOT NULL UNIQUE
                        REFERENCES health_guide (guide_id) ON DELETE CASCADE,
    reminder_time   TIME   NOT NULL,

    repeat_type_grp  VARCHAR(20) NOT NULL DEFAULT 'REPEAT_TYPE'
                         CHECK (repeat_type_grp = 'REPEAT_TYPE'),
    repeat_type_code VARCHAR(20),

    is_browser_noti BOOLEAN NOT NULL DEFAULT FALSE,
    is_email_noti   BOOLEAN NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (repeat_type_grp, repeat_type_code)
        REFERENCES common_code (group_code, code)
);

DO $$ BEGIN
    DROP TRIGGER IF EXISTS trg_med_reminder_updated_at ON med_reminder;
    CREATE TRIGGER trg_med_reminder_updated_at
        BEFORE UPDATE ON med_reminder
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ============================================================
-- 22. 알약 이미지 분석 요청  ★ 수정: image_url 제거
-- ============================================================

CREATE TABLE IF NOT EXISTS pill_analysis_request (
    analysis_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    source_type_grp  VARCHAR(20) NOT NULL DEFAULT 'PILL_SOURCE'
                         CHECK (source_type_grp = 'PILL_SOURCE'),
    source_type_code VARCHAR(20) NOT NULL,

    -- ★ image_url 제거
    -- → uploaded_file + file_entity_map (entity_type_code = 'PILL_REQUEST') 으로 관리
    -- → 멀티 이미지(여러 각도 촬영 등) 지원 가능

    status_grp   VARCHAR(20) NOT NULL DEFAULT 'PILL_ANALYSIS'
                     CHECK (status_grp = 'PILL_ANALYSIS'),
    status_code  VARCHAR(20) NOT NULL DEFAULT 'RECEIVED',

    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    FOREIGN KEY (source_type_grp, source_type_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (status_grp, status_code)
        REFERENCES common_code (group_code, code)
);

CREATE INDEX IF NOT EXISTS idx_pill_analysis_request_status
    ON pill_analysis_request (status_code);


-- ============================================================
-- 23. 알약 분석 단계 (pill_analysis_request CASCADE 재생성으로 재정의 필요)
-- ============================================================

CREATE TABLE IF NOT EXISTS pill_analysis_step (
    step_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_id  UUID NOT NULL
                     REFERENCES pill_analysis_request (analysis_id) ON DELETE CASCADE,

    step_code_grp  VARCHAR(20) NOT NULL DEFAULT 'PILL_STEP'
                       CHECK (step_code_grp = 'PILL_STEP'),
    step_code_code VARCHAR(20) NOT NULL,

    status_grp     VARCHAR(20) NOT NULL DEFAULT 'PILL_STEP_STATUS'
                       CHECK (status_grp = 'PILL_STEP_STATUS'),
    status_code    VARCHAR(20) NOT NULL DEFAULT 'WAITING',

    progress_percent SMALLINT NOT NULL DEFAULT 0
                         CHECK (progress_percent BETWEEN 0 AND 100),

    FOREIGN KEY (step_code_grp, step_code_code)
        REFERENCES common_code (group_code, code),
    FOREIGN KEY (status_grp, status_code)
        REFERENCES common_code (group_code, code),

    UNIQUE (analysis_id, step_code_code)
);

CREATE INDEX IF NOT EXISTS idx_pill_analysis_step_analysis
    ON pill_analysis_step (analysis_id);

CREATE INDEX IF NOT EXISTS idx_pill_analysis_step_analysis
    ON pill_analysis_step (analysis_id);

-- ============================================================
-- 24. 약품 기본 정보
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine (
    medicine_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_name     VARCHAR(200) NOT NULL,
    ingredient_name  VARCHAR(200) NOT NULL,
    product_strength VARCHAR(50),
    thumbnail_url    VARCHAR(500)
);

-- ============================================================
-- 25. 알약 분석 결과 (pill_analysis_request CASCADE 재생성으로 재정의 필요)
-- ============================================================

CREATE TABLE IF NOT EXISTS pill_analysis_result (
    result_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_id  UUID   NOT NULL UNIQUE
                     REFERENCES pill_analysis_request (analysis_id) ON DELETE CASCADE,
    medicine_id  BIGINT NOT NULL
                     REFERENCES medicine (medicine_id),

    confidence_score DECIMAL(5,2) NOT NULL
                         CHECK (confidence_score BETWEEN 0 AND 100),

    result_status_grp  VARCHAR(20) NOT NULL DEFAULT 'PILL_RESULT'
                           CHECK (result_status_grp = 'PILL_RESULT'),
    result_status_code VARCHAR(20) NOT NULL,

    FOREIGN KEY (result_status_grp, result_status_code)
        REFERENCES common_code (group_code, code)
);


-- ============================================================
-- 26. 약품 태그
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_tag (
    tag_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_name    VARCHAR(100) NOT NULL,

    tag_type_grp  VARCHAR(20) NOT NULL DEFAULT 'TAG_TYPE'
                      CHECK (tag_type_grp = 'TAG_TYPE'),
    tag_type_code VARCHAR(20) NOT NULL,

    color_token VARCHAR(30),

    FOREIGN KEY (tag_type_grp, tag_type_code)
        REFERENCES common_code (group_code, code)
);

-- ============================================================
-- 27. 약품-태그 매핑
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_tag_map (
    medicine_id BIGINT NOT NULL
                    REFERENCES medicine (medicine_id) ON DELETE CASCADE,
    tag_id      BIGINT NOT NULL
                    REFERENCES medicine_tag (tag_id) ON DELETE CASCADE,

    PRIMARY KEY (medicine_id, tag_id)
);

-- ============================================================
-- 28. 약품 효능
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_effect (
    effect_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicine_id        BIGINT NOT NULL
                           REFERENCES medicine (medicine_id) ON DELETE CASCADE,
    effect_title       VARCHAR(100),
    effect_description TEXT
);

CREATE INDEX IF NOT EXISTS idx_medicine_effect_medicine
    ON medicine_effect (medicine_id);

-- ============================================================
-- 29. 약품 복약 정보
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_dosage (
    dosage_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicine_id    BIGINT NOT NULL UNIQUE
                       REFERENCES medicine (medicine_id) ON DELETE CASCADE,
    dosage_text    VARCHAR(255),
    frequency_text VARCHAR(255)
);

-- ============================================================
-- 30. 약품 주의사항
-- ============================================================
CREATE TABLE IF NOT EXISTS medicine_caution (
    caution_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    medicine_id  BIGINT NOT NULL
                     REFERENCES medicine (medicine_id) ON DELETE CASCADE,
    caution_title VARCHAR(100),

    severity_grp  VARCHAR(20) NOT NULL DEFAULT 'SEVERITY'
                      CHECK (severity_grp = 'SEVERITY'),
    severity_code VARCHAR(20),

    FOREIGN KEY (severity_grp, severity_code)
        REFERENCES common_code (group_code, code)
);

CREATE INDEX IF NOT EXISTS idx_medicine_caution_medicine
    ON medicine_caution (medicine_id);

-- ============================================================
-- 31. 공통 파일 업로드 (S3 멀티파일)
-- ============================================================
CREATE TABLE IF NOT EXISTS uploaded_file (
    file_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT        NOT NULL
                        REFERENCES users (user_id) ON DELETE CASCADE,

    -- S3 저장 정보
    original_name   VARCHAR(500)  NOT NULL,
    stored_name     VARCHAR(500)  NOT NULL,
    s3_bucket       VARCHAR(200)  NOT NULL,
    s3_key          VARCHAR(1000) NOT NULL,
    s3_url          VARCHAR(2000) NOT NULL,

    -- 파일 메타
    content_type    VARCHAR(200),
    file_size       BIGINT        NOT NULL DEFAULT 0
                        CHECK (file_size >= 0),
    file_extension  VARCHAR(20),

    -- 파일 용도 구분 (공통코드)
    file_category_grp  VARCHAR(20) NOT NULL DEFAULT 'FILE_CATEGORY'
                           CHECK (file_category_grp = 'FILE_CATEGORY'),
    file_category_code VARCHAR(20) NOT NULL,

    -- 상태
    is_deleted      BOOLEAN       NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    FOREIGN KEY (file_category_grp, file_category_code)
        REFERENCES common_code (group_code, code)
);

CREATE INDEX IF NOT EXISTS idx_uploaded_file_user
    ON uploaded_file (user_id, is_deleted);
CREATE INDEX IF NOT EXISTS idx_uploaded_file_category
    ON uploaded_file (file_category_code, is_deleted);
CREATE UNIQUE INDEX IF NOT EXISTS uix_uploaded_file_s3_key
    ON uploaded_file (s3_bucket, s3_key);


-- ============================================================
-- 32. 파일-엔티티 매핑 (다대다 — 멀티파일 지원)
-- ============================================================
-- entity_type: 어떤 테이블과 연결되는지 (DOC_JOB, DOC_RESULT, PILL_REQUEST, GUIDE, CHAT 등)
-- entity_id  : 해당 테이블의 PK 값
-- ============================================================
CREATE TABLE IF NOT EXISTS file_entity_map (
    map_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_id      BIGINT       NOT NULL
                     REFERENCES uploaded_file (file_id) ON DELETE CASCADE,

    entity_type_grp  VARCHAR(20) NOT NULL DEFAULT 'FILE_ENTITY'
                         CHECK (entity_type_grp = 'FILE_ENTITY'),
    entity_type_code VARCHAR(20) NOT NULL,

    entity_id    BIGINT       NOT NULL,

    sort_order   INT          NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    FOREIGN KEY (entity_type_grp, entity_type_code)
        REFERENCES common_code (group_code, code),

    -- 같은 엔티티에 같은 파일 중복 매핑 방지
    UNIQUE (file_id, entity_type_code, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_file_entity_map_entity
    ON file_entity_map (entity_type_code, entity_id);
CREATE INDEX IF NOT EXISTS idx_file_entity_map_file
    ON file_entity_map (file_id);


-- ============================================================
-- 완료 메시지
-- ============================================================
DO $$ BEGIN
    RAISE NOTICE '=== AH_02_07 HealthGuide: 모든 테이블 생성/확인 완료 ===';
END $$;
