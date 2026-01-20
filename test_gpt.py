import os
import openai
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

print("------------------------------------------------")
print(f"🔑 감지된 OpenAI API 키: {api_key[:5]}...{api_key[-5:] if api_key else '없음'}")
print("------------------------------------------------")

if not api_key:
    print("❌ 오류: .env 파일에서 OPENAI_API_KEY를 찾을 수 없습니다.")
    exit()

try:
    client = openai.OpenAI(api_key=api_key)
    
    print("📋 [GPT] 사용 가능한 모델 목록 조회 중...")
    models = client.models.list()
    
    available_gpt_models = []
    print("\n--- [ GPT 계열 모델 목록 ] ---")
    for model in models:
        # gpt로 시작하는 모델만 필터링해서 출력
        if model.id.startswith("gpt"):
            print(f"   - {model.id}")
            available_gpt_models.append(model.id)
            
    print("\n------------------------------------------------")
    
    # 테스트할 모델 선택 (gpt-4o 우선, 없으면 목록의 첫 번째)
    target_model = "gpt-4o"
    if target_model not in available_gpt_models:
        # gpt-4o가 없으면 gpt-4o-mini나 gpt-3.5-turbo 등 대안 찾기
        alternatives = [m for m in available_gpt_models if "gpt-4" in m]
        if alternatives:
            target_model = alternatives[0]
        elif available_gpt_models:
            target_model = available_gpt_models[0]
        
        print(f"⚠️ '{target_model}'로 테스트를 진행합니다.")

    print(f"🤖 [2단계] '{target_model}' 모델에게 질문하는 중...")
    
    response = client.chat.completions.create(
        model=target_model,
        messages=[{"role": "user", "content": "안녕? 넌 어떤 모델이니?"}],
        max_tokens=50
    )
    
    print("\n✅ [성공] GPT 응답:")
    print(response.choices[0].message.content)

except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")