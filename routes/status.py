from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from extensions import db
from models import SystemConfig

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/get_status", methods=["GET"])
def get_status():
    """서비스 상태 조회.

    - 권한: 비로그인 포함 누구나
    - 응답: status 값(active/inactive)
    """
    st = SystemConfig.query.filter_by(key="service_status").first()
    return jsonify({"status": st.value if st else "active"})


@status_bp.route("/api/toggle_status", methods=["POST"])
@login_required
def toggle_status():
    """서비스 상태 토글(관리자 전용).

    - 권한: 관리자
    - 동작: active ↔ inactive 전환
    """
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
    """공급사 제한 상태 조회.

    - 권한: 비로그인 포함 누구나
    - 동작: 상태 레코드가 없으면 기본값(active)으로 생성
    """
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
    """공급사 제한 상태 토글(관리자 전용).

    - 권한: 관리자
    - 입력: provider
    - 동작: active ↔ restricted 전환
    """
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


@status_bp.route("/api/admin/set_provider_status", methods=["POST"])
@login_required
def set_provider_status():
    """공급사 제한 상태 직접 설정(관리자 전용).

    - 권한: 관리자
    - 입력: provider, status(active|restricted)
    - 응답: 변경 결과
    """
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403
    data = request.json or {}
    provider = data.get("provider")
    status = data.get("status")
    if status not in ["active", "restricted"]:
        return jsonify({"error": "Invalid status"}), 400
    conf = SystemConfig.query.filter_by(key=f"provider_status_{provider}").first()
    if conf:
        conf.value = status
        db.session.commit()
        return jsonify({"success": True, "provider": provider, "status": conf.value})
    return jsonify({"error": "Provider not found"}), 404
