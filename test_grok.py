import os
import requests
from dotenv import load_dotenv

# 현재 디렉토리의 .env 파일 로드
load_dotenv()

XAI_API_KEY = os.getenv('XAI_API_KEY')

def test_grok_models():
    if not XAI_API_KEY:
        print("❌ 오류: .env 파일에서 XAI_API_KEY를 찾을 수 없습니다.")
        return

    print("------------------------------------------------")
    print(f"🔑 감지된 xAI API 키: {XAI_API_KEY[:5]}...{XAI_API_KEY[-5:]}")
    print("------------------------------------------------")

    url = "https://api.x.ai/v1/models"
    headers = {
        "Authorization": f"Bearer {XAI_API_KEY}"
    }

    try:
        print("📋 [xAI(Grok)] 사용 가능한 모델 목록 조회 중...\n")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            models_data = response.json().get('data', [])
            
            # API 응답에 포함된 'created' 필드(생성일 timestamp) 기준으로 최신순 정렬
            models_data.sort(key=lambda x: x.get('created', 0), reverse=True)
            
            chat_models = []
            other_models = []
            
            # 분류 로직
            for m in models_data:
                m_id = m['id']
                m_id_low = m_id.lower()
                
                if 'grok' in m_id_low:
                    chat_models.append(m_id)
                else:
                    other_models.append(m_id)
                    
            print(f"✅ 총 {len(models_data)}개의 모델을 찾았습니다.\n")
            
            print("--- [ xAI 모델 목록 (최신순 내림차순) ] ---")
            
            print(f"\n💬 [ 대화형 모델 (Grok) - 총 {len(chat_models)}개 ]")
            for m in chat_models:
                print(f"   - {m}")
                
            if other_models:
                print(f"\n🧩 [ 기타 모델 - 총 {len(other_models)}개 ]")
                for om in other_models:
                    print(f"   - {om}")
            else:
                print(f"\n기타 모델 없음")
            
        else:
            print("❌ API 오류:", response.status_code)
            print(response.text)
            
    except Exception as e:
        print(f"🚨 오류 발생: {e}")

if __name__ == "__main__":
    test_grok_models()
