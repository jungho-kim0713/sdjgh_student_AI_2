-- 002_add_indexes.sql
-- 채팅 이력 조회 가속화를 위한 인덱스 추가

-- ChatSession (user_id, role_key)
CREATE INDEX IF NOT EXISTS idx_chat_session_user_id ON chat_session (user_id);
CREATE INDEX IF NOT EXISTS idx_chat_session_role_key ON chat_session (role_key);

-- Message (session_id, user_id)
CREATE INDEX IF NOT EXISTS idx_message_session_id ON message (session_id);
CREATE INDEX IF NOT EXISTS idx_message_user_id ON message (user_id);

-- ChatFile (session_id, user_id)
CREATE INDEX IF NOT EXISTS idx_chat_file_session_id ON chat_file (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_file_user_id ON chat_file (user_id);

-- PersonaSystemPrompt (persona_id)
CREATE INDEX IF NOT EXISTS idx_persona_sys_prompt_persona_id ON persona_system_prompt (persona_id);

-- DocumentChunk (document_id)
CREATE INDEX IF NOT EXISTS idx_document_chunk_document_id ON document_chunk (document_id);
