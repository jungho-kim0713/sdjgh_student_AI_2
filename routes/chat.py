import os
import datetime
import base64
import traceback

import requests
import google.generativeai as genai
from flask import Blueprint, jsonify, request, render_template, url_for, current_app
from flask_login import login_required, current_user

from extensions import db
from models import ChatSession, Message, ChatFile, SystemConfig, PersonaConfig, User
from prompts import AI_PERSONAS
from services.ai_service import (
    generate_ai_response,
    DEFAULT_MODELS,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    AVAILABLE_MODELS,
    openai_client,
)

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/")
@login_required
def index():
    """메인 채팅 화면 렌더링.

    - 권한: 로그인 사용자
    - 전달: 관리자 여부, 사용자명, 사용자 역할(데이터 속성으로 프론트 전달)
    """
    return render_template(
        "index.html",
        is_admin=current_user.is_admin,
        current_username=current_user.username,
        current_user_role=getattr(current_user, "role", "user"),
    )


@chat_bp.route("/api/get_persona_visibility", methods=["GET"])
@login_required
def get_persona_visibility():
    """페르소나 가시성 목록 제공.

    - 권한: 로그인 사용자
    - 관리자: 전체 페르소나 반환
    - 일반 사용자: allow_user/allow_teacher 설정에 따라 필터링
    """
    if current_user.is_admin:
        personas = [
            {"role_key": key, "role_name": persona["role_name"]}
            for key, persona in AI_PERSONAS.items()
        ]
        return jsonify({"personas": personas})

    # 사용자 역할에 맞는 페르소나만 선별
    user_role = getattr(current_user, "role", "user") or "user"
    allowed = []
    for key, persona in AI_PERSONAS.items():
        conf = PersonaConfig.query.filter_by(role_key=key).first()
        allow_user = conf.allow_user if conf else True
        allow_teacher = conf.allow_teacher if conf else True
        is_allowed = allow_user if user_role == "user" else allow_teacher
        if is_allowed:
            allowed.append({"role_key": key, "role_name": persona["role_name"]})
    return jsonify({"personas": allowed})


@chat_bp.route("/api/get_persona_provider_restrictions", methods=["GET"])
@login_required
def get_persona_provider_restrictions():
    """페르소나별 공급사 제한 정보를 반환한다.

    - 권한: 로그인 사용자
    - 입력: role_key (query param)
    - 응답: restrict_google/restrict_anthropic/restrict_openai
    """
    role_key = request.args.get("role_key")
    if not role_key or role_key not in AI_PERSONAS:
        return jsonify({"error": "Invalid role"}), 400

    conf = PersonaConfig.query.filter_by(role_key=role_key).first()
    data = {
        "restrict_google": conf.restrict_google if conf else False,
        "restrict_anthropic": conf.restrict_anthropic if conf else False,
        "restrict_openai": conf.restrict_openai if conf else False,
    }
    return jsonify(data)


@chat_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    """채팅 요청 처리(텍스트/이미지 생성).

    - 권한: 로그인 사용자
    - 기능: 서비스 점검 체크 → 페르소나/권한 검증 → 세션 생성 → 메시지 저장 → AI 응답 생성
    """
    # 서비스 점검 모드면 즉시 차단
    status_config = SystemConfig.query.filter_by(key="service_status").first()
    if status_config and status_config.value == "inactive":
        return jsonify({"response": "서비스 점검 중입니다."})

    # 요청 데이터 추출
    data = request.json
    role_key = data.get("model")
    provider = data.get("provider", "anthropic")
    user_message = data.get("message")
    file_ids = data.get("file_ids", [])

    # 이미지 생성 페르소나: 별도 플로우로 처리
    if role_key == "ai_illustrator":
        try:
            if not current_user.is_admin:
                conf = PersonaConfig.query.filter_by(role_key=role_key).first()
                restrict_map = {
                    "google": conf.restrict_google if conf else False,
                    "anthropic": conf.restrict_anthropic if conf else False,
                    "openai": conf.restrict_openai if conf else False,
                }
                if restrict_map.get(provider):
                    return jsonify({"error": "권한 없음"}), 403

            session_id = data.get("session_id")
            if not session_id:
                # 새 세션 생성(이미지 생성 전용 제목)
                title = f"그림 생성: {user_message[:20]}"
                current_session = ChatSession(
                    title=title, user_id=current_user.id, role_key=role_key
                )
                db.session.add(current_session)
                db.session.commit()
                session_id = current_session.id

            # 사용자 메시지 저장
            db.session.add(
                Message(
                    session_id=session_id,
                    user_id=current_user.id,
                    is_user=True,
                    content=user_message,
                    provider=provider,
                )
            )
            db.session.commit()

            # 페르소나 설정에서 선택된 모델을 사용한다.
            config = PersonaConfig.query.filter_by(role_key=role_key).first()
            selected_model_id = DEFAULT_MODEL
            if config:
                if provider == "openai":
                    selected_model_id = config.model_openai
                elif provider == "google":
                    selected_model_id = config.model_google
                elif provider == "anthropic":
                    selected_model_id = config.model_anthropic

            # Imagen 4.0 선택 시 대화/프롬프트는 Gemini 3 Pro로 고정
            prompt_model_id = selected_model_id
            if provider == "google" and selected_model_id == "imagen-4.0-generate-001":
                prompt_model_id = "gemini-3-pro-preview"

            # 프롬프트 최적화(텍스트 → 이미지 프롬프트)
            prompt_optimizer = generate_ai_response(
                model_id=prompt_model_id,
                system_prompt=AI_PERSONAS["ai_illustrator"]["system_prompts"].get(
                    provider, "Convert to English prompt"
                ),
                messages=[{"role": "user", "content": user_message}],
                max_tokens=200,
                upload_folder=current_app.config["UPLOAD_FOLDER"],
            )
            final_prompt = prompt_optimizer.strip()

            # 프롬프트 최적화가 실패했으면 원본 메시지 사용
            if final_prompt.startswith("⚠️") or "차단" in final_prompt or "Error" in final_prompt:
                final_prompt = user_message

            generated_image_filename = None

            if provider == "google":
                if not os.getenv("GOOGLE_API_KEY"):
                    raise ValueError("Google API Key Missing")
                # Imagen 4.0 (Ultra) 선택 시 REST 호출
                if selected_model_id == "imagen-4.0-generate-001":
                    try:
                        api_url = (
                            "https://generativelanguage.googleapis.com/v1beta/models/"
                            f"imagen-4.0-generate-001:predict?key={os.getenv('GOOGLE_API_KEY')}"
                        )
                        headers = {"Content-Type": "application/json"}
                        payload = {
                            "instances": [{"prompt": final_prompt}],
                            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
                        }
                        response = requests.post(api_url, headers=headers, json=payload)
                        if response.status_code != 200:
                            raise Exception(
                                f"Google API Error ({response.status_code}): {response.text}"
                            )
                        result = response.json()
                        if "predictions" in result and len(result["predictions"]) > 0:
                            # Base64 이미지 디코딩 후 저장
                            b64_data = result["predictions"][0]["bytesBase64Encoded"]
                            img_data = base64.b64decode(b64_data)
                            generated_image_filename = (
                                f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_imagen.png"
                            )
                            save_path = os.path.join(
                                current_app.config["UPLOAD_FOLDER"],
                                generated_image_filename,
                            )
                            with open(save_path, "wb") as f:
                                f.write(img_data)
                        else:
                            raise Exception("이미지 데이터가 응답에 없습니다.")
                    except Exception as e:
                        print(f"Imagen REST API Error: {e}")
                        return jsonify({"error": f"Google 이미지 생성 실패(API): {str(e)}"}), 500
                else:
                    # Gemini 이미지 모델 사용
                    try:
                        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                        safety_settings = [
                            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                        ]
                        image_model = genai.GenerativeModel(selected_model_id)
                        response = image_model.generate_content(final_prompt, safety_settings=safety_settings)
                        parts = response.candidates[0].content.parts if response.candidates else []
                        img_data = None
                        for part in parts:
                            if hasattr(part, "inline_data") and part.inline_data:
                                img_data = base64.b64decode(part.inline_data.data)
                                break
                            if isinstance(part, dict) and part.get("inline_data"):
                                img_data = base64.b64decode(part["inline_data"]["data"])
                                break
                        if not img_data:
                            raise Exception("이미지 데이터가 응답에 없습니다.")
                        generated_image_filename = (
                            f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_gemini.png"
                        )
                        save_path = os.path.join(
                            current_app.config["UPLOAD_FOLDER"],
                            generated_image_filename,
                        )
                        with open(save_path, "wb") as f:
                            f.write(img_data)
                    except Exception as e:
                        print(f"Gemini Image Error: {e}")
                        return jsonify({"error": f"Google 이미지 생성 실패: {str(e)}"}), 500

            elif provider == "openai":
                # DALL-E 3 호출
                if not openai_client:
                    raise ValueError("OpenAI API Key Missing")
                response = openai_client.images.generate(
                    model="dall-e-3",
                    prompt=final_prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_url = response.data[0].url
                img_data = requests.get(image_url).content
                generated_image_filename = (
                    f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_dalle.png"
                )
                save_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    generated_image_filename,
                )
                with open(save_path, "wb") as f:
                    f.write(img_data)

            else:
                # Claude는 이미지 생성 미지원
                return jsonify(
                    {
                        "response": (
                            "Claude(Anthropic)는 아직 이미지 생성을 지원하지 않습니다. "
                            "Google이나 GPT를 선택해주세요."
                        ),
                        "session_id": session_id,
                    }
                )

            if generated_image_filename:
                # 이미지 파일 메타데이터 저장
                rel_path = f"uploads/{generated_image_filename}"
                new_file = ChatFile(
                    session_id=session_id,
                    user_id=current_user.id,
                    filename=generated_image_filename,
                    storage_path=rel_path,
                    file_type="image/png",
                    file_size=os.path.getsize(save_path),
                    uploaded_by="ai",
                )
                db.session.add(new_file)
                db.session.commit()
                # 사용자에게 이미지 결과 HTML 반환
                response_html = (
                    "🎨 **생성된 이미지**\n\n"
                    f"(Prompt: {final_prompt})\n\n"
                    f"<img src='/static/{rel_path}' style='max-width:100%; border-radius:10px; margin-top:10px;' "
                    "onclick='window.open(this.src)'>"
                )
                db.session.add(
                    Message(
                        session_id=session_id,
                        user_id=current_user.id,
                        is_user=False,
                        content=response_html,
                        provider=provider,
                    )
                )
                db.session.commit()
                return jsonify(
                    {"response": response_html, "session_id": session_id, "provider": provider}
                )

        except Exception as e:
            # 이미지 생성 예외 처리
            print(f"Image Gen Error: {e}")
            return jsonify({"error": f"이미지 생성 실패: {str(e)}"}), 500

    image_paths_for_ai = []

    # 업로드된 파일 중 이미지 경로만 AI 입력으로 전달
    for fid in file_ids:
        f = db.session.get(ChatFile, fid)
        if f and f.user_id == current_user.id:
            if data.get("session_id"):
                f.session_id = data.get("session_id")
            if f.file_type and f.file_type.startswith("image/"):
                image_paths_for_ai.append(f.storage_path)

    db.session.commit()

    # 유효한 페르소나인지 확인
    if role_key not in AI_PERSONAS:
        return jsonify({"error": "Invalid persona"}), 400

    # 관리자 제외: 페르소나 접근 권한 체크
    if not current_user.is_admin:
        user_role = getattr(current_user, "role", "user") or "user"
        conf = PersonaConfig.query.filter_by(role_key=role_key).first()
        allow_user = conf.allow_user if conf else True
        allow_teacher = conf.allow_teacher if conf else True
        is_allowed = allow_user if user_role == "user" else allow_teacher
        if not is_allowed:
            return jsonify({"error": "권한 없음"}), 403
        # 페르소나별 공급사 제한 체크
        restrict_map = {
            "google": conf.restrict_google if conf else False,
            "anthropic": conf.restrict_anthropic if conf else False,
            "openai": conf.restrict_openai if conf else False,
        }
        if restrict_map.get(provider):
            return jsonify({"error": "권한 없음"}), 403
    persona_data = AI_PERSONAS[role_key]
    prompts = persona_data.get("system_prompts", {})
    system_prompt = prompts.get(provider, prompts.get("default", ""))

    # 페르소나 설정에 따라 모델 선택
    config = PersonaConfig.query.filter_by(role_key=role_key).first()
    selected_model_id = DEFAULT_MODEL
    if config:
        if provider == "openai":
            selected_model_id = config.model_openai
        elif provider == "google":
            selected_model_id = config.model_google
        elif provider == "anthropic":
            selected_model_id = config.model_anthropic
    # 모델이 유효하지 않으면 기본값으로 폴백
    if selected_model_id not in AVAILABLE_MODELS:
        if provider == "openai":
            selected_model_id = DEFAULT_MODELS["openai"]
        elif provider == "google":
            selected_model_id = DEFAULT_MODELS["google"]
        else:
            selected_model_id = DEFAULT_MODELS["anthropic"]
    selected_max_tokens = config.max_tokens if config else DEFAULT_MAX_TOKENS

    try:
        session_id = data.get("session_id")

        if session_id:
            # 기존 세션 사용 시 소유자 검증
            current_session = db.session.get(ChatSession, session_id)
            if not current_session:
                return jsonify({"error": "Session not found"}), 404
            if current_session.user_id != current_user.id:
                return jsonify({"error": "권한 없음"}), 403
        else:
            # 새 세션 생성
            title = user_message[:30] if user_message else "새 대화"
            current_session = ChatSession(
                title=title, user_id=current_user.id, role_key=role_key
            )
            db.session.add(current_session)
            db.session.commit()
            session_id = current_session.id
            # 첨부 파일에 세션 ID 연결
            for fid in file_ids:
                f = db.session.get(ChatFile, fid)
                if f:
                    f.session_id = session_id
            db.session.commit()

        # 세션 내 기존 메시지 조회(대화 문맥용)
        db_messages = (
            Message.query.filter_by(session_id=session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

        history_for_api = []
        for msg in db_messages:
            role = "user" if msg.is_user else "assistant"
            msg_image_paths = []
            if msg.image_path:
                msg_image_paths = msg.image_path.split(",")

            item = {"role": role, "content": msg.content, "image_paths": msg_image_paths}

            # 연속된 동일 역할 메시지는 합쳐서 전송(토큰 절감)
            if history_for_api and history_for_api[-1]["role"] == role:
                prev_content = history_for_api[-1]["content"] or ""
                curr_content = item["content"] or ""
                history_for_api[-1]["content"] = prev_content + "\n\n" + curr_content
                history_for_api[-1]["image_paths"].extend(item["image_paths"])
            else:
                history_for_api.append(item)

        final_messages = []
        for m in history_for_api:
            final_messages.append(m)

        # 현재 사용자 메시지를 마지막에 추가
        final_messages.append(
            {
                "role": "user",
                "content": user_message,
                "image_paths": image_paths_for_ai,
            }
        )

        saved_img_path_str = ",".join(image_paths_for_ai) if image_paths_for_ai else None

        # 사용자 메시지를 DB에 저장
        db.session.add(
            Message(
                session_id=session_id,
                user_id=current_user.id,
                is_user=True,
                content=user_message,
                image_path=saved_img_path_str,
                provider=provider,
            )
        )
        db.session.commit()

        # AI 응답 생성
        ai_response_text = generate_ai_response(
            model_id=selected_model_id,
            system_prompt=system_prompt,
            messages=final_messages,
            max_tokens=selected_max_tokens,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
        )

        # AI 응답을 DB에 저장
        db.session.add(
            Message(
                session_id=session_id,
                user_id=current_user.id,
                is_user=False,
                content=ai_response_text,
                provider=provider,
            )
        )
        db.session.commit()

        # 클라이언트에 응답 반환
        return jsonify(
            {"response": ai_response_text, "session_id": session_id, "provider": provider}
        )

    except Exception as e:
        # 처리 실패 시 롤백 및 오류 응답
        print(f"Chat Error ({provider}): {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"AI 응답 오류 ({provider}): {str(e)}"}), 500


@chat_bp.route("/api/get_chat_history")
@login_required
def get_chat_history():
    """선택된 페르소나의 최근 대화 목록 조회.

    - 권한: 로그인 사용자
    - 입력: query param role=페르소나 키
    - 응답: 세션 id/title/username 리스트 (최대 50개)
    """
    hist = (
        db.session.query(ChatSession.id, ChatSession.title, User.username)
        .join(User)
        .filter(ChatSession.role_key == request.args.get("role"))
        .order_by(ChatSession.timestamp.desc())
        .limit(50)
        .all()
    )
    return jsonify([{"id": h.id, "title": h.title, "username": h.username} for h in hist])


@chat_bp.route("/api/get_session/<int:session_id>")
@login_required
def get_session(session_id):
    """특정 세션의 메시지 목록 조회.

    - 권한: 로그인 사용자
    - 입력: session_id (path param)
    - 응답: 메시지 목록 + 소유자 이름
    """
    session_info = db.session.get(ChatSession, session_id)
    if not session_info:
        return jsonify({"error": "Session not found"}), 404
    owner = db.session.get(User, session_info.user_id)
    owner_username = owner.username if owner else "Unknown"

    # 메시지와 작성자명을 조인해서 가져온다
    msgs = (
        db.session.query(Message, User.username)
        .join(User)
        .filter(Message.session_id == session_id)
        .order_by(Message.timestamp.asc())
        .all()
    )

    message_list = []
    for m in msgs:
        img_url = None
        if m.Message.image_path:
            first_path = m.Message.image_path.split(",")[0]
            img_url = url_for("static", filename=first_path)

        # 프론트에서 바로 렌더링 가능한 형태로 변환
        message_list.append(
            {
                "text": m.Message.content,
                "image_path": img_url,
                "sender": "user" if m.Message.is_user else "ai",
                "username": m.username if m.Message.is_user else "AI",
            }
        )

    return jsonify({"owner_username": owner_username, "messages": message_list})


@chat_bp.route("/api/rename_session/<int:session_id>", methods=["POST"])
@login_required
def rename_session(session_id):
    """세션 제목 변경.

    - 권한: 세션 소유자 또는 관리자
    - 입력: new_title (JSON)
    """
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403
    s.title = request.json.get("new_title")
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/api/delete_session/<int:session_id>", methods=["POST"])
@login_required
def delete_session(session_id):
    """세션 삭제(연관 파일/메시지 포함).

    - 권한: 세션 소유자 또는 관리자
    - 동작: 파일 삭제 → 메시지 삭제 → 세션 삭제
    """
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403

    try:
        # 세션에 연결된 파일 제거
        files = ChatFile.query.filter_by(session_id=session_id).all()
        for f in files:
            try:
                if f.file_type.startswith("image/"):
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

                # 파일이 없으면 static 폴더 경로도 확인
                if not os.path.exists(path):
                    path = os.path.join(
                        current_app.static_folder, f.storage_path.replace("uploads/", "", 1)
                    )

                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"File removal error: {e}")

            # 파일 레코드 삭제
            db.session.delete(f)

        # 메시지/세션 레코드 삭제
        Message.query.filter_by(session_id=session_id).delete()
        db.session.delete(s)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        # 오류 발생 시 롤백
        db.session.rollback()
        print(f"Error deleting session {session_id}: {e}")
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500
