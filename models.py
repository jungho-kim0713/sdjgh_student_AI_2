from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
from extensions import db

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
    """
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50), nullable=False)

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