from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from extensions import db
from models import SystemConfig

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/get_status", methods=["GET"])
def get_status():
    st = SystemConfig.query.filter_by(key="service_status").first()
    return jsonify({"status": st.value if st else "active"})


@status_bp.route("/api/toggle_status", methods=["POST"])
@login_required
def toggle_status():
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403
    st = SystemConfig.query.filter_by(key="service_status").first()
    if not st:
        st = SystemConfig(key="service_status", value="inactive")
        db.session.add(st)
        new_val = "inactive"
    else:
        new_val = "active" if st.value == "inactive" else "inactive"
        st.value = new_val
    db.session.commit()
    return jsonify({"status": new_val})


@status_bp.route("/api/get_provider_status", methods=["GET"])
def get_provider_status():
    providers = ["openai", "anthropic", "google"]
    status = {}
    for p in providers:
        conf = SystemConfig.query.filter_by(key=f"provider_status_{p}").first()
        if not conf:
            conf = SystemConfig(key=f"provider_status_{p}", value="active")
            db.session.add(conf)
            db.session.commit()
        status[p] = conf.value
    return jsonify(status)


@status_bp.route("/api/admin/toggle_provider_status", methods=["POST"])
@login_required
def toggle_provider_status():
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403
    data = request.json
    provider = data.get("provider")

    conf = SystemConfig.query.filter_by(key=f"provider_status_{provider}").first()
    if conf:
        conf.value = "restricted" if conf.value == "active" else "active"
        db.session.commit()
        return jsonify({"success": True, "provider": provider, "status": conf.value})
    return jsonify({"error": "Provider not found"}), 404
