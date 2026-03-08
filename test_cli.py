import os
from dotenv import load_dotenv
load_dotenv()
from services.ai_service import get_anthropic_client
import json

client = get_anthropic_client()
chunk = ["dall-e-3", "gpt-4o", "gpt-4-turbo", "o1", "o1-mini"]

prompt = f"""
다음은 공급사에서 제공하는 AI 모델 ID 전체 목록의 일부입니다:
{json.dumps(chunk)}

요구사항:
0. 중요! 절대 모델 목록 중 일부를 생략하지 말고, 제공된 모델 ID {len(chunk)}개를 하나도 빠짐없이 모두 결과에 포함하세요.
1. 각 모델의 특징과 용도(description)를 1줄 이내로 아주 짧게 요약하세요.
2. 2024~2025년 기준 대략적인 API 100만 토큰당 입력(input)과 출력(output) 예상 비용(USD)을 추정하여 숫자로 적어주세요.
3. 반드시 다음 JSON 배열 형식으로만 응답하고, 마크다운 코드블록 등 다른 설명 텍스트는 일체 생략하세요.

형식:
[
  {{
    "id": "모델ID",
    "name": "일반인이 알아보기 쉬운 모델명",
    "input_price": 5.0,
    "output_price": 15.0,
    "description": "다목적 추론에 최적화된 최신 모델입니다."
  }}
]
"""
try:
    available_claude_models = [m.id for m in client.models.list()]
    claude_model = next((m for m in available_claude_models if "sonnet" in m), available_claude_models[0])
    print("Using model:", claude_model)
    
    response = client.messages.create(
        model=claude_model,
        max_tokens=2000,
        system="You are an AI assistant that only outputs strictly valid JSON arrays.",
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text.strip()
    print("--- RAW TEXT ---")
    print(text)
    print("----------------")
    
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
        
    data = json.loads(text.strip())
    print("Parsed JSON items:", len(data))
except Exception as e:
    import traceback
    traceback.print_exc()
