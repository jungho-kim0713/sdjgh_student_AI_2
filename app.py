"""
Flask 애플리케이션 엔트리 파일.
설정/확장 초기화, 블루프린트 등록, 기본 초기 데이터 시딩만 담당한다.
"""

import os
import datetime

import certifi
from sqlalchemy import inspect, text
from flask import Flask, jsonify
from dotenv import load_dotenv

from extensions import db, login_manager
from models import User, SystemConfig, PersonaConfig
from prompts import AI_PERSONAS

# Windows/서버 환경에서 SSL 인증서 경로를 강제로 지정해 오류를 예방한다.
os.environ["SSL_CERT_FILE"] = certifi.where()

# .env 값을 로딩해 API 키/DB 정보 등을 환경변수로 사용한다.
load_dotenv()

# 내부 의존(서비스/라우트)은 환경 초기화 이후에 가져온다.
from services.ai_service import DEFAULT_MODELS, DEFAULT_MAX_TOKENS
from routes import register_blueprints
from routes.auth import init_oauth

# Flask 앱 인스턴스 생성(정적/템플릿 경로 지정)
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# OAuth 초기화
init_oauth(app)


@app.after_request
def add_security_headers(response):
    """모든 응답에 CSP 보안 헤더를 주입한다."""
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://generativelanguage.googleapis.com https://api.openai.com https://api.anthropic.com https://cloudflareinsights.com;"
    )
    response.headers["Content-Security-Policy"] = csp
    return response


# DB 연결 정보(없으면 로컬 SQLite로 폴백)
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_HOST = os.environ.get("DB_HOST")
DB_NAME = os.environ.get("DB_NAME")

if DB_HOST and DB_USER and DB_PASS and DB_NAME:
    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}"
    )
    print(f"INFO: PostgreSQL({DB_HOST})에 연결합니다.")
else:
    print("INFO: DB 환경 변수가 감지되지 않아 '로컬 SQLite(chatbot.db)'를 사용합니다.")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chatbot.db"

# SQLAlchemy 추적/시크릿키 설정
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "default-dev-secret-key")

# 업로드 경로 구성 및 기본 폴더 생성
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(os.path.join(UPLOAD_FOLDER, "files")):
    os.makedirs(os.path.join(UPLOAD_FOLDER, "files"))

# Flask 확장 초기화
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login이 사용자 세션을 복원할 때 호출된다."""
    return User.query.get(int(user_id))


@app.context_processor
def inject_version():
    """템플릿 캐시 방지를 위한 버전 문자열을 주입한다."""
    return dict(version=datetime.datetime.now().strftime("%Y%m%d%H%M%S"))


@app.errorhandler(413)
def too_large(e):
    """업로드 용량 초과(413) 응답을 JSON으로 통일한다."""
    return jsonify({"error": "File too large (Max 100MB)"}), 413


with app.app_context():
    # 앱 최초 구동 시 필요한 기본 레코드를 채운다.
    try:
        db.create_all()
        # 기존 DB에 새 컬럼이 없으면 추가한다.
        inspector = inspect(db.engine)

        def ensure_column(table_name, column_name, ddl):
            columns = [col["name"] for col in inspector.get_columns(table_name)]
            if column_name in columns:
                return
            with db.engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))

        ensure_column("user", "role", "role VARCHAR(20) DEFAULT 'user'")
        ensure_column("persona_config", "allow_user", "allow_user BOOLEAN DEFAULT 1")
        ensure_column("persona_config", "allow_teacher", "allow_teacher BOOLEAN DEFAULT 1")
        ensure_column("persona_config", "restrict_google", "restrict_google BOOLEAN DEFAULT 0")
        ensure_column("persona_config", "restrict_anthropic", "restrict_anthropic BOOLEAN DEFAULT 0")
        ensure_column("persona_config", "restrict_openai", "restrict_openai BOOLEAN DEFAULT 0")

        # 새 컬럼 기본값 보정(기존 레코드).
        with db.engine.begin() as conn:
            conn.execute(text("UPDATE user SET role='user' WHERE role IS NULL"))
            conn.execute(text("UPDATE persona_config SET allow_user=1 WHERE allow_user IS NULL"))
            conn.execute(text("UPDATE persona_config SET allow_teacher=1 WHERE allow_teacher IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_google=0 WHERE restrict_google IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_anthropic=0 WHERE restrict_anthropic IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_openai=0 WHERE restrict_openai IS NULL"))
        # 서비스 상태 기본값 시딩
        if not SystemConfig.query.filter_by(key="service_status").first():
            db.session.add(SystemConfig(key="service_status", value="active"))

        # 공급사별 제한 상태 기본값 시딩
        for provider in ["openai", "anthropic", "google"]:
            key = f"provider_status_{provider}"
            if not SystemConfig.query.filter_by(key=key).first():
                db.session.add(SystemConfig(key=key, value="active"))

        # 페르소나별 모델/토큰 기본값 시딩
        for role_key in AI_PERSONAS.keys():
            if not PersonaConfig.query.filter_by(role_key=role_key).first():
                db.session.add(
                    PersonaConfig(
                        role_key=role_key,
                        model_openai=DEFAULT_MODELS["openai"],
                        model_anthropic=DEFAULT_MODELS["anthropic"],
                        model_google=DEFAULT_MODELS["google"],
                        max_tokens=DEFAULT_MAX_TOKENS,
                    )
                )
        db.session.commit()
    except Exception:
        pass


# 모든 블루프린트 등록(라우트는 routes/ 하위 모듈에만 존재)
register_blueprints(app)


if __name__ == "__main__":
    # 개발용 로컬 실행 엔트리
    app.run(debug=True, host="0.0.0.0", port=5000)