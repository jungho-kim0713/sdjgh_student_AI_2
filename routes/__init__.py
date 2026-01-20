from routes.auth import auth_bp
from routes.chat import chat_bp
from routes.files import files_bp
from routes.admin import admin_bp
from routes.status import status_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(status_bp)
