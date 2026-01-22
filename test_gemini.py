import os
import google.generativeai as genai
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

print("------------------------------------------------")
print(f"🔑 감지된 API 키: {api_key[:5]}...{api_key[-5:] if api_key else '없음'}")
print("------------------------------------------------")

if not api_key:
    print("❌ 오류: .env 파일에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
    exit()

try:
    # Gemini 설정
    genai.configure(api_key=api_key)
    
    print("📋 [gemini] 사용 가능한 모델 목록 조회 중...")
    available_models = []
    image_related_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # 모델 이름에서 'models/' 접두사 제거
            name = m.name.replace('models/', '')
            print(f"   - {name}")
            available_models.append(name)
            if "image" in name or "imagen" in name:
                image_related_models.append(name)
    
    print("\n------------------------------------------------")
    print(f"✅ 총 {len(available_models)}개의 모델을 찾았습니다.")

    print("\n🖼️ [gemini] 이미지 관련 모델(이름 기준 필터)")
    if image_related_models:
        for name in image_related_models:
            print(f"   - {name}")
    else:
        print("   (없음)")

    print("\n🧪 [imagen] REST 전용 모델 접근 확인")
    imagen_rest_models = [
    "imagen-4.0-generate-001",        # Standard
    "imagen-4.0-ultra-generate-001",  # Ultra
    "imagen-4.0-fast-generate-001",   # Fast
    ]
    for model_name in imagen_rest_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}?key={api_key}"
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                print(f"   - {model_name} (접근 가능)")
            else:
                print(f"   - {model_name} (응답 {res.status_code})")
        except Exception as err:
            print(f"   - {model_name} (요청 실패: {err})")

except genai.configureError:
    print("\n❌ 인증 실패: API 키가 올바르지 않습니다.")

except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")