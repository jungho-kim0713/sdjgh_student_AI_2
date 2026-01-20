import os
import base64
import mimetypes
import requests
import google.generativeai as genai
import openai
import anthropic
from flask import current_app

# ---------------------------------------------------------
# [1] 모델 정의 (상수)
# ---------------------------------------------------------
AVAILABLE_MODELS = {
    # OpenAI (GPT)
    "gpt-4o": {"name": "GPT-4o (Omni)", "provider": "openai"},
    "gpt-4o-mini": {"name": "GPT-4o Mini", "provider": "openai"},
    
    # Anthropic (Claude)
    "claude-haiku-4-5-20251001": {"name": "Claude Haiku 4.5", "provider": "anthropic"},
    "claude-sonnet-4-5-20250929": {"name": "Claude Sonnet 4.5", "provider": "anthropic"},
    "claude-opus-4-1-20250805": {"name": "Claude Opus 4.1", "provider": "anthropic"},
    
    # Google (Gemini)
    "gemini-2.0-flash": {"name": "Gemini 2.0 Flash", "provider": "google"},
    "gemini-3-pro-preview": {"name": "Gemini 3.0 Pro", "provider": "google"}
}

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-2.0-flash"
}

# ---------------------------------------------------------
# [2] AI 클라이언트 초기화 함수
# ---------------------------------------------------------
# 전역 클라이언트 변수
openai_client = None
anthropic_client = None

def init_ai_clients():
    """환경 변수에서 API 키를 로드하여 클라이언트를 초기화합니다."""
    global openai_client, anthropic_client
    
    # OpenAI 초기화
    if os.getenv("OPENAI_API_KEY"):
        try:
            openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        except Exception as e:
            print(f"⚠️ OpenAI Client Init Error: {e}")

    # Anthropic 초기화
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        except Exception as e:
            print(f"⚠️ Anthropic Client Init Error: {e}")

    # Google 초기화
    if os.getenv("GOOGLE_API_KEY"):
        try:
            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        except Exception as e:
            print(f"⚠️ Google Client Init Error: {e}")

# 앱 시작 시 초기화 실행
init_ai_clients()

# ---------------------------------------------------------
# [3] 통합 AI 응답 생성 함수 (핵심)
# ---------------------------------------------------------
def generate_ai_response(model_id, system_prompt, messages, max_tokens, upload_folder):
    """
    선택된 모델(GPT, Claude, Gemini)에 따라 적절한 API를 호출하여 응답을 반환합니다.
    """
    # 모델 ID 유효성 검사 및 공급사 확인
    model_info = AVAILABLE_MODELS.get(model_id)
    if not model_info:
        # 잘못된 모델 ID일 경우 공급사별 기본값으로 대체
        if "gpt" in str(model_id): model_id = DEFAULT_MODELS["openai"]
        elif "claude" in str(model_id): model_id = DEFAULT_MODELS["anthropic"]
        elif "gemini" in str(model_id): model_id = DEFAULT_MODELS["google"]
        else: model_id = DEFAULT_MODELS["anthropic"]
        model_info = AVAILABLE_MODELS[model_id]

    provider = model_info["provider"]

    # --- A. Anthropic (Claude) 처리 ---
    if provider == "anthropic":
        if not anthropic_client: raise ValueError("Anthropic API Key가 없습니다.")
        
        anthropic_messages = []
        for msg in messages:
            content_list = []
            
            # 이미지 처리
            img_paths = msg.get("image_paths", [])
            for img_path in img_paths:
                try:
                    # 상대 경로를 절대 경로로 변환
                    relative_path = img_path.replace('uploads/', '', 1) 
                    full_path = os.path.join(upload_folder, relative_path)
                    
                    with open(full_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                        media_type = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image", 
                            "source": {"type": "base64", "media_type": media_type, "data": img_data}
                        })
                except Exception as e:
                    print(f"Anthropic Image Load Warning: {e}")

            # 텍스트 처리
            msg_content = msg.get("content")
            if isinstance(msg_content, str) and msg_content.strip():
                content_list.append({"type": "text", "text": msg_content})
            
            if content_list:
                anthropic_messages.append({"role": msg["role"], "content": content_list})
        
        # API 호출
        response = anthropic_client.messages.create(
            model=model_id, max_tokens=max_tokens, system=system_prompt, messages=anthropic_messages
        )
        return response.content[0].text

    # --- B. OpenAI (GPT) 처리 ---
    elif provider == "openai":
        if not openai_client: raise ValueError("OpenAI API Key가 없습니다.")
        
        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            content_list = []
            
            # 텍스트 처리
            msg_content = msg.get("content")
            if isinstance(msg_content, str) and msg_content:
                content_list.append({"type": "text", "text": msg_content})

            # 이미지 처리
            img_paths = msg.get("image_paths", [])
            for img_path in img_paths:
                try:
                    relative_path = img_path.replace('uploads/', '', 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    with open(full_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                        mime = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image_url", 
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"}
                        })
                except: pass
            
            if content_list:
                openai_messages.append({"role": msg["role"], "content": content_list})
            
        # API 호출
        response = openai_client.chat.completions.create(
            model=model_id, messages=openai_messages, max_tokens=max_tokens
        )
        return response.choices[0].message.content

    # --- C. Google (Gemini) 처리 ---
    elif provider == "google":
        if not os.getenv("GOOGLE_API_KEY"): raise ValueError("Google API Key가 없습니다.")
        
        # 안전 설정 (학교용이므로 기본 차단은 유지하되, 코딩 관련 질문이 막히지 않도록 조정)
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
        
        gen_config = genai.types.GenerationConfig(max_output_tokens=max_tokens)
        gemini_model = genai.GenerativeModel(model_id, system_instruction=system_prompt)
        
        chat_history = []
        for msg in messages:
            # Gemini는 user/model 역할을 사용
            role = "user" if msg["role"] == "user" else "model"
            parts = []
            
            # 텍스트 추가
            msg_content = msg.get("content")
            if isinstance(msg_content, str) and msg_content:
                parts.append(msg_content)

            # 이미지 추가 (Pillow 라이브러리 사용)
            img_paths = msg.get("image_paths", [])
            for img_path in img_paths:
                try:
                    import PIL.Image
                    relative_path = img_path.replace('uploads/', '', 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    img = PIL.Image.open(full_path)
                    parts.append(img)
                except Exception as e:
                    print(f"Gemini Image Load Error: {e}")
            
            if parts:
                chat_history.append({"role": role, "parts": parts})
        
        try:
            # 마지막 메시지가 사용자 메시지여야 채팅 시작 가능
            if chat_history and chat_history[-1]["role"] == "user":
                last_msg = chat_history.pop()
                chat_session = gemini_model.start_chat(history=chat_history)
                response = chat_session.send_message(
                    last_msg["parts"], 
                    generation_config=gen_config, 
                    safety_settings=safety_settings
                )
                return response.text
            else:
                return "대화 기록 오류: 마지막 메시지가 사용자가 아닙니다."
        except ValueError:
            return "⚠️ [Google Gemini Error] 안전 정책에 의해 답변이 차단되었습니다."
        except Exception as e:
            print(f"Gemini API Error: {e}")
            raise e

    return "Error: 지원하지 않는 공급사입니다."