import os
import google.generativeai as genai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ 오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    exit()

print("------------------------------------------------")
print(f"🔑 감지된 Gemini API 키: {api_key[:5]}...{api_key[-5:]}")
print("------------------------------------------------")

try:
    # Gemini 설정
    genai.configure(api_key=api_key)
    
    print("📋 [Gemini] 사용 가능한 모델 목록 조회 중...")
    available_models = []
    image_models = []
    
    for m in genai.list_models():
        name = m.name.replace('models/', '')
        available_models.append(name)
        
        # 이미지 모델 확인 (imagen 등)
        if 'imagen' in name.lower():
            image_models.append(name)
    
    print(f"✅ 총 {len(available_models)}개의 모델을 찾았습니다.")
    
    print("\n--- [ Gemini 모델 목록 ] ---")
    for m in available_models:
        print(f"   - {m}")
        
    print("\n🖼️ [ Gemini 이미지 생성 모델 ]")
    if image_models:
        for im in image_models:
            print(f"   - {im}")
    else:
        print("   - 전용 이미지 생성 모델('imagen' 등)이 현재 API 키 또는 SDK에서 목록으로 조회되지 않았습니다.")
        print("   - 참고: Gemini 자체는 텍스트/멀티모달 모델이며, Google은 Imagen 모델을 별도로 제공하거나 버전에 따라 직접 이름 지정(imagen-3.0-generate-001)을 해야 할 수 있습니다.")

except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")