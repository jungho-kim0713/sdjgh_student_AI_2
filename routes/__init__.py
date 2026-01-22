"""라우트 블루프린트 등록 모듈.

여기서 모든 하위 routes 모듈의 블루프린트를 불러오고
Flask 앱에 한 번에 등록한다.
"""

from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.files import files_bp
from routes.admin import admin_bp
from routes.status import status_bp


def register_blueprints(app):
    """앱에 모든 블루프린트를 등록한다.

    호출 위치: app.py 초기화 단계
    - 인증/채팅/파일/관리자/상태 관련 라우트가 활성화됨
    """
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(status_bp)
