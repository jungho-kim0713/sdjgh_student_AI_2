-- ===============================================================
-- 마이그레이션 001: pgvector 확장 및 RAG 시스템 테이블 생성
-- 작성일: 2026-02-08
-- 설명:
--   - pgvector 확장 설치
--   - 동적 페르소나 관리를 위한 6개 신규 테이블 생성
--   - 벡터 검색을 위한 인덱스 생성
-- ===============================================================

-- Step 1: pgvector 확장 설치
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: 페르소나 정의 테이블
CREATE TABLE IF NOT EXISTS persona_definition (
    id SERIAL PRIMARY KEY,
    role_key VARCHAR(50) UNIQUE NOT NULL,           -- 식별자 (예: "math_tutor")
    role_name VARCHAR(100) NOT NULL,                -- 표시명 (예: "수학 튜터")
    description TEXT,                                -- 설명
    icon VARCHAR(50) DEFAULT '🤖',                   -- 아이콘
    is_system BOOLEAN DEFAULT FALSE,                 -- 시스템 기본 페르소나
    is_active BOOLEAN DEFAULT TRUE,
    created_by INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- AI 모델 설정 (기존 PersonaConfig 통합)
    model_openai VARCHAR(100) DEFAULT 'gpt-4o-mini',
    model_anthropic VARCHAR(100) DEFAULT 'claude-haiku-4-5-20251001',
    model_google VARCHAR(100) DEFAULT 'gemini-2.0-flash',
    max_tokens INTEGER DEFAULT 4096,

    -- 권한 설정
    allow_user BOOLEAN DEFAULT TRUE,
    allow_teacher BOOLEAN DEFAULT TRUE,
    restrict_google BOOLEAN DEFAULT FALSE,
    restrict_anthropic BOOLEAN DEFAULT FALSE,
    restrict_openai BOOLEAN DEFAULT FALSE,

    -- RAG 설정
    use_rag BOOLEAN DEFAULT FALSE,                   -- RAG 사용 여부
    retrieval_strategy VARCHAR(20) DEFAULT 'soft_topk', -- 'soft_topk' | 'gap_based'
    rag_top_k INTEGER DEFAULT 3,                     -- Top-K (고정) 또는 Min-K (Soft)
    rag_max_k INTEGER DEFAULT 7,                     -- Soft Top-K 최대값
    rag_similarity_threshold FLOAT DEFAULT 0.5,      -- 유사도 임계값
    rag_gap_threshold FLOAT DEFAULT 0.1              -- Gap-based 전략용 임계값
);

-- Step 3: 시스템 프롬프트 테이블
CREATE TABLE IF NOT EXISTS persona_system_prompt (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES persona_definition(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,                   -- 'default', 'openai', 'anthropic', 'google'
    system_prompt TEXT NOT NULL,
    updated_by INTEGER REFERENCES "user"(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(persona_id, provider)
);

-- Step 4: 교사 권한 테이블
CREATE TABLE IF NOT EXISTS persona_teacher_permission (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES persona_definition(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    can_edit_prompt BOOLEAN DEFAULT TRUE,
    can_manage_knowledge BOOLEAN DEFAULT TRUE,
    can_view_analytics BOOLEAN DEFAULT TRUE,
    granted_by INTEGER REFERENCES "user"(id),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(persona_id, teacher_id)
);

-- Step 5: 지식 베이스 메타데이터 테이블
CREATE TABLE IF NOT EXISTS persona_knowledge_base (
    id SERIAL PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES persona_definition(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,                      -- 예: "확률과 통계 교재"
    description TEXT,
    created_by INTEGER REFERENCES "user"(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    chunk_strategy VARCHAR(50) DEFAULT 'paragraph',  -- 청킹 전략
    chunk_size INTEGER DEFAULT 1000,
    chunk_overlap INTEGER DEFAULT 200
);

-- Step 6: 업로드된 문서 테이블
CREATE TABLE IF NOT EXISTS knowledge_document (
    id SERIAL PRIMARY KEY,
    knowledge_base_id INTEGER NOT NULL REFERENCES persona_knowledge_base(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(512),
    file_type VARCHAR(100),
    file_size BIGINT,
    content_hash VARCHAR(64),                        -- 중복 방지용
    extracted_text TEXT,
    chunk_count INTEGER DEFAULT 0,
    uploaded_by INTEGER REFERENCES "user"(id),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP,
    processing_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    error_message TEXT
);

-- Step 7: 벡터 저장소 테이블
CREATE TABLE IF NOT EXISTS document_chunk (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    content_length INTEGER,
    embedding vector(1536),                          -- OpenAI text-embedding-3-small 차원
    chunk_metadata JSONB,                            -- 페이지 번호 등
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 8: 인덱스 생성 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_knowledge_document_kb ON knowledge_document(knowledge_base_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_document_status ON knowledge_document(processing_status);
CREATE INDEX IF NOT EXISTS idx_document_chunk_document ON document_chunk(document_id);

-- Step 9: pgvector 인덱스 생성 (벡터 검색 최적화)
-- IVFFlat: 근사 검색 인덱스 (대용량 데이터에 적합)
-- lists 파라미터: 청크 수의 제곱근 정도 (100개 청크 기준: lists=10)
CREATE INDEX IF NOT EXISTS idx_document_chunk_embedding
ON document_chunk
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Step 10: 기존 chat_session 테이블에 persona_id 컬럼 추가 (점진적 마이그레이션)
-- 이미 존재하는 경우 에러 무시
DO $$
BEGIN
    ALTER TABLE chat_session ADD COLUMN persona_id INTEGER REFERENCES persona_definition(id);
EXCEPTION
    WHEN duplicate_column THEN NULL;
END $$;

-- ===============================================================
-- 마이그레이션 완료
-- ===============================================================
