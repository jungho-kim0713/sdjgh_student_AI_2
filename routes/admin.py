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
    """관리자 전용: 페르소나별 모델/토큰/사용자 허용 설정 조회.

    - 권한: 관리자만 가능
    - 응답: 페르소나 리스트 + 사용 가능한 모델 목록
    """
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    configs = PersonaConfig.query.all()
    config_map = {c.role_key: c for c in configs}

    personas_data = []
    for key, p in AI_PERSONAS.items():
        # DB에 설정이 없으면 기본 모델/토큰을 사용
        c = config_map.get(key)
        personas_data.append(
            {
                "role_key": key,
                "role_name": p["role_name"],
                "model_openai": c.model_openai if c else DEFAULT_MODELS["openai"],
                "model_anthropic": c.model_anthropic if c else DEFAULT_MODELS["anthropic"],
                "model_google": c.model_google if c else DEFAULT_MODELS["google"],
                "max_tokens": c.max_tokens if c else DEFAULT_MAX_TOKENS,
                "allow_user": c.allow_user if c else True,
                "allow_teacher": c.allow_teacher if c else True,
                "restrict_google": c.restrict_google if c else False,
                "restrict_anthropic": c.restrict_anthropic if c else False,
                "restrict_openai": c.restrict_openai if c else False,
            }
        )
    return jsonify({"personas": personas_data, "models": AVAILABLE_MODELS})


@admin_bp.route("/api/admin/update_persona_config", methods=["POST"])
@login_required
def admin_update_persona_config():
    """관리자 전용: 페르소나별 모델/토큰/허용 역할 설정 저장.

    - 권한: 관리자만 가능
    - 입력: role_key + 변경할 필드(모델/토큰/allow_user/allow_teacher)
    - 출력: 저장 성공 여부
    """
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    data = request.json
    role_key = data.get("role_key")

    # 해당 페르소나 설정이 없으면 새로 생성
    conf = PersonaConfig.query.filter_by(role_key=role_key).first()
    if not conf:
        conf = PersonaConfig(role_key=role_key)
        db.session.add(conf)

    # 모델 설정 필드 업데이트(전달된 값만 반영)
    if data.get("model_openai"):
        conf.model_openai = data.get("model_openai")
    if data.get("model_anthropic"):
        conf.model_anthropic = data.get("model_anthropic")
    if data.get("model_google"):
        conf.model_google = data.get("model_google")

    # 토큰 입력은 숫자 변환 후 저장
    if "max_tokens" in data:
        try:
            val = int(data["max_tokens"])
            conf.max_tokens = val
        except (ValueError, TypeError):
            pass

    # 사용자 허용 여부 저장(불리언/문자열/숫자 입력 대응)
    if "allow_user" in data:
        val = data.get("allow_user")
        conf.allow_user = True if val in [True, "true", "True", 1, "1"] else False
    if "allow_teacher" in data:
        val = data.get("allow_teacher")
        conf.allow_teacher = True if val in [True, "true", "True", 1, "1"] else False

    if "restrict_google" in data:
        val = data.get("restrict_google")
        conf.restrict_google = True if val in [True, "true", "True", 1, "1"] else False
    if "restrict_anthropic" in data:
        val = data.get("restrict_anthropic")
        conf.restrict_anthropic = True if val in [True, "true", "True", 1, "1"] else False
    if "restrict_openai" in data:
        val = data.get("restrict_openai")
        conf.restrict_openai = True if val in [True, "true", "True", 1, "1"] else False

    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/api/admin/get_users")
@login_required
def admin_get_users():
    """관리자 전용: 사용자 목록 조회.

    - 권한: 관리자만 가능
    - 응답: id/username/is_admin/role 목록
    """
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    return jsonify(
        [
            {"id": u.id, "username": u.username, "is_admin": u.is_admin, "role": u.role}
            for u in User.query.all()
        ]
    )


@admin_bp.route("/api/admin/update_user_role", methods=["POST"])
@login_required
def admin_update_user_role():
    """관리자 전용: 사용자 역할(user/teacher) 변경.

    - 권한: 관리자만 가능
    - 입력: user_id, role(user|teacher)
    - 응답: 변경 결과
    """
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    data = request.json or {}
    user_id = data.get("user_id")
    new_role = data.get("role")
    if new_role not in ["user", "teacher"]:
        return jsonify({"error": "Invalid role"}), 400
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.role = new_role
    db.session.commit()
    return jsonify({"success": True, "user_id": user_id, "role": new_role})


@admin_bp.route("/api/admin/delete_user", methods=["POST"])
@login_required
def admin_delete_user():
    """관리자 전용: 사용자 삭제(대화/파일 포함).

    - 권한: 관리자만 가능
    - 입력: user_id
    - 동작: 파일 삭제 → 메시지/세션 삭제 → 사용자 삭제
    """
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    uid = request.json.get("user_id")
    if uid == current_user.id:
        return jsonify({"error": "Self delete"}), 400
    u = db.session.get(User, uid)
    if u:
        try:
            # 사용자가 올린 파일을 먼저 찾아 제거
            user_files = ChatFile.query.filter_by(user_id=uid).all()
            for f in user_files:
                try:
                    if f.file_type.startswith("image/"):
                        # 이미지 파일은 uploads 루트에 저장됨
                        path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"],
                            os.path.basename(f.storage_path),
                        )
                    else:
                        # 일반 파일은 uploads/files 폴더에 저장됨
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

            # 메시지/세션/사용자 레코드 삭제
            Message.query.filter_by(user_id=uid).delete()
            ChatSession.query.filter_by(user_id=uid).delete()
            db.session.delete(u)
            db.session.commit()
            return jsonify({"success": True, "username": u.username})
        except Exception as e:
            # 일부라도 실패하면 롤백
            db.session.rollback()
            return jsonify({"error": f"Delete failed: {str(e)}"}), 500

    return jsonify({"error": "User not found"}), 404


@admin_bp.route("/api/admin/get_user_history/<int:user_id>", methods=["GET"])
@login_required
def admin_get_user_history(user_id):
    """관리자 전용: 특정 사용자의 대화 기록 목록 조회.

    - 권한: 관리자만 가능
    - 입력: user_id (path param)
    - 응답: 세션 메타데이터 목록
    """
    if not current_user.is_admin:
        return jsonify({"error": "Permission denied"}), 403
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    # 세션 메타데이터만 조회하여 전달(메시지 본문은 제외)
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
    """관리자 전용: 고아 파일(세션 없음)을 정리.

    - 권한: 관리자만 가능
    - 기준: session_id가 없고, 1시간 이상 지난 파일
    - 응답: 삭제 개수/회수 용량
    """
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403

    try:
        # 안전을 위해 1시간 이상 지난 파일만 대상으로 함
        cutoff_time = datetime.datetime.utcnow() - datetime.timedelta(hours=1)
        orphaned_files = ChatFile.query.filter(
            ChatFile.session_id == None, ChatFile.timestamp < cutoff_time
        ).all()

        deleted_count = 0
        cleaned_space_mb = 0.0

        for f in orphaned_files:
            try:
                if f.file_type and f.file_type.startswith("image/"):
                    # 이미지 파일은 uploads 루트 경로
                    path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], os.path.basename(f.storage_path)
                    )
                else:
                    # 일반 파일은 uploads/files 하위 경로
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

            # 파일 레코드 삭제
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
        # 예외 발생 시 롤백 후 오류 반환
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
