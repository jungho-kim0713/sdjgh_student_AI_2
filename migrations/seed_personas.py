"""
기존 prompts.py의 페르소나를 DB로 마이그레이션

이 스크립트를 실행하면:
1. prompts.py의 5개 페르소나 → PersonaDefinition 테이블에 저장
2. 각 페르소나의 시스템 프롬프트 → PersonaSystemPrompt 테이블에 저장
3. 시스템 페르소나로 표시 (is_system=True)

사용법:
    python migrations/seed_personas.py
"""

import sys
import os

# 프로젝트 루트를 PYTHONPATH에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db
from models import PersonaDefinition, PersonaSystemPrompt
from prompts import AI_PERSONAS


def seed_personas():
    """기존 페르소나를 DB에 시딩"""

    with app.app_context():
        print("=" * 60)
        print("📚 기존 페르소나 마이그레이션 시작")
        print("=" * 60)

        # 페르소나별 기본 아이콘 매핑
        persona_icons = {
            "wangchobo_tutor": "🎓",
            "ai_principles": "🔬",
            "ai_web_game_maker": "🎮",
            "ai_illustrator": "🎨",
            "general": "💬"
        }

        # 시스템 페르소나로 고정할 role_key 목록
        system_persona_keys = {"ai_illustrator", "general"}

        for role_key, persona_data in AI_PERSONAS.items():
            print(f"\n🔄 처리 중: {role_key} ({persona_data['role_name']})")

            # 1. PersonaDefinition 확인 및 생성
            existing = PersonaDefinition.query.filter_by(role_key=role_key).first()

            if existing:
                print(f"   ⚠️  이미 존재함 → 건너뜀")
                continue

            # 새 페르소나 생성
            persona = PersonaDefinition(
                role_key=role_key,
                role_name=persona_data["role_name"],
                description=persona_data.get("description", ""),
                icon=persona_icons.get(role_key, "🤖"),
                is_system=role_key in system_persona_keys,  # 지정된 페르소나만 시스템
                is_active=True,

                # AI 모델 기본값
                model_openai="gpt-4.1-mini",
                model_anthropic="claude-haiku-4-5-20251001",
                model_google="gemini-2.0-flash",
                max_tokens=4096,

                # 권한 설정
                allow_user=True,
                allow_teacher=True,
                restrict_google=False,
                restrict_anthropic=False,
                restrict_openai=False,

                # RAG 비활성화 (기본 페르소나는 RAG 사용 안 함)
                use_rag=False,
                retrieval_strategy="soft_topk",
                rag_top_k=3,
                rag_max_k=7,
                rag_similarity_threshold=0.5,
                rag_gap_threshold=0.1
            )

            db.session.add(persona)
            db.session.flush()  # ID 생성

            print(f"   ✅ PersonaDefinition 생성 (ID: {persona.id})")

            # 2. PersonaSystemPrompt 생성 (각 provider별로)
            system_prompts = persona_data.get("system_prompts", {})

            for provider, prompt_text in system_prompts.items():
                prompt = PersonaSystemPrompt(
                    persona_id=persona.id,
                    provider=provider,
                    system_prompt=prompt_text
                )
                db.session.add(prompt)
                print(f"      → {provider} 프롬프트 추가")

        # 모든 변경사항 커밋
        db.session.commit()

        print("\n" + "=" * 60)
        print("✅ 마이그레이션 완료!")
        print("=" * 60)

        # 결과 확인
        total_personas = PersonaDefinition.query.count()
        total_prompts = PersonaSystemPrompt.query.count()

        print(f"\n📊 마이그레이션 결과:")
        print(f"   - 총 페르소나 수: {total_personas}개")
        print(f"   - 총 시스템 프롬프트 수: {total_prompts}개")

        print("\n🎯 등록된 페르소나 목록:")
        personas = PersonaDefinition.query.all()
        for p in personas:
            badge = "🔧" if not p.is_system else "⭐"
            print(f"   {badge} {p.icon} {p.role_name} ({p.role_key})")


if __name__ == "__main__":
    try:
        seed_personas()
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
