from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import os
import json
import psutil
from datetime import datetime, timezone

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


# ========================================================================
# 공급사 모델 설정 API
# ========================================================================

@status_bp.route("/api/admin/available_models/<provider>", methods=["GET"])
@login_required
def get_available_models(provider):
    """특정 공급사의 사용 가능한 모든 모델 리스트 조회 (메타데이터 포함).

    Args:
        provider: "openai" | "anthropic" | "google"

    Returns:
        {
            "provider": "openai",
            "models": [
                {
                    "id": "gpt-4o",
                    "name": "GPT-4o (Omni)",
                    "input_price": 5.00,
                    "output_price": 15.00,
                    "description": "Most capable OpenAI model for complex tasks"
                },
                ...
            ]
        }
    """
    if not current_user.is_admin:
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403

    try:
        # AVAILABLE_MODELS와 초기화된 클라이언트 가져오기
        from services.ai_service import AVAILABLE_MODELS, openai_client, anthropic_client

        if provider == "openai":
            api_models_data = []
            
            # 1. API 호출 시도
            if openai_client:
                try:
                    models_list = openai_client.models.list()
                    for model in models_list:
                         api_models_data.append(model.id)
                except Exception as e:
                    print(f"[WARNING] OpenAI API calls failed: {e}")
            
            # 2. AVAILABLE_MODELS에서 필터링 (Fallback)
            available = []
            # API 호출이 성공했으면 API에 있는 것만, 실패했거나 키가 없으면 전체 목록 표시
            use_api_filter = len(api_models_data) > 0
            
            for model_id, metadata in AVAILABLE_MODELS.items():
                if metadata["provider"] == "openai":
                    # API 호출에 성공했다면, 실제로 존재하는 모델인지 확인 (옵션)
                    # 여기서는 '화이트리스트' 개념이므로 AVAILABLE_MODELS에 있는 것만 보여줌.
                    # 단, API가 살아있는데 API 목록에 없다면(deprecated 등) 제외할 수도 있음.
                    # 안전을 위해: API가 죽었으면 무조건 보여주고, 살았으면 교차 검증?
                    # 사용자 요구사항: "에러 안 나게". -> 그냥 무조건 AVAILABLE_MODELS 뿌려도 됨.
                    # 하지만 '실제 사용 가능 여부'를 체크하는 원래 의도를 살리기 위해:
                    # keys가 없으면 -> 다 보여줌.
                    # keys가 있으면 -> API 리스트에 있는 것만 보여줌?
                    # -> API 키가 있어도 쿼터 초과 등으로 실패하면 다 보여주는게 안전함.
                    
                    available.append({
                        "id": model_id,
                        "name": metadata["name"],
                        "input_price": metadata["input_price"],
                        "output_price": metadata["output_price"],
                        "description": metadata["description"]
                    })

            return jsonify({"provider": provider, "models": available})

        elif provider == "anthropic":
            api_models_data = []

            if anthropic_client:
                try:
                    models_page = anthropic_client.models.list()
                    for model in models_page:
                        api_models_data.append(model.id)
                except Exception as e:
                    print(f"[WARNING] Anthropic API calls failed: {e}")

            available = []
            for model_id, metadata in AVAILABLE_MODELS.items():
                if metadata["provider"] == "anthropic":
                    available.append({
                        "id": model_id,
                        "name": metadata["name"],
                        "input_price": metadata["input_price"],
                        "output_price": metadata["output_price"],
                        "description": metadata["description"]
                    })

            return jsonify({"provider": provider, "models": available})

        elif provider == "google":
            api_models_data = []
            
            import google.generativeai as genai
            api_key = os.getenv("GOOGLE_API_KEY")
            
            if api_key:
                try:
                    genai.configure(api_key=api_key)
                    for model in genai.list_models():
                        if 'generateContent' in model.supported_generation_methods:
                            model_id = model.name.replace('models/', '')
                            api_models_data.append(model_id)
                except Exception as e:
                    print(f"[WARNING] Google API calls failed: {e}")

            available = []
            for model_id, metadata in AVAILABLE_MODELS.items():
                if metadata["provider"] == "google":
                    available.append({
                        "id": model_id,
                        "name": metadata["name"],
                        "input_price": metadata["input_price"],
                        "output_price": metadata["output_price"],
                        "description": metadata["description"]
                    })

            return jsonify({"provider": provider, "models": available})

        else:
            return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    except Exception as e:
        return jsonify({"error": f"모델 조회 실패: {str(e)}"}), 500


@status_bp.route("/api/admin/enabled_models", methods=["POST"])
@login_required
def save_enabled_models():
    """활성화할 모델 리스트 저장.

    Request Body:
        {
            "provider": "openai",
            "enabled_models": ["gpt-4o", "gpt-4o-mini"]
        }
    """
    if not current_user.is_admin:
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403

    data = request.json or {}
    provider = data.get("provider")
    enabled_models = data.get("enabled_models", [])

    if provider not in ["openai", "anthropic", "google"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    # SystemConfig에서 해당 키 찾기 또는 생성
    key = f"enabled_models_{provider}"
    conf = SystemConfig.query.filter_by(key=key).first()

    if not conf:
        conf = SystemConfig(key=key, value=json.dumps(enabled_models))
        db.session.add(conf)
    else:
        conf.value = json.dumps(enabled_models)

    db.session.commit()

    return jsonify({
        "success": True,
        "provider": provider,
        "enabled_models": enabled_models
    })


@status_bp.route("/api/admin/enabled_models", methods=["GET"])
def get_enabled_models():
    """모든 공급사의 활성화된 모델 리스트 조회.

    Returns:
        {
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"],
            "google": ["gemini-2.0-flash", "gemini-3-flash-preview"]
        }
    """
    providers = ["openai", "anthropic", "google"]
    enabled_models = {}

    for provider in providers:
        key = f"enabled_models_{provider}"
        conf = SystemConfig.query.filter_by(key=key).first()

        if conf:
            try:
                enabled_models[provider] = json.loads(conf.value)
            except json.JSONDecodeError:
                enabled_models[provider] = []
        else:
            # 레코드가 없으면 기본값 사용
            default_models = {
                "openai": ["gpt-4.1-mini", "gpt-5-mini"],
                "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"],
                "google": ["gemini-3-flash-preview", "gemini-2.5-flash"]
            }
            enabled_models[provider] = default_models.get(provider, [])

    return jsonify(enabled_models)


@status_bp.route("/api/admin/enabled_models/<provider>", methods=["GET"])
def get_enabled_models_by_provider(provider):
    """특정 공급사의 활성화된 모델 리스트 조회.

    Returns:
        {
            "provider": "openai",
            "enabled_models": ["gpt-4o", "gpt-4o-mini"]
        }
    """
    if provider not in ["openai", "anthropic", "google"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    key = f"enabled_models_{provider}"
    conf = SystemConfig.query.filter_by(key=key).first()

    if conf:
        try:
            enabled_models = json.loads(conf.value)
        except json.JSONDecodeError:
            enabled_models = []
    else:
        # 기본값
        default_models = {
            "openai": ["gpt-4o-mini", "gpt-4o"],
            "anthropic": ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"],
            "google": ["gemini-3-flash-preview", "gemini-2.5-flash"]
        }
        enabled_models = default_models.get(provider, [])

    return jsonify({
        "provider": provider,
        "enabled_models": enabled_models
    })


@status_bp.route("/api/admin/model_order", methods=["POST"])
@login_required
def save_model_order():
    """모델 표시 순서 저장.

    Request Body:
        {
            "provider": "openai",
            "model_order": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
        }
    """
    if not current_user.is_admin:
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403

    data = request.json or {}
    provider = data.get("provider")
    model_order = data.get("model_order", [])

    if provider not in ["openai", "anthropic", "google"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    key = f"model_order_{provider}"
    conf = SystemConfig.query.filter_by(key=key).first()

    if not conf:
        conf = SystemConfig(key=key, value=json.dumps(model_order))
        db.session.add(conf)
    else:
        conf.value = json.dumps(model_order)

    db.session.commit()

    return jsonify({
        "success": True,
        "provider": provider,
        "model_order": model_order
    })


@status_bp.route("/api/admin/model_order/<provider>", methods=["GET"])
def get_model_order(provider):
    """특정 공급사의 모델 표시 순서 조회.

    Returns:
        {
            "provider": "openai",
            "model_order": ["gpt-4o", "gpt-4o-mini"]
        }
    """
    if provider not in ["openai", "anthropic", "google"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    key = f"model_order_{provider}"
    conf = SystemConfig.query.filter_by(key=key).first()

    if conf:
        try:
            model_order = json.loads(conf.value)
        except json.JSONDecodeError:
            model_order = []
    else:
        # 기본값: enabled_models와 동일
        enabled_key = f"enabled_models_{provider}"
        enabled_conf = SystemConfig.query.filter_by(key=enabled_key).first()
        if enabled_conf:
            try:
                model_order = json.loads(enabled_conf.value)
            except json.JSONDecodeError:
                model_order = []
        else:
            model_order = []

    return jsonify({
        "provider": provider,
        "model_order": model_order
    })


@status_bp.route("/api/admin/refresh_models/<provider>", methods=["POST"])
@login_required
def refresh_models(provider):
    """특정 공급사의 모델 리스트를 수동으로 새로고침.

    Returns:
        {
            "success": True,
            "provider": "openai",
            "new_models": ["gpt-5"],  # 새로 발견된 모델
            "updated_at": "2026-02-16T10:30:00Z"
        }
    """
    if not current_user.is_admin:
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403

    if provider not in ["openai", "anthropic", "google"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    try:
        # 초기화된 클라이언트 가져오기
        from services.ai_service import openai_client, anthropic_client, AVAILABLE_MODELS

        # 1. 현재 활성화된 모델 조회
        enabled_key = f"enabled_models_{provider}"
        enabled_conf = SystemConfig.query.filter_by(key=enabled_key).first()
        enabled_models = json.loads(enabled_conf.value) if enabled_conf else []

        # 2. API에서 최신 모델 리스트 가져오기
        api_models = []

        if provider == "openai":
            if openai_client:
                models_list = openai_client.models.list()
                api_models = [m.id for m in models_list if m.id.startswith("gpt")]

        elif provider == "anthropic":
            if anthropic_client:
                # Anthropic API로 모델 리스트 조회
                models_page = anthropic_client.models.list()
                api_models = [m.id for m in models_page]

        elif provider == "google":
            import google.generativeai as genai
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                api_models = [
                    m.name.replace('models/', '')
                    for m in genai.list_models()
                    if 'generateContent' in m.supported_generation_methods
                ]

        # 3. 새로운 모델 감지
        new_models = [m for m in api_models if m not in enabled_models]

        # 4. 마지막 업데이트 시간 기록
        update_key = f"last_model_update_{provider}"
        update_conf = SystemConfig.query.filter_by(key=update_key).first()
        updated_at = datetime.now(timezone.utc).isoformat()

        if not update_conf:
            update_conf = SystemConfig(key=update_key, value=updated_at)
            db.session.add(update_conf)
        else:
            update_conf.value = updated_at

        db.session.commit()

        return jsonify({
            "success": True,
            "provider": provider,
            "new_models": new_models,
            "updated_at": updated_at
        })

    except Exception as e:
        return jsonify({"error": f"모델 새로고침 실패: {str(e)}"}), 500


@status_bp.route("/api/admin/system_config/<key>", methods=["GET"])
def get_system_config(key):
    """특정 SystemConfig 키의 값 조회.

    Args:
        key: SystemConfig 키 (예: "last_model_update_openai")

    Returns:
        {
            "key": "last_model_update_openai",
            "value": "2026-02-16T10:30:00Z"
        }
    """
    conf = SystemConfig.query.filter_by(key=key).first()

    if conf:
        return jsonify({"key": key, "value": conf.value})
    else:
        return jsonify({"error": "설정을 찾을 수 없습니다."}), 404
