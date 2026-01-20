import os
import datetime
import base64
import traceback

import requests
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
    return render_template(
        "index.html",
        is_admin=current_user.is_admin,
        current_username=current_user.username,
    )


@chat_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    status_config = SystemConfig.query.filter_by(key="service_status").first()
    if status_config and status_config.value == "inactive":
        return jsonify({"response": "서비스 점검 중입니다."})

    data = request.json
    role_key = data.get("model")
    provider = data.get("provider", "anthropic")
    user_message = data.get("message")
    file_ids = data.get("file_ids", [])

    if role_key == "ai_illustrator":
        try:
            session_id = data.get("session_id")
            if not session_id:
                title = f"그림 생성: {user_message[:20]}"
                current_session = ChatSession(
                    title=title, user_id=current_user.id, role_key=role_key
                )
                db.session.add(current_session)
                db.session.commit()
                session_id = current_session.id

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

            prompt_optimizer = generate_ai_response(
                model_id=DEFAULT_MODELS[provider],
                system_prompt=AI_PERSONAS["ai_illustrator"]["system_prompts"].get(
                    provider, "Convert to English prompt"
                ),
                messages=[{"role": "user", "content": user_message}],
                max_tokens=200,
                upload_folder=current_app.config["UPLOAD_FOLDER"],
            )
            final_prompt = prompt_optimizer.strip()

            generated_image_filename = None

            if provider == "google":
                if not os.getenv("GOOGLE_API_KEY"):
                    raise ValueError("Google API Key Missing")
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

            elif provider == "openai":
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
            print(f"Image Gen Error: {e}")
            return jsonify({"error": f"이미지 생성 실패: {str(e)}"}), 500

    image_paths_for_ai = []

    for fid in file_ids:
        f = db.session.get(ChatFile, fid)
        if f and f.user_id == current_user.id:
            if data.get("session_id"):
                f.session_id = data.get("session_id")
            if f.file_type and f.file_type.startswith("image/"):
                image_paths_for_ai.append(f.storage_path)

    db.session.commit()

    if role_key not in AI_PERSONAS:
        return jsonify({"error": "Invalid persona"}), 400
    persona_data = AI_PERSONAS[role_key]
    prompts = persona_data.get("system_prompts", {})
    system_prompt = prompts.get(provider, prompts.get("default", ""))

    config = PersonaConfig.query.filter_by(role_key=role_key).first()
    selected_model_id = DEFAULT_MODEL
    if config:
        if provider == "openai":
            selected_model_id = config.model_openai
        elif provider == "google":
            selected_model_id = config.model_google
        elif provider == "anthropic":
            selected_model_id = config.model_anthropic
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
            current_session = db.session.get(ChatSession, session_id)
            if not current_session:
                return jsonify({"error": "Session not found"}), 404
            if current_session.user_id != current_user.id:
                return jsonify({"error": "권한 없음"}), 403
        else:
            title = user_message[:30] if user_message else "새 대화"
            current_session = ChatSession(
                title=title, user_id=current_user.id, role_key=role_key
            )
            db.session.add(current_session)
            db.session.commit()
            session_id = current_session.id
            for fid in file_ids:
                f = db.session.get(ChatFile, fid)
                if f:
                    f.session_id = session_id
            db.session.commit()

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

        final_messages.append(
            {
                "role": "user",
                "content": user_message,
                "image_paths": image_paths_for_ai,
            }
        )

        saved_img_path_str = ",".join(image_paths_for_ai) if image_paths_for_ai else None

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

        ai_response_text = generate_ai_response(
            model_id=selected_model_id,
            system_prompt=system_prompt,
            messages=final_messages,
            max_tokens=selected_max_tokens,
            upload_folder=current_app.config["UPLOAD_FOLDER"],
        )

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

        return jsonify(
            {"response": ai_response_text, "session_id": session_id, "provider": provider}
        )

    except Exception as e:
        print(f"Chat Error ({provider}): {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"AI 응답 오류 ({provider}): {str(e)}"}), 500


@chat_bp.route("/api/get_chat_history")
@login_required
def get_chat_history():
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
    session_info = db.session.get(ChatSession, session_id)
    if not session_info:
        return jsonify({"error": "Session not found"}), 404
    owner = db.session.get(User, session_info.user_id)
    owner_username = owner.username if owner else "Unknown"

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
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403
    s.title = request.json.get("new_title")
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/api/delete_session/<int:session_id>", methods=["POST"])
@login_required
def delete_session(session_id):
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403

    try:
        files = ChatFile.query.filter_by(session_id=session_id).all()
        for f in files:
            try:
                if f.file_type.startswith("image/"):
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
                    os.remove(path)
            except Exception as e:
                print(f"File removal error: {e}")

            db.session.delete(f)

        Message.query.filter_by(session_id=session_id).delete()
        db.session.delete(s)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting session {session_id}: {e}")
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500
