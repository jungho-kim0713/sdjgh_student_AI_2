from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import os
import json
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
    providers = ["openai", "anthropic", "google", "xai"]
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
        # 1. DB에서 동적으로 저장된 모델 메타데이터 확인 (새로고침 기능 사용 후)
        metadata_key = f"available_models_metadata_{provider}"
        metadata_conf = SystemConfig.query.filter_by(key=metadata_key).first()
        
        if metadata_conf:
            try:
                available = json.loads(metadata_conf.value)
                return jsonify({"provider": provider, "models": available})
            except Exception as e:
                print(f"[WARNING] 메타데이터 JSON 로딩 실패: {e}")

        # 2. DB에 없다면 Fallback (로컬 AVAILABLE_MODELS 정적 데이터 리턴)
        from services.ai_service import AVAILABLE_MODELS
        available = []
        for model_id, metadata in AVAILABLE_MODELS.items():
            if metadata["provider"] == provider:
                available.append({
                    "id": model_id,
                    "name": metadata["name"],
                    "input_price": metadata["input_price"],
                    "output_price": metadata["output_price"],
                    "description": metadata["description"]
                })

        return jsonify({"provider": provider, "models": available})

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

    if provider not in ["openai", "anthropic", "google", "xai"]:
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
    providers = ["openai", "anthropic", "google", "xai"]
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
                "google": ["gemini-3-flash-preview", "gemini-2.5-flash"],
                "xai": ["grok-4-1-fast-reasoning", "grok-imagine-image"]
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
    if provider not in ["openai", "anthropic", "google", "xai"]:
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
            "google": ["gemini-3-flash-preview", "gemini-2.5-flash"],
            "xai": ["grok-4-1-fast-reasoning"]
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

    if provider not in ["openai", "anthropic", "google", "xai"]:
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
    if provider not in ["openai", "anthropic", "google", "xai"]:
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


def generate_model_metadata_via_claude(provider, model_list):
    """Claude API를 이용해 모델을 최신순으로 정렬하고 메타데이터(설명/가격) JSON을 생성합니다."""
    from services.ai_service import get_anthropic_client
    client = get_anthropic_client()
    if not client:
        return None

    import traceback
    
    all_metadata = []
    chunk_size = 50  # 15에서 50으로 증가시켜 API 호출 횟수를 줄이고 504 Timeout 방지
    
    # 모델 리스트를 chunk_size 단위로 나눔
    for i in range(0, len(model_list), chunk_size):
        chunk = model_list[i:i + chunk_size]
        
        prompt = f"""
다음은 {provider} 공급사에서 제공하는 AI 모델 ID 전체 목록의 일부({i+1}~{i+len(chunk)}번째)입니다:
{json.dumps(chunk)}

요구사항:
0. 중요! 절대 모델 목록 중 일부를 생략하지 말고, 제공된 모델 ID {len(chunk)}개를 하나도 빠짐없이 모두 결과에 포함하세요.
1. 각 모델의 특징과 용도(description)를 1줄 이내로 아주 짧게 요약하세요.
2. 2024~2025년 기준 대략적인 API 100만 토큰당 입력(input)과 출력(output) 예상 비용(USD)을 추정하여 숫자로 적어주세요.
3. 반드시 다음 JSON 배열 형식으로만 응답하고, 마크다운 코드블록 등 다른 설명 텍스트는 일체 생략하세요.

형식:
[
  {{
    "id": "모델ID",
    "name": "일반인이 알아보기 쉬운 모델명",
    "input_price": 5.0,
    "output_price": 15.0,
    "description": "다목적 추론에 최적화된 최신 모델입니다."
  }},
  ...
]
"""
        try:
            available_claude_models = [m.id for m in client.models.list()]
            claude_model = next((m for m in available_claude_models if "sonnet" in m), available_claude_models[0] if available_claude_models else "claude-3-5-sonnet-20240620")
            
            response = client.messages.create(
                model=claude_model,
                max_tokens=4000,
                system="You are an AI assistant that only outputs strictly valid JSON arrays.",
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text.strip()
            import re
            json_pattern = re.compile(r'\[.*\]', re.DOTALL)
            match = json_pattern.search(text)
            if match:
                chunk_metadata = json.loads(match.group(0))
                all_metadata.extend(chunk_metadata)
            else:
                print("JSON Error: Claude response did not contain a valid array.")
                print("Raw Text:", text)
        except Exception as e:
            print(f"[Error generating metadata via Claude for chunk {i}-{i+len(chunk)}]: {e}")
            traceback.print_exc()
            
    # 전체 메타데이터가 생성되었으면 자체적으로 최신/고성능 순으로 간략하게 정렬
    # (Claude가 아닌 Python 레벨에서 정렬. 이름 및 id 길이 기준 등 간단한 휴리스틱)
    def sort_score(m):
        import re
        m_id = str(m.get("id", "")).lower()
        score = 0
        
        # 1. Family priority (lower is top)
        if "o3" in m_id: score -= 110
        elif "o1" in m_id: score -= 100
        elif "gpt-5" in m_id: score -= 98
        elif "gpt-4.5" in m_id: score -= 95
        elif "gpt-4o" in m_id: score -= 90
        elif "gpt-4-turbo" in m_id: score -= 80
        elif "gpt-4" in m_id: score -= 70
        elif "gpt-3.5" in m_id: score -= 50
        elif "gpt-" in m_id: score -= 60
        
        if "sonnet" in m_id: score -= 90
        elif "opus" in m_id: score -= 85
        elif "haiku" in m_id: score -= 75
        
        if "gemini-2.5" in m_id: score -= 90
        elif "gemini-1.5" in m_id: score -= 70
        elif "gemini-1.0" in m_id: score -= 50
        
        if "grok-4" in m_id: score -= 90
        elif "grok-3" in m_id: score -= 80
        elif "grok-2" in m_id: score -= 60
        elif "grok" in m_id: score -= 50
        
        # 2. Extract versions using regex to sort descending (negative float)
        nums = re.findall(r'\d+(?:\.\d+)?', m_id)
        num_score = 0
        if nums:
            try:
                num_score = -float(nums[0])
            except:
                pass
                
        # 3. Tie-breaker suffixes
        if "latest" in m_id: num_score -= 0.5
        if "preview" in m_id: num_score -= 0.2
        if "vision" in m_id: num_score += 0.1
        if "mini" in m_id or "flash" in m_id or "haiku" in m_id or "nano" in m_id: num_score += 0.2
        
        return (score, num_score, m_id)
        
    all_metadata.sort(key=sort_score)
    print(f"Successfully generated metadata for {len(all_metadata)} out of {len(model_list)} models")
    return all_metadata



@status_bp.route("/api/admin/refresh_models/<provider>", methods=["POST"])
@login_required
def refresh_models(provider):
    """특정 공급사의 모델 리스트를 API에서 새로고침하고 Claude로 메타데이터를 갱신합니다."""
    if not current_user.is_admin:
        return jsonify({"error": "관리자 권한이 필요합니다."}), 403

    if provider not in ["openai", "anthropic", "google", "xai"]:
        return jsonify({"error": "유효하지 않은 공급사입니다."}), 400

    try:
        from services.ai_service import get_openai_client, get_anthropic_client, get_xai_client
        
        # 1. 현재 활성화된 모델 (새 모델 비교용)
        enabled_key = f"enabled_models_{provider}"
        enabled_conf = SystemConfig.query.filter_by(key=enabled_key).first()
        enabled_models = json.loads(enabled_conf.value) if enabled_conf else []

        api_models = []

        if provider == "openai":
            openai_client = get_openai_client()
            if openai_client:
                models_list = openai_client.models.list()
                api_models = [m.id for m in models_list if m.id.startswith("gpt") or m.id.startswith("o1") or m.id.startswith("o3") or "dall-e" in m.id]
                
                # 504 Timeout 방지를 위한 2차 필터링: 구버전 스냅샷 등 파생 모델 제거
                exclude_patterns = ["-0301", "-0613", "-1106", "-0314", "-0409", "vision-preview", "instruct", "realtime", "audio"]
                api_models = [m for m in api_models if not any(p in m for p in exclude_patterns)]
                
                # 모델 수가 여전히 너무 많을 경우, 짧은 이름(Alias, 예: gpt-4o) 우선으로 최대 60개까지만 잘라서 Claude 호출 최소화
                # 단, AI 화가 이미지 생성을 위한 dall-e 모델은 예외적으로 반드시 포함
                dalle_models = [m for m in api_models if "dall-e" in m]
                other_models = [m for m in api_models if "dall-e" not in m]
                other_models = sorted(other_models, key=lambda x: (len(x), x))[:60 - len(dalle_models)]
                api_models = dalle_models + other_models

        elif provider == "anthropic":
            anthropic_client = get_anthropic_client()
            if anthropic_client:
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

        elif provider == "xai":
            xai_client = get_xai_client()
            if xai_client:
                try:
                    models_list = xai_client.models.list()
                    api_models = [m.id for m in models_list.data]
                except Exception as e:
                    print(f"[WARNING] xAI API calls failed: {e}")

        new_models = [m for m in api_models if m not in enabled_models]

        # 2. Claude API를 통해 동적 메타데이터(정렬, 가격, 설명) 생성 및 DB 저장
        if api_models:
            metadata_json = generate_model_metadata_via_claude(provider, api_models)
            if metadata_json:
                metadata_key = f"available_models_metadata_{provider}"
                metadata_conf = SystemConfig.query.filter_by(key=metadata_key).first()
                if not metadata_conf:
                    metadata_conf = SystemConfig(key=metadata_key, value=json.dumps(metadata_json))
                    db.session.add(metadata_conf)
                else:
                    metadata_conf.value = json.dumps(metadata_json)

        # 3. 업데이트 시간 기록

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
