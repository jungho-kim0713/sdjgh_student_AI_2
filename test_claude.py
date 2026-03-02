import os
import anthropic
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("❌ 오류: .env 파일에서 ANTHROPIC_API_KEY를 찾을 수 없습니다.")
    exit()

print("------------------------------------------------")
print(f"🔑 감지된 Anthropic API 키: {api_key[:5]}...{api_key[-5:] if api_key else '없음'}")
print("------------------------------------------------")

try:
    client = anthropic.Anthropic(api_key=api_key)
    
    print("📋 [Claude] 사용 가능한 모델 목록 조회 중...")
    
    page = client.models.list()
    available_models = [model.id for model in page]
    
    print(f"✅ 총 {len(available_models)}개의 모델을 찾았습니다.")
    
    print("\n--- [ Claude 모델 목록 ] ---")
    for model_id in available_models:
        print(f"   - {model_id}")
            
    print("\n🖼️ [ Claude 이미지 생성 모델 ]")
    print("   - ❌ 현재 Anthropic의 Claude는 이미지 생성(Image Generation) 기능을 제공하지 않습니다.")
    print("   - (단, 이미지를 '입력'으로 받아 분석하는 비전(Vision) 기능은 claude-3 등의 계열에서 지원합니다.)")
    
except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")