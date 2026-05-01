-- =============================================================
-- 복약 알림 — 카카오 나에게 보내기 컬럼 추가
-- create_tables.sql 의 med_reminder 테이블 CREATE 문에는 이미 반영돼 있지만,
-- 기존 EC2 DB에 컬럼이 없을 수 있으므로 DO 블록으로 안전하게 추가합니다.
-- 수동 실행: psql -h localhost -U postgres -d healthguide -f scripts/sql/create_tables_patch.sql
-- 또는 create_tables.sql 의 med_reminder 블록 아래에 붙여넣기
-- =============================================================

-- ✅ med_reminder 테이블에 is_kakao_noti 컬럼 추가 (이미 있으면 스킵)
DO $$ BEGIN
    ALTER TABLE med_reminder ADD COLUMN is_kakao_noti BOOLEAN NOT NULL DEFAULT FALSE;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;
