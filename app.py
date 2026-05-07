"""
Flask 애플리케이션 엔트리 파일.
설정/확장 초기화, 블루프린트 등록, 기본 초기 데이터 시딩만 담당한다.
"""

import os
import datetime

try:
    import gevent.monkey
    gevent.monkey.patch_all()
    import psycogreen.gevent
    psycogreen.gevent.patch_psycopg()
except ImportError:
    pass

import certifi
from sqlalchemy import inspect, text
from flask import Flask, jsonify, request, send_from_directory, redirect
from dotenv import load_dotenv

from extensions import db, login_manager, cache
from models import User, SystemConfig, PersonaConfig, PersonaDefinition
from prompts import AI_PERSONAS

# Windows/서버 환경에서 SSL 인증서 경로를 강제로 지정해 오류를 예방한다.
os.environ["SSL_CERT_FILE"] = certifi.where()

# .env 값을 로딩해 API 키/DB 정보 등을 환경변수로 사용한다.
load_dotenv()

# 내부 의존(서비스/라우트)은 환경 초기화 이후에 가져온다.
from services.ai_service import DEFAULT_MODELS, DEFAULT_MAX_TOKENS
from routes import register_blueprints
from routes.auth import init_oauth
from werkzeug.middleware.proxy_fix import ProxyFix

# Flask 앱 인스턴스 생성(정적/템플릿 경로 지정)
app = Flask(__name__, static_folder="static", template_folder="templates")
# [ProxyFix] 리버스 프록시(Nginx/Cloudflare) 환경에서 HTTPS 및 실제 IP를 인식하도록 설정
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# OAuth 초기화
init_oauth(app)


@app.route('/service-worker.js')
def service_worker():
    """서비스 워커를 루트 스코프(/)에서 서빙한다."""
    resp = send_from_directory('static', 'service-worker.js',
                               mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/manifest.json')
def pwa_manifest():
    """PWA manifest를 루트에서 서빙한다."""
    return send_from_directory('static', 'manifest.json',
                               mimetype='application/manifest+json')


@app.after_request
def add_security_headers(response):
    """모든 응답에 CSP 보안 헤더를 주입한다."""
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://generativelanguage.googleapis.com https://api.openai.com https://api.anthropic.com https://cloudflareinsights.com;"
    )
    response.headers["Content-Security-Policy"] = csp
    
    # [보안] 업로드된 일반 파일 접근 시 강제 다운로드 처리 (XSS 방어)
    if request.path.startswith('/static/uploads/files/'):
        response.headers['Content-Disposition'] = 'attachment'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
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
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_size": 8,         # 워커(8)당 상시 유지 연결 수 (총 ~80개)
    "max_overflow": 8,      # 초과 시 추가 연결 (총 최대 ~160개, PostgreSQL max_connections=200 이하)
    "pool_pre_ping": True,  # 사용 전 연결 유효성 확인 (DB 재시작 후 에러 방지)
    "pool_recycle": 3600,   # 1시간마다 연결 갱신 (좀비 연결 방지)
}
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
login_manager.login_message = ""

@login_manager.unauthorized_handler
def unauthorized():
    platform_url = os.environ.get("PLATFORM_URL", "https://platform.sdjgh-ai.kr/")
    return redirect(platform_url)

# Cache 설정 (CELERY_BROKER_URL이 설정된 경우에만 Redis 사용, 미설정 시 로컬 SimpleCache)
_celery_broker = os.environ.get("CELERY_BROKER_URL")
if _celery_broker:
    _redis_base = _celery_broker.rsplit("/", 1)[0]
    app.config["CACHE_TYPE"] = "RedisCache"
    app.config["CACHE_REDIS_URL"] = f"{_redis_base}/1"
else:
    app.config["CACHE_TYPE"] = "SimpleCache"
app.config["CACHE_DEFAULT_TIMEOUT"] = 60
cache.init_app(app)

# Celery 초기화 (RAG 백그라운드 작업용)
from tasks import init_celery
celery = init_celery(app)


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
        ensure_column("persona_config", "allow_user", "allow_user BOOLEAN DEFAULT TRUE")
        ensure_column("persona_config", "allow_teacher", "allow_teacher BOOLEAN DEFAULT TRUE")
        ensure_column("persona_config", "restrict_google", "restrict_google BOOLEAN DEFAULT FALSE")
        ensure_column("persona_config", "restrict_anthropic", "restrict_anthropic BOOLEAN DEFAULT FALSE")
        ensure_column("persona_config", "restrict_openai", "restrict_openai BOOLEAN DEFAULT FALSE")
        ensure_column("persona_config", "restrict_xai", "restrict_xai BOOLEAN DEFAULT FALSE")
        ensure_column("persona_config", "model_xai", "model_xai VARCHAR(100) DEFAULT 'grok-4-1-fast-reasoning'")
        ensure_column("persona_definition", "restrict_xai", "restrict_xai BOOLEAN DEFAULT FALSE")
        ensure_column("persona_definition", "model_xai", "model_xai VARCHAR(100) DEFAULT 'grok-4-1-fast-reasoning'")
        ensure_column("persona_definition", "sort_order", "sort_order INTEGER DEFAULT 0")

        # 새 컬럼 기본값 보정(기존 레코드).
        with db.engine.begin() as conn:
            conn.execute(text('UPDATE "user" SET role=\'user\' WHERE role IS NULL'))
            conn.execute(text("UPDATE persona_config SET allow_user=TRUE WHERE allow_user IS NULL"))
            conn.execute(text("UPDATE persona_config SET allow_teacher=TRUE WHERE allow_teacher IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_google=FALSE WHERE restrict_google IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_anthropic=FALSE WHERE restrict_anthropic IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_openai=FALSE WHERE restrict_openai IS NULL"))
            conn.execute(text("UPDATE persona_config SET restrict_xai=FALSE WHERE restrict_xai IS NULL"))
            conn.execute(text("UPDATE persona_config SET model_xai='grok-4-1-fast-reasoning' WHERE model_xai IS NULL"))
            conn.execute(text("UPDATE persona_definition SET restrict_xai=FALSE WHERE restrict_xai IS NULL"))
            conn.execute(text("UPDATE persona_definition SET model_xai='grok-4-1-fast-reasoning' WHERE model_xai IS NULL"))
            # sort_order가 0인 기존 레코드를 id 순서로 초기화
            conn.execute(text("UPDATE persona_definition SET sort_order=id WHERE sort_order=0 OR sort_order IS NULL"))
            # ai_illustrator, general 외 나머지 기본 페르소나의 is_system 해제
            conn.execute(text(
                "UPDATE persona_definition SET is_system=FALSE "
                "WHERE role_key NOT IN ('ai_illustrator', 'general') AND is_system=TRUE"
            ))
        # 서비스 상태 기본값 시딩
        if not SystemConfig.query.filter_by(key="service_status").first():
            db.session.add(SystemConfig(key="service_status", value="active"))

        # 공급사별 제한 상태 기본값 시딩
        for provider in ["openai", "anthropic", "google", "xai"]:
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
                        model_xai=DEFAULT_MODELS.get("xai", "grok-4-1-fast-reasoning"),
                        max_tokens=DEFAULT_MAX_TOKENS,
                    )
                )
        db.session.commit()
        
        # ----------------------------------------------------
        # 기본 페르소나 자동 복구(Auto-Seed)
        # ----------------------------------------------------
        # 사용자가 chatbot.db 파일을 윈도우에서 직접 삭제하여 DB가 초기화될 경우
        # 기본 제공 페르소나 5개가 날아가는 것을 방지하기 위해 
        # 페르소나 테이블이 비어있다면 자동 1회 파종(결실)을 거칩니다.
        if PersonaDefinition.query.count() == 0:
            print("INFO: 페르소나 테이블이 비어 있습니다. 기본 5개 페르소나를 자동 생성합니다.")
            from migrations.seed_personas import seed_personas
            seed_personas()
            
    except Exception as e:
        print(f"DB Initialization Error: {e}")



# 모든 블루프린트 등록(라우트는 routes/ 하위 모듈에만 존재)
register_blueprints(app)


if __name__ == "__main__":
    # 개발용 로컬 실행 엔트리
    app.run(debug=True, host="0.0.0.0", port=8081)