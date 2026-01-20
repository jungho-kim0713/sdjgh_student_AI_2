import os
import google.generativeai as genai
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
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            # 모델 이름에서 'models/' 접두사 제거
            name = m.name.replace('models/', '')
            print(f"   - {name}")
            available_models.append(name)
    
    print("\n------------------------------------------------")
    print(f"✅ 총 {len(available_models)}개의 모델을 찾았습니다.")

except genai.configureError:
    print("\n❌ 인증 실패: API 키가 올바르지 않습니다.")

except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")