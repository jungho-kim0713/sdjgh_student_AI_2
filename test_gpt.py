import os
import requests
from dotenv import load_dotenv

# 현재 디렉토리의 .env 파일 로드
load_dotenv()

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

def test_openai_models():
    if not OPENAI_API_KEY:
        print("❌ 오류: .env 파일에서 OPENAI_API_KEY를 찾을 수 없습니다.")
        return

    print("------------------------------------------------")
    print(f"🔑 감지된 OpenAI API 키: {OPENAI_API_KEY[:5]}...{OPENAI_API_KEY[-5:]}")
    print("------------------------------------------------")

    url = "https://api.openai.com/v1/models"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    try:
        print("📋 [OpenAI] 사용 가능한 모델 목록 조회 중...\n")
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            models_data = response.json().get('data', [])
            
            # API 응답에 포함된 'created' 필드(생성일 timestamp) 기준으로 최신순 정렬
            models_data.sort(key=lambda x: x.get('created', 0), reverse=True)
            
            chat_models = []
            image_models = []
            audio_models = []
            embedding_models = []
            other_models = []
            
            # 분류 로직
            for m in models_data:
                m_id = m['id']
                m_id_low = m_id.lower()
                
                if m_id_low.startswith('dall-e') or 'image' in m_id_low:
                    image_models.append(m_id)
                elif m_id_low.startswith('tts-') or m_id_low.startswith('whisper') or m_id_low.startswith('gpt-audio') or m_id_low.startswith('gpt-realtime'):
                    audio_models.append(m_id)
                elif m_id_low.startswith('gpt-') or 'omni' in m_id_low or m_id_low.startswith('o1') or m_id_low.startswith('o3'):
                    chat_models.append(m_id)
                elif 'embedding' in m_id_low:
                    embedding_models.append(m_id)
                else:
                    other_models.append(m_id)
                    
            print(f"✅ 총 {len(models_data)}개의 모델을 찾았습니다.\n")
            
            print("--- [ 용도별 OpenAI 모델 목록 (최신순 내림차순) ] ---")
            
            print(f"\n💬 [ 대화형 모델 (Chat/Reasoning) - 총 {len(chat_models)}개 ]")
            for m in chat_models:
                print(f"   - {m}")
                
            print(f"\n🖼️ [ 이미지 생성 모델 (DALL-E) - 총 {len(image_models)}개 ]")
            if image_models:
                for im in image_models:
                    print(f"   - {im}")
            else:
                print("   - 조회된 모델 없음")

            print(f"\n🔊 [ 음성 모델 (TTS/Whisper) - 총 {len(audio_models)}개 ]")
            if audio_models:
                for am in audio_models:
                    print(f"   - {am}")
            else:
                print("   - 조회된 모델 없음")

            print(f"\n🧩 [ 임베딩 모델 - 총 {len(embedding_models)}개 ]")
            if embedding_models:
                for em in embedding_models:
                    print(f"   - {em}")
            else:
                print("   - 조회된 모델 없음")
                
            print(f"\n기타 모델 (총 {len(other_models)}개)")
            
        else:
            print("❌ API 오류:", response.status_code)
            print(response.text)
            
    except Exception as e:
        print(f"🚨 오류 발생: {e}")

if __name__ == "__main__":
    test_openai_models()
