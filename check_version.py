# 이 파일을 서버에 올리고 아래 명령어로 실행하세요:
# docker-compose run web python check_version.py

import os
import sys
import google.generativeai as genai
import importlib.metadata

# .env 로드 (API 키 확인용)
from dotenv import load_dotenv
load_dotenv()

def check_environment():
    print("="*50)
    print(" 🕵️‍♂️ 서버 환경 진단 도구")
    print("="*50)

    # 1. 파이썬 버전 확인
    print(f"[1] Python Version: {sys.version.split()[0]}")

    # 2. 라이브러리 버전 확인
    try:
        ver = importlib.metadata.version("google-generativeai")
        print(f"[2] google-generativeai Library Version: {ver}")
        
        # 버전 판단
        major, minor, patch = map(int, ver.split('.')[:3])
        if major == 0 and minor < 8:
            print("    ❌ 경고: 버전이 너무 낮습니다. (0.8.3 이상 필요)")
            print("    -> Docker 캐시 문제일 확률이 99%입니다.")
        else:
            print("    ✅ 통과: 이미지 생성이 가능한 버전입니다.")
            
    except Exception as e:
        print(f"    ❌ 라이브러리를 찾을 수 없음: {e}")

    # 3. Import 테스트
    print(f"[3] Class Import Test")
    try:
        from google.generativeai import ImageGenerationModel
        print("    ✅ ImageGenerationModel 클래스 불러오기 성공!")
    except ImportError:
        print("    ❌ ImageGenerationModel 클래스 불러오기 실패 (업데이트 필수)")

    # 4. 사용 가능한 모델 목록 조회
    print(f"[4] Available Models List (API Key Check)")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("    ❌ .env 파일에서 GOOGLE_API_KEY를 찾을 수 없습니다.")
        return

    try:
        genai.configure(api_key=api_key)
        print("    --> Google API 연결 성공. 모델 목록을 조회합니다...\n")
        
        count = 0
        for m in genai.list_models():
            count += 1
            print(f"    - {m.name}")
            # 지원 기능 확인
            if 'generateContent' in m.supported_generation_methods:
                pass
            if 'image' in m.name or 'imagen' in m.name:
                print(f"      ✨ (이미지 관련 모델 감지됨)")

        print(f"\n    --> 총 {count}개의 모델이 조회되었습니다.")

    except Exception as e:
        print(f"    ❌ 모델 조회 실패: {e}")

if __name__ == "__main__":
    check_environment()