"""
AI 공급사별 클라이언트 초기화 및 통합 응답 생성 로직.
라우트에서 공통적으로 호출할 수 있도록 순수 함수 형태로 제공한다.
"""

import os
import base64
import mimetypes

import anthropic
import openai
import google.generativeai as genai

# Anthropic 클라이언트는 키가 있을 때만 초기화한다.
anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    try:
        anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    except Exception as e:
        print(f"⚠️ Anthropic Client Init Error: {e}")

# OpenAI 클라이언트는 키가 있을 때만 초기화한다.
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    try:
        openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    except Exception as e:
        print(f"⚠️ OpenAI Client Init Error: {e}")

# Google Gemini는 전역 configure로 키를 등록한다.
if os.getenv("GOOGLE_API_KEY"):
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    except Exception as e:
        print(f"⚠️ Google Client Init Error: {e}")

# 지원 모델 목록(프론트 관리자 패널에 노출되는 기준)
AVAILABLE_MODELS = {
    "gpt-4o": {"name": "GPT-4o (Omni)", "provider": "openai", "input_price": 5.00, "output_price": 15.00},
    "gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "openai", "input_price": 0.15, "output_price": 0.60},
    "claude-haiku-4-5-20251001": {"name": "Claude Haiku 4.5", "provider": "anthropic", "input_price": 1.00, "output_price": 5.00},
    "claude-sonnet-4-5-20250929": {"name": "Claude Sonnet 4.5", "provider": "anthropic", "input_price": 3.00, "output_price": 15.00},
    "claude-opus-4-1-20250805": {"name": "Claude Opus 4.1", "provider": "anthropic", "input_price": 15.00, "output_price": 75.00},
    "gemini-2.0-flash": {"name": "Gemini 2.0 Flash", "provider": "google", "input_price": 0.10, "output_price": 0.40},
    "gemini-3-flash-preview": {"name": "Gemini 3 Flash", "provider": "google", "input_price": 0.0, "output_price": 0.0},
    "gemini-3-pro-preview": {"name": "Gemini 3 Pro", "provider": "google", "input_price": 0.0, "output_price": 0.0},
    "gemini-2.0-flash-exp-image-generation": {"name": "Gemini 2.0 Flash (Exp) Image", "provider": "google", "input_price": 0.0006, "output_price": 0.0006},
    "gemini-2.5-flash-image": {"name": "Gemini 2.5 Flash Image", "provider": "google", "input_price": 0.02, "output_price": 0.02},
    "gemini-3-pro-image-preview": {"name": "Gemini 3.0 Pro Image", "provider": "google", "input_price": 0.03, "output_price": 0.03},
    "imagen-4.0-ultra-generate-001": {"name": "Imagen 4.0 (Ultra)", "provider": "google", "input_price": 0.06, "output_price": 0.06},
}

# 공급사별 기본 모델 아이디(모델 정보 누락 시 fallback)
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-3-flash-preview",
}
DEFAULT_MODEL = DEFAULT_MODELS["anthropic"]
DEFAULT_MAX_TOKENS = 4096


def generate_ai_response(model_id, system_prompt, messages, max_tokens, upload_folder):
    """
    여러 공급사에 대한 통합 응답 생성 함수.

    Args:
        model_id: 사용자가 선택한 모델 ID(존재하지 않으면 공급사 기본 모델로 대체).
        system_prompt: 시스템 프롬프트(페르소나별 정책 메시지).
        messages: role/content/image_paths가 포함된 대화 기록.
        max_tokens: 응답 길이 제한.
        upload_folder: 이미지 파일이 저장된 업로드 루트 경로.
    """
    model_info = AVAILABLE_MODELS.get(model_id)
    if not model_info:
        if "gpt" in model_id:
            model_id = DEFAULT_MODELS["openai"]
        elif "claude" in model_id:
            model_id = DEFAULT_MODELS["anthropic"]
        elif "gemini" in model_id:
            model_id = DEFAULT_MODELS["google"]
        else:
            model_id = DEFAULT_MODELS["anthropic"]
        model_info = AVAILABLE_MODELS[model_id]

    # 모델 소유 공급사를 기준으로 분기한다.
    provider = model_info["provider"]

    if provider == "anthropic":
        # Anthropic 메시지 포맷(텍스트+이미지)을 구성한다.
        if not anthropic_client:
            raise ValueError("Anthropic API Key가 없거나 초기화되지 않았습니다.")
        anthropic_messages = []
        for msg in messages:
            content_list = []
            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                # 로컬 파일을 base64로 읽어 Anthropic 이미지 형식으로 변환
                try:
                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    with open(full_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                        media_type = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": img_data},
                        })
                except Exception as e:
                    print(f"Anthropic Image Load Warning: {e}")

            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                content_list.extend(msg_content)
            elif isinstance(msg_content, str) and msg_content.strip():
                content_list.append({"type": "text", "text": msg_content})

            if content_list:
                anthropic_messages.append({"role": msg["role"], "content": content_list})

        response = anthropic_client.messages.create(
            model=model_id, max_tokens=max_tokens, system=system_prompt, messages=anthropic_messages
        )
        return response.content[0].text

    if provider == "openai":
        # OpenAI 메시지 포맷(텍스트+이미지)을 구성한다.
        if not openai_client:
            raise ValueError("OpenAI API Key가 없거나 초기화되지 않았습니다.")
        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            content_list = []
            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                content_list.extend(msg_content)
            elif isinstance(msg_content, str) and msg_content:
                content_list.append({"type": "text", "text": msg_content})

            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                # OpenAI는 data URL 방식으로 이미지를 전달한다.
                try:
                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    with open(full_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                        mime = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        })
                except Exception:
                    pass

            if content_list:
                openai_messages.append({"role": msg["role"], "content": content_list})

        response = openai_client.chat.completions.create(
            model=model_id, messages=openai_messages, max_tokens=max_tokens
        )
        return response.choices[0].message.content

    if provider == "google":
        # Gemini는 safety 설정과 history 기반 대화 세션을 사용한다.
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("Google API Key가 없습니다.")

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        gen_config = genai.types.GenerationConfig(max_output_tokens=max_tokens)
        gemini_model = genai.GenerativeModel(model_id, system_instruction=system_prompt)

        chat_history = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            parts = []
            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                for item in msg_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item["text"])
            elif isinstance(msg_content, str) and msg_content:
                parts.append(msg_content)

            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                try:
                    import PIL.Image

                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    img = PIL.Image.open(full_path)
                    parts.append(img)
                except Exception as e:
                    print(f"Gemini Image Load Error: {e}")

            if parts:
                chat_history.append({"role": role, "parts": parts})

        try:
            # 마지막 메시지를 사용자 입력으로 보고 나머지는 history로 전달한다.
            if chat_history and chat_history[-1]["role"] == "user":
                last_msg = chat_history.pop()
                chat_session = gemini_model.start_chat(history=chat_history)
                response = chat_session.send_message(
                    last_msg["parts"], generation_config=gen_config, safety_settings=safety_settings
                )
                return response.text
            chat_session = gemini_model.start_chat(history=chat_history)
            response = chat_session.send_message(
                "Please continue.", generation_config=gen_config, safety_settings=safety_settings
            )
            return response.text
        except ValueError:
            return "⚠️ [Google Gemini Error] 안전 정책에 의해 답변이 차단되었습니다."
        except Exception as e:
            print(f"Gemini API Error details: {e}")
            raise e

    return "Error: Provider not supported"
