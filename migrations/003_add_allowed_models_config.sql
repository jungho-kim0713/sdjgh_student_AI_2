-- Migration 003: 페르소나별 허용 모델 목록 컬럼 추가
-- 3단계 모델 필터링: 관리자 → 교사/관리자(페르소나별) → 학생
-- JSON 형식: {"openai": ["gpt-4o-mini", "gpt-4o"], "anthropic": [...], "google": [...], "xai": [...]}
ALTER TABLE persona_definition
  ADD COLUMN IF NOT EXISTS allowed_models_config TEXT;
