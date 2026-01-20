import os
import datetime

from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from extensions import db
from models import User, ChatSession, Message, ChatFile, PersonaConfig
from prompts import AI_PERSONAS
from services.ai_service import DEFAULT_MODELS, DEFAULT_MAX_TOKENS, AVAILABLE_MODELS

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/api/admin/get_persona_config")
@login_required
def admin_get_persona_config():
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    configs = PersonaConfig.query.all()
    config_map = {c.role_key: c for c in configs}

    personas_data = []
    for key, p in AI_PERSONAS.items():
        c = config_map.get(key)
        personas_data.append(
            {
                "role_key": key,
                "role_name": p["role_name"],
                "model_openai": c.model_openai if c else DEFAULT_MODELS["openai"],
                "model_anthropic": c.model_anthropic if c else DEFAULT_MODELS["anthropic"],
                "model_google": c.model_google if c else DEFAULT_MODELS["google"],
                "max_tokens": c.max_tokens if c else DEFAULT_MAX_TOKENS,
            }
        )
    return jsonify({"personas": personas_data, "models": AVAILABLE_MODELS})


@admin_bp.route("/api/admin/update_persona_config", methods=["POST"])
@login_required
def admin_update_persona_config():
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    data = request.json
    role_key = data.get("role_key")

    conf = PersonaConfig.query.filter_by(role_key=role_key).first()
    if not conf:
        conf = PersonaConfig(role_key=role_key)
        db.session.add(conf)

    if data.get("model_openai"):
        conf.model_openai = data.get("model_openai")
    if data.get("model_anthropic"):
        conf.model_anthropic = data.get("model_anthropic")
    if data.get("model_google"):
        conf.model_google = data.get("model_google")

    if "max_tokens" in data:
        try:
            val = int(data["max_tokens"])
            conf.max_tokens = val
        except (ValueError, TypeError):
            pass

    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/admin/get_users")
@login_required
def admin_get_users():
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    return jsonify(
        [{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in User.query.all()]
    )


@admin_bp.route("/api/admin/delete_user", methods=["POST"])
@login_required
def admin_delete_user():
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    uid = request.json.get("user_id")
    if uid == current_user.id:
        return jsonify({"error": "Self delete"}), 400
    u = db.session.get(User, uid)
    if u:
        try:
            user_files = ChatFile.query.filter_by(user_id=uid).all()
            for f in user_files:
                try:
                    if f.file_type.startswith("image/"):
                        path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"],
                            os.path.basename(f.storage_path),
                        )
                    else:
                        path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"],
                            "files",
                            os.path.basename(f.storage_path),
                        )
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
                db.session.delete(f)

            Message.query.filter_by(user_id=uid).delete()
            ChatSession.query.filter_by(user_id=uid).delete()
            db.session.delete(u)
            db.session.commit()
            return jsonify({"success": True, "username": u.username})
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": f"Delete failed: {str(e)}"}), 500

    return jsonify({"error": "User not found"}), 404


@admin_bp.route("/api/admin/get_user_history/<int:user_id>", methods=["GET"])
@login_required
def admin_get_user_history(user_id):
    if not current_user.is_admin:
        return jsonify({"error": "Permission denied"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    sessions = (
        db.session.query(ChatSession.id, ChatSession.title, ChatSession.role_key, ChatSession.timestamp)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.timestamp.desc())
        .all()
    )
    role_names = {key: persona["role_name"] for key, persona in AI_PERSONAS.items()}
    history_list = [
        {
            "id": s.id,
            "title": s.title,
            "role_name": role_names.get(s.role_key, "알 수 없음"),
            "timestamp": s.timestamp.strftime("%Y-%m-%d %H:%M"),
        }
        for s in sessions
    ]
    return jsonify({"username": user.username, "history": history_list})


@admin_bp.route("/api/admin/cleanup_orphaned_files", methods=["POST"])
@login_required
def cleanup_orphaned_files():
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403

    try:
        cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        orphaned_files = ChatFile.query.filter(
            ChatFile.session_id == None, ChatFile.timestamp < cutoff_time
        ).all()

        deleted_count = 0
        cleaned_space_mb = 0.0

        for f in orphaned_files:
            try:
                if f.file_type and f.file_type.startswith("image/"):
                    path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], os.path.basename(f.storage_path)
                    )
                else:
                    path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"],
                        "files",
                        os.path.basename(f.storage_path),
                    )

                if not os.path.exists(path):
                    path = os.path.join(
                        current_app.static_folder, f.storage_path.replace("uploads/", "", 1)
                    )

                if os.path.exists(path):
                    file_size = os.path.getsize(path)
                    os.remove(path)
                    cleaned_space_mb += file_size
            except Exception as e:
                print(f"File delete error ({f.filename}): {e}")

            db.session.delete(f)
            deleted_count += 1

        db.session.commit()

        return jsonify(
            {
                "success": True,
                "count": deleted_count,
                "space_freed": round(cleaned_space_mb / (1024 * 1024), 2),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
