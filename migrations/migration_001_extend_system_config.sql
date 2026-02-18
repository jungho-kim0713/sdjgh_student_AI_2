-- ========================================================================
-- Migration 001: Extend SystemConfig value column to TEXT
-- ========================================================================
-- 목적: SystemConfig.value 컬럼을 String(50)에서 TEXT로 확장하여
--       JSON 배열 (enabled_models, model_order 등)을 저장할 수 있도록 함
--
-- 실행 방법:
-- docker exec -i ai_platform_db psql -U postgres -d ai_platform < migrations/migration_001_extend_system_config.sql
-- ========================================================================

-- 1. value 컬럼 타입 변경 (String(50) -> TEXT)
ALTER TABLE system_config ALTER COLUMN value TYPE TEXT;

-- 2. 초기 데이터 삽입 (enabled_models, model_order, last_model_update)
INSERT INTO system_config (key, value) VALUES
    ('enabled_models_openai', '["gpt-4o-mini", "gpt-4o"]'),
    ('enabled_models_anthropic', '["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"]'),
    ('enabled_models_google', '["gemini-2.0-flash", "gemini-3-flash-preview"]'),
    ('model_order_openai', '["gpt-4o-mini", "gpt-4o"]'),
    ('model_order_anthropic', '["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"]'),
    ('model_order_google', '["gemini-2.0-flash", "gemini-3-flash-preview"]'),
    ('last_model_update_openai', '2026-02-15T00:00:00Z'),
    ('last_model_update_anthropic', '2026-02-15T00:00:00Z'),
    ('last_model_update_google', '2026-02-15T00:00:00Z')
ON CONFLICT (key) DO NOTHING;

-- 3. 변경사항 확인
SELECT key,
       CASE
           WHEN LENGTH(value) > 50 THEN LEFT(value, 47) || '...'
           ELSE value
       END as value_preview,
       LENGTH(value) as value_length
FROM system_config
WHERE key LIKE 'enabled_models_%'
   OR key LIKE 'model_order_%'
   OR key LIKE 'last_model_update_%'
ORDER BY key;
