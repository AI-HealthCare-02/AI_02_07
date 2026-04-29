-- =============================================================
-- AH_02_07 HealthGuide — 공통코드 시드 데이터
-- 
-- PK: common_group_code(group_code), common_code(group_code, code)
-- ON CONFLICT 로 멱등 실행 보장 (몇 번이든 재실행 가능)
--
-- 실행: psql -h localhost -U postgres -d healthguide -f scripts/sql/seed_common_codes.sql
-- =============================================================

-- ─────────────────────────────────────────────
-- A. 그룹 코드
-- ─────────────────────────────────────────────
INSERT INTO common_group_code (group_code, group_name, description, is_used, created_at) VALUES
    ('GENDER',           '성별',                '사용자 성별',                    TRUE, NOW()),
    ('PROVIDER',         '가입 경로',            'OAuth / 로컬 등 가입 경로',       TRUE, NOW()),
    ('PREGNANCY',        '임신/수유 상태',        '임신·수유 여부',                  TRUE, NOW()),
    ('SMOKING',          '흡연 상태',             '흡연 여부/빈도',                  TRUE, NOW()),
    ('DRINKING',         '음주 빈도',             '음주 빈도',                      TRUE, NOW()),
    ('EXERCISE',         '운동 빈도',             '운동 빈도',                      TRUE, NOW()),
    ('SLEEP_TIME',       '수면 시간',             '하루 평균 수면 시간대',            TRUE, NOW()),
    ('SENDER_TYPE',      '메시지 발신자',          '채팅 메시지 발신 주체',            TRUE, NOW()),
    ('ADMIN_ROLE',       '관리자 권한',            '관리자 역할 등급',                TRUE, NOW()),
    ('JOB_STATUS',       '작업 상태',             '비동기 작업(의료문서 분석) 상태',  TRUE, NOW()),
    ('DOC_TYPE',         '문서 유형',             '의료 문서 종류',                  TRUE, NOW()),
    ('OCR_STATUS',       'OCR 상태',              'OCR 처리 상태',                  TRUE, NOW()),
    ('GUIDE_STATUS',     '가이드 상태',            '복약 가이드 진행 상태',            TRUE, NOW()),
    ('INPUT_METHOD',     '입력 방식',             '데이터 입력 경로',                TRUE, NOW()),
    ('CONDITION_TYPE',   '환자 상태 유형',         '기저질환·복용약·알레르기 분류',    TRUE, NOW()),
    ('MED_CATEGORY',     '의약품 분류',            '전문/일반/건강기능식품 등',        TRUE, NOW()),
    ('MED_TIMING',       '복약 시점',             '식전/식후/취침전 등',             TRUE, NOW()),
    ('RESULT_TYPE',      '가이드 결과 유형',        'LLM 생성 가이드 결과 종류',       TRUE, NOW()),
    ('REPEAT_TYPE',      '반복 유형',             '알림 반복 주기',                  TRUE, NOW()),
    ('PILL_SOURCE',      '알약 이미지 소스',        '알약 이미지 등록 방식',            TRUE, NOW()),
    ('PILL_ANALYSIS',    '알약 분석 상태',          '알약 분석 요청 상태',             TRUE, NOW()),
    ('PILL_STEP',        '알약 분석 단계',          '알약 분석 파이프라인 단계',        TRUE, NOW()),
    ('PILL_STEP_STATUS', '알약 단계 상태',          '알약 분석 각 단계 상태',          TRUE, NOW()),
    ('PILL_RESULT',      '알약 결과 상태',          '알약 분석 최종 결과 상태',        TRUE, NOW()),
    ('TAG_TYPE',         '태그 유형',             '약품 태그 분류',                  TRUE, NOW()),
    ('SEVERITY',         '주의 강도',             '약품 주의사항 심각도',             TRUE, NOW()),
    ('FILE_CATEGORY',    '파일 카테고리',         '업로드 파일 용도 구분',            TRUE, NOW()),
    ('FILE_ENTITY',      '파일 엔티티 유형',       '파일이 연결된 엔티티 종류',          TRUE, NOW())
ON CONFLICT (group_code) DO UPDATE SET
    group_name  = EXCLUDED.group_name,
    description = EXCLUDED.description,
    is_used     = EXCLUDED.is_used;


-- ─────────────────────────────────────────────
-- B. 개별 코드
-- ─────────────────────────────────────────────
INSERT INTO common_code (group_code, code, code_name, sort_order, is_used, created_at) VALUES

    -- GENDER
    ('GENDER', 'MALE',   '남성', 1, TRUE, NOW()),
    ('GENDER', 'FEMALE', '여성', 2, TRUE, NOW()),
    ('GENDER', 'OTHER',  '기타', 3, TRUE, NOW()),

    -- PROVIDER (가입 경로)
    ('PROVIDER', 'LOCAL',  '로컬(이메일)', 1, TRUE, NOW()),
    ('PROVIDER', 'GOOGLE', 'Google',      2, TRUE, NOW()),
    ('PROVIDER', 'KAKAO',  'Kakao',       3, TRUE, NOW()),

    -- PREGNANCY
    ('PREGNANCY', 'NONE',      '해당없음',    1, TRUE, NOW()),
    ('PREGNANCY', 'PREGNANT',  '임신 중',     2, TRUE, NOW()),
    ('PREGNANCY', 'NURSING',   '수유 중',     3, TRUE, NOW()),
    ('PREGNANCY', 'PLANNING',  '임신 계획 중', 4, TRUE, NOW()),

    -- SMOKING
    ('SMOKING', 'NONE',       '비흡연',   1, TRUE, NOW()),
    ('SMOKING', 'QUIT',       '금연',     2, TRUE, NOW()),
    ('SMOKING', 'OCCASIONAL', '가끔',     3, TRUE, NOW()),
    ('SMOKING', 'DAILY',      '매일',     4, TRUE, NOW()),

    -- DRINKING
    ('DRINKING', 'NONE',       '비음주',         1, TRUE, NOW()),
    ('DRINKING', 'OCCASIONAL', '월 1~2회',       2, TRUE, NOW()),
    ('DRINKING', 'WEEKLY',     '주 1~2회',       3, TRUE, NOW()),
    ('DRINKING', 'DAILY',      '거의 매일',      4, TRUE, NOW()),

    -- EXERCISE
    ('EXERCISE', 'NONE',       '안 함',           1, TRUE, NOW()),
    ('EXERCISE', 'LIGHT',      '주 1~2회 가벼운',  2, TRUE, NOW()),
    ('EXERCISE', 'MODERATE',   '주 3~4회 중간',    3, TRUE, NOW()),
    ('EXERCISE', 'INTENSE',    '주 5회 이상 고강도',4, TRUE, NOW()),

    -- SLEEP_TIME
    ('SLEEP_TIME', 'LT_5H',   '5시간 미만',   1, TRUE, NOW()),
    ('SLEEP_TIME', '5H_7H',   '5~7시간',      2, TRUE, NOW()),
    ('SLEEP_TIME', '7H_9H',   '7~9시간',      3, TRUE, NOW()),
    ('SLEEP_TIME', 'GT_9H',   '9시간 초과',   4, TRUE, NOW()),

    -- SENDER_TYPE
    ('SENDER_TYPE', 'USER',      '사용자',       1, TRUE, NOW()),
    ('SENDER_TYPE', 'ASSISTANT', 'AI 어시스턴트', 2, TRUE, NOW()),
    ('SENDER_TYPE', 'SYSTEM',    '시스템',        3, TRUE, NOW()),

    -- ADMIN_ROLE
    ('ADMIN_ROLE', 'SUPER_ADMIN', '슈퍼 관리자', 1, TRUE, NOW()),
    ('ADMIN_ROLE', 'MANAGER',    '일반 관리자', 2, TRUE, NOW()),

    -- JOB_STATUS
    ('JOB_STATUS', 'JOB_PENDING',    '대기',   1, TRUE, NOW()),
    ('JOB_STATUS', 'JOB_PROCESSING', '처리중', 2, TRUE, NOW()),
    ('JOB_STATUS', 'JOB_COMPLETED',  '완료',   3, TRUE, NOW()),
    ('JOB_STATUS', 'JOB_FAILED',     '실패',   4, TRUE, NOW()),
    ('JOB_STATUS', 'JOB_RETRYING',   '재시도', 5, TRUE, NOW()),

    -- DOC_TYPE
    ('DOC_TYPE', 'DOC_PRESCRIPTION',   '처방전',    1, TRUE, NOW()),
    ('DOC_TYPE', 'DOC_DIAGNOSIS',      '진단서',    2, TRUE, NOW()),
    ('DOC_TYPE', 'DOC_TEST_RESULT',    '검사 결과', 3, TRUE, NOW()),
    ('DOC_TYPE', 'DOC_DISCHARGE',      '퇴원 요약', 4, TRUE, NOW()),
    ('DOC_TYPE', 'DOC_MEDICATION_INFO','약 설명서',  5, TRUE, NOW()),
    ('DOC_TYPE', 'DOC_OTHER',          '기타',      6, TRUE, NOW()),

    -- OCR_STATUS
    ('OCR_STATUS', 'OCR_PENDING',     'OCR 대기', 1, TRUE, NOW()),
    ('OCR_STATUS', 'OCR_IN_PROGRESS', 'OCR 진행', 2, TRUE, NOW()),
    ('OCR_STATUS', 'OCR_COMPLETED',   'OCR 완료', 3, TRUE, NOW()),
    ('OCR_STATUS', 'OCR_FAILED',      'OCR 실패', 4, TRUE, NOW()),

    -- GUIDE_STATUS
    ('GUIDE_STATUS', 'DRAFT',     '초안',     1, TRUE, NOW()),
    ('GUIDE_STATUS', 'ACTIVE',    '활성',     2, TRUE, NOW()),
    ('GUIDE_STATUS', 'PAUSED',    '일시중지', 3, TRUE, NOW()),
    ('GUIDE_STATUS', 'COMPLETED', '완료',     4, TRUE, NOW()),
    ('GUIDE_STATUS', 'EXPIRED',   '만료',     5, TRUE, NOW()),

    -- INPUT_METHOD
    ('INPUT_METHOD', 'MANUAL', '직접 입력', 1, TRUE, NOW()),
    ('INPUT_METHOD', 'OCR',    'OCR 입력',  2, TRUE, NOW()),
    ('INPUT_METHOD', 'VOICE',  '음성 입력', 3, TRUE, NOW()),
    ('INPUT_METHOD', 'CAMERA', '카메라',    4, TRUE, NOW()),
    ('INPUT_METHOD', 'AUTO',   '자동',      5, TRUE, NOW()),

    -- CONDITION_TYPE
    ('CONDITION_TYPE', 'DISEASE',         '기저질환',    1, TRUE, NOW()),
    ('CONDITION_TYPE', 'CURRENT_MED',     '현재 복용약',  2, TRUE, NOW()),
    ('CONDITION_TYPE', 'ALLERGY',         '알레르기',     3, TRUE, NOW()),
    ('CONDITION_TYPE', 'SURGERY_HISTORY', '수술 이력',    4, TRUE, NOW()),

    -- MED_CATEGORY
    ('MED_CATEGORY', 'PRESCRIPTION', '전문의약품',   1, TRUE, NOW()),
    ('MED_CATEGORY', 'OTC',          '일반의약품',   2, TRUE, NOW()),
    ('MED_CATEGORY', 'SUPPLEMENT',   '건강기능식품', 3, TRUE, NOW()),
    ('MED_CATEGORY', 'HERBAL',       '한약',         4, TRUE, NOW()),

    -- MED_TIMING
    ('MED_TIMING', 'BEFORE_MEAL',          '식전',        1, TRUE, NOW()),
    ('MED_TIMING', 'BEFORE_MEAL_30',       '식전 30분',   2, TRUE, NOW()),
    ('MED_TIMING', 'AFTER_MEAL',           '식후',        3, TRUE, NOW()),
    ('MED_TIMING', 'AFTER_MEAL_IMMEDIATE', '식후 즉시',   4, TRUE, NOW()),
    ('MED_TIMING', 'AFTER_MEAL_30',        '식후 30분',   5, TRUE, NOW()),
    ('MED_TIMING', 'WITH_MEAL',            '식사 중',     6, TRUE, NOW()),
    ('MED_TIMING', 'BEFORE_SLEEP',         '취침 전',     7, TRUE, NOW()),
    ('MED_TIMING', 'MORNING',              '기상 직후',   8, TRUE, NOW()),
    ('MED_TIMING', 'AS_NEEDED',            '필요 시',     9, TRUE, NOW()),

    -- RESULT_TYPE
    ('RESULT_TYPE', 'SUMMARY',        '종합 요약',    1, TRUE, NOW()),
    ('RESULT_TYPE', 'INTERACTION',    '상호작용 분석', 2, TRUE, NOW()),
    ('RESULT_TYPE', 'LIFESTYLE_TIP',  '생활습관 조언', 3, TRUE, NOW()),
    ('RESULT_TYPE', 'SIDE_EFFECT',    '부작용 안내',   4, TRUE, NOW()),
    ('RESULT_TYPE', 'EMERGENCY_SIGN', '응급 증상',     5, TRUE, NOW()),

    -- REPEAT_TYPE (기존 코드 + ✅ 추가: RPT_ 접두사 코드)
    ('REPEAT_TYPE', 'ONCE',       '1회',         1, TRUE, NOW()),
    ('REPEAT_TYPE', 'DAILY',      '매일',        2, TRUE, NOW()),
    ('REPEAT_TYPE', 'WEEKLY',     '매주',        3, TRUE, NOW()),
    ('REPEAT_TYPE', 'MONTHLY',    '매월',        4, TRUE, NOW()),
    ('REPEAT_TYPE', 'CUSTOM',     '사용자 지정', 5, TRUE, NOW()),
    ('REPEAT_TYPE', 'RPT_DAILY',   '매일(알림)',        6, TRUE, NOW()),
    ('REPEAT_TYPE', 'RPT_WEEKDAY', '평일(알림)',        7, TRUE, NOW()),
    ('REPEAT_TYPE', 'RPT_CUSTOM',  '사용자 지정(알림)', 8, TRUE, NOW()),

    -- PILL_SOURCE
    ('PILL_SOURCE', 'CAMERA',      '카메라 촬영', 1, TRUE, NOW()),
    ('PILL_SOURCE', 'GALLERY',     '갤러리 선택', 2, TRUE, NOW()),
    ('PILL_SOURCE', 'FILE_UPLOAD', '파일 업로드', 3, TRUE, NOW()),

    -- PILL_ANALYSIS
    ('PILL_ANALYSIS', 'RECEIVED',    '접수됨', 1, TRUE, NOW()),
    ('PILL_ANALYSIS', 'IN_PROGRESS', '분석중',  2, TRUE, NOW()),
    ('PILL_ANALYSIS', 'COMPLETED',   '완료',    3, TRUE, NOW()),
    ('PILL_ANALYSIS', 'FAILED',      '실패',    4, TRUE, NOW()),

    -- PILL_STEP
    ('PILL_STEP', 'PREPROCESSING',  '전처리',    1, TRUE, NOW()),
    ('PILL_STEP', 'PILL_DETECTION', '알약 탐지', 2, TRUE, NOW()),
    ('PILL_STEP', 'PILL_CLASSIFY',  '알약 분류', 3, TRUE, NOW()),
    ('PILL_STEP', 'LLM_ANALYSIS',   'LLM 분석', 4, TRUE, NOW()),

    -- PILL_STEP_STATUS
    ('PILL_STEP_STATUS', 'WAITING', '대기',   1, TRUE, NOW()),
    ('PILL_STEP_STATUS', 'RUNNING', '실행중',  2, TRUE, NOW()),
    ('PILL_STEP_STATUS', 'SUCCESS', '성공',    3, TRUE, NOW()),
    ('PILL_STEP_STATUS', 'FAILED',  '실패',    4, TRUE, NOW()),
    ('PILL_STEP_STATUS', 'SKIPPED', '건너뜀',  5, TRUE, NOW()),

    -- PILL_RESULT
    ('PILL_RESULT', 'IDENTIFIED',   '식별 완료',   1, TRUE, NOW()),
    ('PILL_RESULT', 'UNIDENTIFIED', '식별 불가',   2, TRUE, NOW()),
    ('PILL_RESULT', 'LOW_CONF',     '신뢰도 낮음', 3, TRUE, NOW()),

    -- TAG_TYPE
    ('TAG_TYPE', 'SYMPTOM',    '증상',      1, TRUE, NOW()),
    ('TAG_TYPE', 'DISEASE',    '질환',      2, TRUE, NOW()),
    ('TAG_TYPE', 'INGREDIENT', '성분',      3, TRUE, NOW()),
    ('TAG_TYPE', 'CATEGORY',   '약효 분류', 4, TRUE, NOW()),

    -- SEVERITY
    ('SEVERITY', 'LOW',      '낮음', 1, TRUE, NOW()),
    ('SEVERITY', 'MODERATE', '보통', 2, TRUE, NOW()),
    ('SEVERITY', 'HIGH',     '높음', 3, TRUE, NOW()),
    ('SEVERITY', 'CRITICAL', '위험', 4, TRUE, NOW()),

    -- FILE_CATEGORY
    ('FILE_CATEGORY', 'DOC_MEDICAL',      '의료문서',     1, TRUE, NOW()),
    ('FILE_CATEGORY', 'DOC_PRESCRIPTION', '처방전',          2, TRUE, NOW()),
    ('FILE_CATEGORY', 'IMG_PILL',         '알약 이미지',   3, TRUE, NOW()),
    ('FILE_CATEGORY', 'IMG_GENERAL',      '일반 이미지',   4, TRUE, NOW()),
    ('FILE_CATEGORY', 'DOC_OTHER',        '기타 문서',     5, TRUE, NOW()),

    -- FILE_ENTITY
    ('FILE_ENTITY', 'DOC_JOB',     '의료문서 분석 작업', 1, TRUE, NOW()),
    ('FILE_ENTITY', 'DOC_RESULT',  '의료문서 분석 결과', 2, TRUE, NOW()),
    ('FILE_ENTITY', 'PILL_REQUEST','알약 분석 요청',   3, TRUE, NOW()),
    ('FILE_ENTITY', 'GUIDE',       '복약 가이드',       4, TRUE, NOW()),
    ('FILE_ENTITY', 'CHAT',        '채팅',               5, TRUE, NOW())

ON CONFLICT (group_code, code) DO UPDATE SET
    code_name  = EXCLUDED.code_name,
    sort_order = EXCLUDED.sort_order,
    is_used    = EXCLUDED.is_used;


-- ─────────────────────────────────────────────
-- C. ai_settings 기본값 (chat)
-- ─────────────────────────────────────────────
INSERT INTO ai_settings (config_name, api_model, system_prompt, temperature, max_tokens, is_active)
VALUES (
    'chat',
    'gpt-4o-mini',
    '당신은 HealthGuide AI 건강 상담 도우미입니다. 사용자의 건강·의료·복약·증상·질병·영양·운동·정신건강 관련 질문에 친절하고 정확하게 답변하세요. 전문 의료 행위를 대체하지 않으며, 심각한 증상은 의사 상담을 권유하세요.',
    0.2,
    300,
    TRUE
)
ON CONFLICT (config_name) DO NOTHING;

-- ─────────────────────────────────────────────
-- D. 초기 관리자 계정 (admin / admin1234)
-- ─────────────────────────────────────────────
INSERT INTO admin_users (admin_email, password, admin_name, role_grp, role_code)
VALUES (
    'admin',
    '$2b$12$yrqqGbVH9NpWnDzyuarEaOHm916/ru8dNjCVQb.QcWLcIYE8eDSRe',
    '관리자',
    'ADMIN_ROLE',
    'SUPER_ADMIN'
)
ON CONFLICT (admin_email) DO NOTHING;

-- ─────────────────────────────────────────────
-- 확인 쿼리
-- ─────────────────────────────────────────────
DO $$ BEGIN
    RAISE NOTICE '=== 공통코드 시딩 완료 ===';
END $$;

SELECT g.group_code, g.group_name, COUNT(c.code) AS code_count
  FROM common_group_code g
  LEFT JOIN common_code c ON c.group_code = g.group_code
 GROUP BY g.group_code, g.group_name
 ORDER BY g.group_code;
