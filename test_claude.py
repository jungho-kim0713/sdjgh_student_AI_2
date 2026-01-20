import os
import anthropic
from dotenv import load_dotenv

# .env 파일 로드 (API 키 가져오기)
load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

print("------------------------------------------------")
print(f"🔑 감지된 Anthropic API 키: {api_key[:5]}...{api_key[-5:] if api_key else '없음'}")
print("------------------------------------------------")

if not api_key:
    print("❌ 오류: .env 파일에서 ANTHROPIC_API_KEY를 찾을 수 없습니다.")
    exit()

try:
    client = anthropic.Anthropic(api_key=api_key)
    
    print("📋 [Claude] 사용 가능한 모델 목록 조회 중...")
    
    # 모델 목록 조회
    # (참고: API 키 권한에 따라 list()가 지원되지 않을 수 있습니다.)
    page = client.models.list()
    
    available_models = []
    print("\n--- [ Claude 모델 목록 ] ---")
    
    # Paginator 처리 (혹시 모델이 많을 경우)
    for model in page:
        print(f"   - {model.id}")
        available_models.append(model.id)
            
    print("\n------------------------------------------------")
    print(f"✅ 총 {len(available_models)}개의 모델을 찾았습니다.")
    
    # ---------------------------------------------------------
    # (신규) 모델 하나씩 순회하며 질문 테스트
    # ---------------------------------------------------------
    print("\n🧪 실전 테스트 시작: '안녕? 넌 어떤 모델이니?'")
    
    found_working_model = False
    target_question = "안녕? 넌 어떤 모델이니?"

    # 목록 순서대로 테스트 (최신순 정렬 보장 안됨, 목록대로 진행)
    for model_id in available_models:
        print(f"\n🤖 [시도] 모델: {model_id}")
        try:
            # API 호출 시도
            response = client.messages.create(
                model=model_id,
                max_tokens=200,
                messages=[{"role": "user", "content": target_question}]
            )
            
            # 성공 시 출력
            print(f"   ✅ 성공! 응답:\n   \"{response.content[0].text}\"")
            print(f"\n🎉 찾았습니다! 사용 가능한 모델: {model_id}")
            
            found_working_model = True
            break  # 하나라도 성공하면 테스트 종료
            
        except Exception as e:
            # 실패 시 에러 메시지 간략 출력 후 다음 모델로
            error_msg = str(e).split('\n')[0] # 첫 줄만 표시
            print(f"   ❌ 실패: {error_msg}")
            continue
    
    if not found_working_model:
        print("\n🚫 모든 모델에 대해 테스트를 실패했습니다. API 키 권한을 확인해주세요.")

except anthropic.AuthenticationError:
    print("\n❌ 인증 실패: API 키가 올바르지 않습니다.")
except Exception as e:
    print(f"\n🚫 [실패] 오류 발생:\n{e}")