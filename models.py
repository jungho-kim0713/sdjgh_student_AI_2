from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from extensions import db
from pgvector.sqlalchemy import Vector

# ---------------------------------------------------------
# [1] 사용자(User) 모델
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    """
    사용자 계정 정보를 저장하는 테이블입니다.
    Flask-Login의 UserMixin을 상속받아 인증 관련 기능을 제공합니다.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # 로그인 ID (고유값)
    password_hash = db.Column(db.String(200), nullable=False)         # 암호화된 비밀번호
    is_admin = db.Column(db.Boolean, default=False)                   # 관리자 여부
    role = db.Column(db.String(20), default="user", nullable=False)   # 사용자 역할(user|teacher)
    google_id = db.Column(db.String(100), unique=True, nullable=True) # 구글 고유 ID
    email = db.Column(db.String(120), unique=True, nullable=True)     # 구글 이메일
    is_approved = db.Column(db.Boolean, default=False)                # 관리자 승인 여부

    def set_password(self, password):
        """비밀번호를 안전하게 해시화하여 저장합니다."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """입력된 비밀번호와 저장된 해시를 비교하여 검증합니다."""
        return check_password_hash(self.password_hash, password)

# ---------------------------------------------------------
# [2] 대화방(ChatSession) 모델
# ---------------------------------------------------------
class ChatSession(db.Model):
    """
    하나의 대화 주제(채팅방)를 나타내는 테이블입니다.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)  # 대화방 제목 (보통 첫 질문으로 자동 설정)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) # 소유자 ID
    role_key = db.Column(db.String(50), nullable=False) # 사용된 AI 페르소나 (예: 'wangchobo_tutor')
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow) # 생성 시간

# ---------------------------------------------------------
# [3] 메시지(Message) 모델
# ---------------------------------------------------------
class Message(db.Model):
    """
    채팅방 내의 개별 말풍선(질문/답변)을 저장하는 테이블입니다.
    """
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_user = db.Column(db.Boolean, default=True)      # True: 사용자 질문, False: AI 답변
    content = db.Column(db.Text, nullable=True)        # 텍스트 내용
    image_path = db.Column(db.String(1024), nullable=True) # 이미지 경로 (콤마로 구분)
    provider = db.Column(db.String(20), nullable=True) # 답변을 생성한 AI 모델 (gpt, claude 등)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ---------------------------------------------------------
# [4] 파일(ChatFile) 모델
# ---------------------------------------------------------
class ChatFile(db.Model):
    """
    사용자가 업로드하거나 AI가 생성한 파일 정보를 저장합니다.
    """
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=True) 
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)       # 원본 파일명
    storage_path = db.Column(db.String(512), nullable=False)   # 서버 저장 경로 (static/uploads/...)
    file_type = db.Column(db.String(100), nullable=True)       # MIME 타입 (image/png, text/plain 등)
    file_size = db.Column(db.Integer, nullable=True)           # 파일 크기 (bytes)
    uploaded_by = db.Column(db.String(20), default='user')     # 'user' 또는 'ai'
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# ---------------------------------------------------------
# [5] 시스템 설정(SystemConfig) 모델
# ---------------------------------------------------------
class SystemConfig(db.Model):
    """
    전역 시스템 설정 (예: 서비스 점검 모드, 공급사 제한 상태 등)
    NOTE: value 컬럼은 JSON 배열을 저장하기 위해 Text 타입 사용
    """
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

# ---------------------------------------------------------
# [6] 페르소나 설정(PersonaConfig) 모델
# ---------------------------------------------------------
class PersonaConfig(db.Model):
    """
    각 페르소나별로 사용할 AI 모델과 토큰 설정을 저장합니다.
    (관리자 패널에서 수정 가능)
    """
    id = db.Column(db.Integer, primary_key=True)
    role_key = db.Column(db.String(50), unique=True, nullable=False) # 페르소나 식별키
    model_openai = db.Column(db.String(100), default="gpt-4o-mini")
    model_anthropic = db.Column(db.String(100), default="claude-haiku-4-5-20251001")
    model_google = db.Column(db.String(100), default="gemini-2.0-flash")
    max_tokens = db.Column(db.Integer, default=4096) 
    model_id = db.Column(db.String(100), nullable=True) # (구버전 호환용)
    allow_user = db.Column(db.Boolean, default=True)
    allow_teacher = db.Column(db.Boolean, default=True)
    restrict_google = db.Column(db.Boolean, default=False)
    restrict_anthropic = db.Column(db.Boolean, default=False)
    restrict_openai = db.Column(db.Boolean, default=False)

# ---------------------------------------------------------
# [7] 페르소나 정의(PersonaDefinition) 모델 - RAG 시스템
# ---------------------------------------------------------
class PersonaDefinition(db.Model):
    """
    동적 페르소나 관리를 위한 테이블입니다.
    기존 prompts.py의 하드코딩을 DB로 이동하여 관리자가 웹에서 페르소나를 추가/수정할 수 있습니다.
    """
    __tablename__ = 'persona_definition'

    id = db.Column(db.Integer, primary_key=True)
    role_key = db.Column(db.String(50), unique=True, nullable=False)  # 식별자 (예: "math_tutor")
    role_name = db.Column(db.String(100), nullable=False)             # 표시명 (예: "수학 튜터")
    description = db.Column(db.Text)                                  # 설명
    icon = db.Column(db.String(50), default='🤖')                     # 아이콘
    is_system = db.Column(db.Boolean, default=False)                  # 시스템 기본 페르소나
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # AI 모델 설정
    model_openai = db.Column(db.String(100), default='gpt-4o-mini')
    model_anthropic = db.Column(db.String(100), default='claude-haiku-4-5-20251001')
    model_google = db.Column(db.String(100), default='gemini-2.0-flash')
    max_tokens = db.Column(db.Integer, default=4096)

    # 권한 설정
    allow_user = db.Column(db.Boolean, default=True)
    allow_teacher = db.Column(db.Boolean, default=True)
    restrict_google = db.Column(db.Boolean, default=False)
    restrict_anthropic = db.Column(db.Boolean, default=False)
    restrict_openai = db.Column(db.Boolean, default=False)

    # RAG 설정
    use_rag = db.Column(db.Boolean, default=False)                    # RAG 사용 여부
    retrieval_strategy = db.Column(db.String(20), default='soft_topk') # 'soft_topk' | 'gap_based'
    rag_top_k = db.Column(db.Integer, default=3)                      # Top-K (고정) 또는 Min-K (Soft)
    rag_max_k = db.Column(db.Integer, default=7)                      # Soft Top-K 최대값
    rag_similarity_threshold = db.Column(db.Float, default=0.5)       # 유사도 임계값
    rag_gap_threshold = db.Column(db.Float, default=0.1)              # Gap-based 전략용 임계값

    # 관계
    system_prompts = db.relationship('PersonaSystemPrompt', backref='persona', cascade='all, delete-orphan', lazy='dynamic')
    knowledge_bases = db.relationship('PersonaKnowledgeBase', backref='persona', cascade='all, delete-orphan', lazy='dynamic')
    teacher_permissions = db.relationship('PersonaTeacherPermission', backref='persona', cascade='all, delete-orphan', lazy='dynamic')

# ---------------------------------------------------------
# [8] 페르소나 시스템 프롬프트(PersonaSystemPrompt) 모델
# ---------------------------------------------------------
class PersonaSystemPrompt(db.Model):
    """
    페르소나별 AI 공급사별 시스템 프롬프트를 저장합니다.
    교사가 웹에서 프롬프트를 수정할 수 있습니다.
    """
    __tablename__ = 'persona_system_prompt'

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_definition.id', ondelete='CASCADE'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)              # 'default', 'openai', 'anthropic', 'google'
    system_prompt = db.Column(db.Text, nullable=False)
    updated_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('persona_id', 'provider', name='_persona_provider_uc'),)

# ---------------------------------------------------------
# [9] 교사 권한(PersonaTeacherPermission) 모델
# ---------------------------------------------------------
class PersonaTeacherPermission(db.Model):
    """
    특정 페르소나의 관리 권한을 특정 교사에게 부여합니다.
    """
    __tablename__ = 'persona_teacher_permission'

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_definition.id', ondelete='CASCADE'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    can_edit_prompt = db.Column(db.Boolean, default=True)
    can_manage_knowledge = db.Column(db.Boolean, default=True)
    can_view_analytics = db.Column(db.Boolean, default=True)
    granted_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    granted_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('persona_id', 'teacher_id', name='_persona_teacher_uc'),)

# ---------------------------------------------------------
# [10] 지식 베이스(PersonaKnowledgeBase) 모델
# ---------------------------------------------------------
class PersonaKnowledgeBase(db.Model):
    """
    페르소나별 지식 베이스 메타데이터를 저장합니다.
    하나의 페르소나는 여러 지식 베이스를 가질 수 있습니다.
    """
    __tablename__ = 'persona_knowledge_base'

    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_definition.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(255), nullable=False)                 # 예: "확률과 통계 교재"
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    chunk_strategy = db.Column(db.String(50), default='paragraph')   # 청킹 전략
    chunk_size = db.Column(db.Integer, default=500)
    chunk_overlap = db.Column(db.Integer, default=100)

    # 관계
    documents = db.relationship('KnowledgeDocument', backref='knowledge_base', cascade='all, delete-orphan', lazy='dynamic')

# ---------------------------------------------------------
# [11] 지식 문서(KnowledgeDocument) 모델
# ---------------------------------------------------------
class KnowledgeDocument(db.Model):
    """
    지식 베이스에 업로드된 문서 정보를 저장합니다.
    """
    __tablename__ = 'knowledge_document'

    id = db.Column(db.Integer, primary_key=True)
    knowledge_base_id = db.Column(db.Integer, db.ForeignKey('persona_knowledge_base.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512))
    file_type = db.Column(db.String(100))
    file_size = db.Column(db.BigInteger)
    content_hash = db.Column(db.String(64))                          # 중복 방지용
    extracted_text = db.Column(db.Text)
    chunk_count = db.Column(db.Integer, default=0)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    processed_at = db.Column(db.DateTime)
    processing_status = db.Column(db.String(20), default='pending')  # 'pending', 'processing', 'completed', 'failed'
    error_message = db.Column(db.Text)

    # 관계
    chunks = db.relationship('DocumentChunk', backref='document', cascade='all, delete-orphan', lazy='dynamic')

# ---------------------------------------------------------
# [12] 문서 청크(DocumentChunk) 모델 - 벡터 저장소
# ---------------------------------------------------------
class DocumentChunk(db.Model):
    """
    문서를 청킹한 결과와 임베딩 벡터를 저장합니다.
    pgvector를 사용하여 벡터 검색을 수행합니다.
    """
    __tablename__ = 'document_chunk'

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('knowledge_document.id', ondelete='CASCADE'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_length = db.Column(db.Integer)
    # pgvector의 vector 타입 사용 (1536차원 - OpenAI text-embedding-3-small)
    embedding = db.Column(Vector(1536))  # pgvector 전용 타입
    chunk_metadata = db.Column(db.JSON)  # 페이지 번호 등 추가 정보
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)