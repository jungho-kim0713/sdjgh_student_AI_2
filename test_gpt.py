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
    
    # 1. 모델 목록 조회   
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
    
    # 2. 텍스트 생성 테스트 (Chat Completion)
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

    # 3. 이미지 생성 테스트 (Image Generation)
    # 목록에서 확인하신 'gpt-image-1.5'를 우선 사용
    image_model = "gpt-image-1.5"
    
    print(f"\n🎨 [3/3] 이미지 생성 테스트 중... (모델: {image_model})")
    
    if image_model in available_models:
        try:
            image_response = client.images.generate(
                model=image_model,
                prompt="A beautiful sunset over a futuristic digital city, highly detailed, cinematic lighting",
                n=1,
                size="1024x1024"
            )
            print(f"✅ 이미지 생성 성공!")
            print(f"🔗 이미지 결과 URL: {image_response.data[0].url}")
        except Exception as e:
            print(f"❌ 이미지 생성 실패 (API 호출 오류): {e}")
            print("💡 팁: 'dall-e-3' 모델이 목록에 있다면 해당 모델로도 시도해 보세요.")
    else:
        print(f"⚠️ 경고: 목록에 '{image_model}' 모델이 존재하지 않습니다. 생성을 건너뜁니다.")

    print("\n------------------------------------------------")
    print("🚀 모든 테스트 절차가 완료되었습니다.")



except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")