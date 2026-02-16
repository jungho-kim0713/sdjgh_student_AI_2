"""
AI 공급사별 클라이언트 초기화 및 통합 응답 생성 로직.
라우트에서 공통적으로 호출할 수 있도록 순수 함수 형태로 제공한다.
"""

import os
import base64
import mimetypes

import anthropic
import openai
import google.generativeai as genai
import httpx

# Anthropic 클라이언트는 키가 있을 때만 초기화한다.
anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    try:
        # Anthropic 클라이언트 초기화 (httpx 파라미터 없이)
        anthropic_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    except Exception as e:
        print(f"⚠️ Anthropic Client Init Error: {e}")

# OpenAI 클라이언트는 키가 있을 때만 초기화한다.
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    try:
        # httpx 클라이언트를 명시적으로 생성 (proxies 자동 감지 비활성화)
        http_client = httpx.Client()
        openai_client = openai.OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            http_client=http_client
        )
    except Exception as e:
        print(f"⚠️ OpenAI Client Init Error: {e}")

# Google Gemini는 전역 configure로 키를 등록한다.
if os.getenv("GOOGLE_API_KEY"):
    try:
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    except Exception as e:
        print(f"⚠️ Google Client Init Error: {e}")

# 지원 모델 목록(프론트 관리자 패널에 노출되는 기준)
# 2025년 모델만 포함, 모든 모델에 출시일/가격/특징 포함
AVAILABLE_MODELS = {
    # ===== GPT-4o 검색 특화 (2025년 3월) =====
    "gpt-4o-search-preview": {
        "name": "GPT-4o Search Preview (2025년 3월)",
        "provider": "openai",
        "input_price": 5.00,
        "output_price": 15.00,
        "description": "웹 검색 통합과 실시간 정보 접근 기능"
    },
    "gpt-4o-search-preview-2025-03-11": {
        "name": "GPT-4o Search (2025년 3월 11일)",
        "provider": "openai",
        "input_price": 5.00,
        "output_price": 15.00,
        "description": "2025년 3월 11일 검색 최적화 스냅샷"
    },

    # ===== GPT-4o Mini 2025년 버전 =====
    "gpt-4o-mini-transcribe-2025-12-15": {
        "name": "GPT-4o Mini Transcribe (2025년 12월 15일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "전사 정확도가 개선된 최신 버전"
    },
    "gpt-4o-mini-transcribe-2025-03-20": {
        "name": "GPT-4o Mini Transcribe (2025년 3월 20일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "2025년 3월 20일 스냅샷"
    },
    "gpt-4o-mini-tts": {
        "name": "GPT-4o Mini TTS (2025년)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "저비용 음성 합성(Text-to-Speech) 모델"
    },
    "gpt-4o-mini-tts-2025-12-15": {
        "name": "GPT-4o Mini TTS (2025년 12월 15일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "자연스러운 음성 생성 최적화"
    },
    "gpt-4o-mini-tts-2025-03-20": {
        "name": "GPT-4o Mini TTS (2025년 3월 20일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "2025년 3월 20일 음성 품질 개선 버전"
    },
    "gpt-4o-mini-search-preview": {
        "name": "GPT-4o Mini Search Preview (2025년 3월)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "저비용 웹 검색 통합 모델"
    },
    "gpt-4o-mini-search-preview-2025-03-11": {
        "name": "GPT-4o Mini Search (2025년 3월 11일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "2025년 3월 11일 검색 최적화 스냅샷"
    },

    # ===== Audio/Realtime 전용 (2025년) =====
    "gpt-audio": {
        "name": "GPT Audio (2025년 8월)",
        "provider": "openai",
        "input_price": 0.30,
        "output_price": 0.90,
        "description": "범용 오디오 처리 및 생성 전문 모델"
    },
    "gpt-audio-2025-08-28": {
        "name": "GPT Audio (2025년 8월 28일)",
        "provider": "openai",
        "input_price": 0.30,
        "output_price": 0.90,
        "description": "2025년 8월 28일 오디오 품질 개선 버전"
    },
    "gpt-audio-mini": {
        "name": "GPT Audio Mini (2025년 10월)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "경량 오디오 처리 모델"
    },
    "gpt-audio-mini-2025-10-06": {
        "name": "GPT Audio Mini (2025년 10월 6일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "2025년 10월 6일 스냅샷"
    },
    "gpt-audio-mini-2025-12-15": {
        "name": "GPT Audio Mini (2025년 12월 15일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "2025년 12월 15일 최신 버전"
    },
    "gpt-realtime": {
        "name": "GPT Realtime (2025년 8월)",
        "provider": "openai",
        "input_price": 0.30,
        "output_price": 0.90,
        "description": "실시간 양방향 대화를 위한 저지연 모델"
    },
    "gpt-realtime-2025-08-28": {
        "name": "GPT Realtime (2025년 8월 28일)",
        "provider": "openai",
        "input_price": 0.30,
        "output_price": 0.90,
        "description": "2025년 8월 28일 스냅샷"
    },
    "gpt-realtime-mini": {
        "name": "GPT Realtime Mini (2025년 10월)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "경량 실시간 대화 모델"
    },
    "gpt-realtime-mini-2025-10-06": {
        "name": "GPT Realtime Mini (2025년 10월 6일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "2025년 10월 6일 스냅샷"
    },
    "gpt-realtime-mini-2025-12-15": {
        "name": "GPT Realtime Mini (2025년 12월 15일)",
        "provider": "openai",
        "input_price": 0.15,
        "output_price": 0.45,
        "description": "2025년 12월 15일 최신 버전"
    },
    "gpt-4o-realtime-preview-2025-06-03": {
        "name": "GPT-4o Realtime (2025년 6월 3일)",
        "provider": "openai",
        "input_price": 5.00,
        "output_price": 15.00,
        "description": "2025년 6월 3일 GPT-4o 기반 실시간 모델"
    },
    "gpt-4o-audio-preview-2025-06-03": {
        "name": "GPT-4o Audio (2025년 6월 3일)",
        "provider": "openai",
        "input_price": 5.00,
        "output_price": 15.00,
        "description": "2025년 6월 3일 GPT-4o 기반 오디오 모델"
    },

    # ===== GPT-4.1 시리즈 (2025년 4월) =====
    "gpt-4.1": {
        "name": "GPT-4.1 (2025년 4월)",
        "provider": "openai",
        "input_price": 30.00,
        "output_price": 60.00,
        "description": "GPT-4의 진화 버전, 추론과 코딩 능력 대폭 개선"
    },
    "gpt-4.1-2025-04-14": {
        "name": "GPT-4.1 (2025년 4월 14일)",
        "provider": "openai",
        "input_price": 30.00,
        "output_price": 60.00,
        "description": "2025년 4월 14일 초기 출시 스냅샷"
    },
    "gpt-4.1-mini": {
        "name": "GPT-4.1 Mini (2025년 4월)",
        "provider": "openai",
        "input_price": 0.20,
        "output_price": 0.80,
        "description": "일상 작업에 최적화된 효율적인 GPT-4.1"
    },
    "gpt-4.1-mini-2025-04-14": {
        "name": "GPT-4.1 Mini (2025년 4월 14일)",
        "provider": "openai",
        "input_price": 0.20,
        "output_price": 0.80,
        "description": "2025년 4월 14일 스냅샷"
    },
    "gpt-4.1-nano": {
        "name": "GPT-4.1 Nano (2025년 4월)",
        "provider": "openai",
        "input_price": 0.05,
        "output_price": 0.20,
        "description": "엣지 디바이스와 모바일 앱을 위한 초경량 모델"
    },
    "gpt-4.1-nano-2025-04-14": {
        "name": "GPT-4.1 Nano (2025년 4월 14일)",
        "provider": "openai",
        "input_price": 0.05,
        "output_price": 0.20,
        "description": "2025년 4월 14일 스냅샷"
    },

    # ===== GPT-5 시리즈 (2025년 8월) =====
    "gpt-5": {
        "name": "GPT-5 (2025년 8월)",
        "provider": "openai",
        "input_price": 50.00,
        "output_price": 100.00,
        "description": "OpenAI의 차세대 플래그십, AGI급 추론과 창의성"
    },
    "gpt-5-2025-08-07": {
        "name": "GPT-5 (2025년 8월 7일)",
        "provider": "openai",
        "input_price": 50.00,
        "output_price": 100.00,
        "description": "2025년 8월 7일 초기 출시 스냅샷"
    },
    "gpt-5-chat-latest": {
        "name": "GPT-5 Chat Latest (2025년 8월)",
        "provider": "openai",
        "input_price": 50.00,
        "output_price": 100.00,
        "description": "대화 최적화된 최신 GPT-5 버전"
    },
    "gpt-5-mini": {
        "name": "GPT-5 Mini (2025년 8월)",
        "provider": "openai",
        "input_price": 1.00,
        "output_price": 3.00,
        "description": "GPT-5 기술 기반 효율적인 경량 모델"
    },
    "gpt-5-mini-2025-08-07": {
        "name": "GPT-5 Mini (2025년 8월 7일)",
        "provider": "openai",
        "input_price": 1.00,
        "output_price": 3.00,
        "description": "2025년 8월 7일 스냅샷"
    },
    "gpt-5-nano": {
        "name": "GPT-5 Nano (2025년 8월)",
        "provider": "openai",
        "input_price": 0.10,
        "output_price": 0.30,
        "description": "엣지 배포용 초경량 GPT-5"
    },
    "gpt-5-nano-2025-08-07": {
        "name": "GPT-5 Nano (2025년 8월 7일)",
        "provider": "openai",
        "input_price": 0.10,
        "output_price": 0.30,
        "description": "2025년 8월 7일 스냅샷"
    },
    "gpt-5-codex": {
        "name": "GPT-5 Codex (2025년 8월)",
        "provider": "openai",
        "input_price": 15.00,
        "output_price": 45.00,
        "description": "GPT-5 기반 고급 코드 생성 및 분석 전문 모델"
    },
    "gpt-5-pro": {
        "name": "GPT-5 Pro (2025년 10월)",
        "provider": "openai",
        "input_price": 60.00,
        "output_price": 120.00,
        "description": "GPT-5의 최상위 버전, 전문가급 작업용"
    },
    "gpt-5-pro-2025-10-06": {
        "name": "GPT-5 Pro (2025년 10월 6일)",
        "provider": "openai",
        "input_price": 60.00,
        "output_price": 120.00,
        "description": "2025년 10월 6일 스냅샷"
    },
    "gpt-5-search-api": {
        "name": "GPT-5 Search API (2025년 10월)",
        "provider": "openai",
        "input_price": 50.00,
        "output_price": 100.00,
        "description": "실시간 웹 검색 통합 GPT-5"
    },
    "gpt-5-search-api-2025-10-14": {
        "name": "GPT-5 Search API (2025년 10월 14일)",
        "provider": "openai",
        "input_price": 50.00,
        "output_price": 100.00,
        "description": "2025년 10월 14일 검색 최적화 버전"
    },

    # ===== GPT-5.1 시리즈 (2025년 11월) =====
    "gpt-5.1": {
        "name": "GPT-5.1 (2025년 11월)",
        "provider": "openai",
        "input_price": 55.00,
        "output_price": 110.00,
        "description": "GPT-5의 개선 버전, 성능과 안정성 향상"
    },
    "gpt-5.1-2025-11-13": {
        "name": "GPT-5.1 (2025년 11월 13일)",
        "provider": "openai",
        "input_price": 55.00,
        "output_price": 110.00,
        "description": "2025년 11월 13일 스냅샷"
    },
    "gpt-5.1-chat-latest": {
        "name": "GPT-5.1 Chat Latest (2025년 11월)",
        "provider": "openai",
        "input_price": 55.00,
        "output_price": 110.00,
        "description": "대화 최적화된 최신 GPT-5.1"
    },
    "gpt-5.1-codex": {
        "name": "GPT-5.1 Codex (2025년 11월)",
        "provider": "openai",
        "input_price": 18.00,
        "output_price": 54.00,
        "description": "GPT-5.1 기반 코드 생성 전문 모델"
    },
    "gpt-5.1-codex-mini": {
        "name": "GPT-5.1 Codex Mini (2025년 11월)",
        "provider": "openai",
        "input_price": 2.00,
        "output_price": 6.00,
        "description": "경량 코드 생성 모델"
    },
    "gpt-5.1-codex-max": {
        "name": "GPT-5.1 Codex Max (2025년 11월)",
        "provider": "openai",
        "input_price": 25.00,
        "output_price": 75.00,
        "description": "최대 성능 코드 생성 모델"
    },

    # ===== GPT-5.2 시리즈 (2025년 12월) =====
    "gpt-5.2": {
        "name": "GPT-5.2 (2025년 12월)",
        "provider": "openai",
        "input_price": 60.00,
        "output_price": 120.00,
        "description": "최신 GPT-5.2, 멀티모달 통합 강화"
    },
    "gpt-5.2-2025-12-11": {
        "name": "GPT-5.2 (2025년 12월 11일)",
        "provider": "openai",
        "input_price": 60.00,
        "output_price": 120.00,
        "description": "2025년 12월 11일 스냅샷"
    },
    "gpt-5.2-chat-latest": {
        "name": "GPT-5.2 Chat Latest (2025년 12월)",
        "provider": "openai",
        "input_price": 60.00,
        "output_price": 120.00,
        "description": "대화 최적화 최신 버전"
    },
    "gpt-5.2-codex": {
        "name": "GPT-5.2 Codex (2025년 12월)",
        "provider": "openai",
        "input_price": 20.00,
        "output_price": 60.00,
        "description": "최신 코드 생성 및 분석 전문 모델"
    },
    "gpt-5.2-pro": {
        "name": "GPT-5.2 Pro (2025년 12월)",
        "provider": "openai",
        "input_price": 70.00,
        "output_price": 140.00,
        "description": "GPT-5.2의 프로페셔널 버전"
    },
    "gpt-5.2-pro-2025-12-11": {
        "name": "GPT-5.2 Pro (2025년 12월 11일)",
        "provider": "openai",
        "input_price": 70.00,
        "output_price": 140.00,
        "description": "2025년 12월 11일 스냅샷"
    },

    # ===== 이미지 모델 (2025년) =====
    "gpt-image-1": {
        "name": "GPT Image 1 (2025년)",
        "provider": "openai",
        "input_price": 0.50,
        "output_price": 1.00,
        "description": "이미지 이해, 분석, 캡셔닝 전문 모델"
    },
    "gpt-image-1-mini": {
        "name": "GPT Image 1 Mini (2025년)",
        "provider": "openai",
        "input_price": 0.10,
        "output_price": 0.30,
        "description": "경량 이미지 분석 모델"
    },
    "gpt-image-1.5": {
        "name": "GPT Image 1.5 (2025년)",
        "provider": "openai",
        "input_price": 0.80,
        "output_price": 1.60,
        "description": "향상된 이미지 이해 및 생성 기능"
    },

    # ===== Anthropic Models - Claude 4.x Series =====
    "claude-opus-4-6": {
        "name": "Claude Opus 4.6 (2025년)",
        "provider": "anthropic",
        "input_price": 15.00,
        "output_price": 75.00,
        "description": "향상된 추론 능력을 갖춘 최신 최고급 Claude 모델"
    },
    "claude-opus-4-5-20251101": {
        "name": "Claude Opus 4.5 (2025년 11월)",
        "provider": "anthropic",
        "input_price": 15.00,
        "output_price": 75.00,
        "description": "강력한 분석 능력을 갖춘 이전 세대 Opus 모델"
    },
    "claude-sonnet-4-5-20250929": {
        "name": "Claude Sonnet 4.5 (2025년 9월)",
        "provider": "anthropic",
        "input_price": 3.00,
        "output_price": 15.00,
        "description": "다양한 작업에서 균형잡힌 성능을 제공하는 모델"
    },
    "claude-haiku-4-5-20251001": {
        "name": "Claude Haiku 4.5 (2025년 10월)",
        "provider": "anthropic",
        "input_price": 1.00,
        "output_price": 5.00,
        "description": "즉각적인 응답과 대량 처리를 위한 초고속 모델"
    },
    "claude-opus-4-20250514": {
        "name": "Claude Opus 4.0 (2025년 5월)",
        "provider": "anthropic",
        "input_price": 15.00,
        "output_price": 75.00,
        "description": "까다로운 분석 작업을 위한 강력한 Opus 4.0 모델"
    },
    "claude-sonnet-4-20250514": {
        "name": "Claude Sonnet 4.0 (2025년 5월)",
        "provider": "anthropic",
        "input_price": 3.00,
        "output_price": 15.00,
        "description": "성능과 비용의 균형을 위한 다목적 Sonnet 4.0 모델"
    },
    "claude-opus-4-1-20250805": {
        "name": "Claude Opus 4.1 (2025년 8월)",
        "provider": "anthropic",
        "input_price": 15.00,
        "output_price": 75.00,
        "description": "복잡한 분석과 창의적 작업을 위한 개선된 Opus 4.1 모델"
    },

    # ===== Anthropic Models - Claude 3.x Series =====
    "claude-3-7-sonnet-20250219": {
        "name": "Claude 3.7 Sonnet (2025년 2월)",
        "provider": "anthropic",
        "input_price": 3.00,
        "output_price": 15.00,
        "description": "향상된 기능을 갖춘 고급 Claude 3.7 Sonnet 모델"
    },
    "claude-3-5-haiku-20241022": {
        "name": "Claude 3.5 Haiku (2024년 10월)",
        "provider": "anthropic",
        "input_price": 0.80,
        "output_price": 4.00,
        "description": "빠른 응답을 위한 효율적인 Claude 3.5 Haiku 모델"
    },
    "claude-3-haiku-20240307": {
        "name": "Claude 3 Haiku (2024년 3월)",
        "provider": "anthropic",
        "input_price": 0.25,
        "output_price": 1.25,
        "description": "비용 효율적인 기본 작업을 위한 레거시 Claude 3 Haiku 모델"
    },

    # ===== Google Models - Gemini 2.5 Series (2025년 2월) =====
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash (2025년 2월)",
        "provider": "google",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "빠른 응답 속도와 멀티모달 처리를 위한 경량 Gemini 2.5 모델"
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro (2025년 2월)",
        "provider": "google",
        "input_price": 1.25,
        "output_price": 5.00,
        "description": "복잡한 추론과 분석 작업을 위한 전문가급 Gemini 2.5 모델"
    },
    "gemini-2.5-flash-preview-tts": {
        "name": "Gemini 2.5 Flash TTS (2025년 2월)",
        "provider": "google",
        "input_price": 0.15,
        "output_price": 0.60,
        "description": "Gemini 2.5 Flash 기반 음성 합성(Text-to-Speech) 프리뷰"
    },
    "gemini-2.5-pro-preview-tts": {
        "name": "Gemini 2.5 Pro TTS (2025년 2월)",
        "provider": "google",
        "input_price": 1.25,
        "output_price": 5.00,
        "description": "Gemini 2.5 Pro 기반 고품질 음성 합성 프리뷰"
    },

    # ===== Google Models - Gemini 3.0 Series (2025년 6월) =====
    "gemini-3-flash-preview": {
        "name": "Gemini 3 Flash (2025년 6월)",
        "provider": "google",
        "input_price": 0.0,
        "output_price": 0.0,
        "description": "차세대 멀티모달 AI, 빠른 응답과 향상된 이해 능력 (프리뷰 무료)"
    },
    "gemini-3-pro-preview": {
        "name": "Gemini 3 Pro (2025년 6월)",
        "provider": "google",
        "input_price": 0.0,
        "output_price": 0.0,
        "description": "최고 수준의 추론과 창의성을 위한 Gemini 3 플래그십 (프리뷰 무료)"
    },

    # ===== Google Models - Image Generation (2025년) =====
    "gemini-2.5-flash-image": {
        "name": "Gemini 2.5 Flash Image (2025년 3월)",
        "provider": "google",
        "input_price": 0.02,
        "output_price": 0.02,
        "description": "빠른 속도와 개선된 품질의 Gemini 2.5 이미지 생성 모델"
    },
    "gemini-3-pro-image-preview": {
        "name": "Gemini 3.0 Pro Image (2025년 6월)",
        "provider": "google",
        "input_price": 0.03,
        "output_price": 0.03,
        "description": "세밀한 제어와 전문가급 품질의 Gemini 3.0 이미지 생성"
    },
    "imagen-4.0-generate-001": {
        "name": "Imagen 4.0 (2025년 5월)",
        "provider": "google",
        "input_price": 0.04,
        "output_price": 0.04,
        "description": "사진급 품질의 최첨단 이미지 생성 전문 모델"
    },

    # ===== Google Models - Gemma (On-device/Edge) (2025년 7월) =====
    "gemma-3-1b-it": {
        "name": "Gemma 3 1B (2025년 7월)",
        "provider": "google",
        "input_price": 0.0,
        "output_price": 0.0,
        "description": "온디바이스 배포를 위한 1B 파라미터 경량 모델 (무료)"
    },
    "gemma-3-4b-it": {
        "name": "Gemma 3 4B (2025년 7월)",
        "provider": "google",
        "input_price": 0.0,
        "output_price": 0.0,
        "description": "향상된 성능의 4B 파라미터 온디바이스 모델 (무료)"
    },
}

# 공급사별 기본 모델 아이디(모델 정보 누락 시 fallback)
DEFAULT_MODELS = {
    "openai": "gpt-4.1-mini",
    "anthropic": "claude-haiku-4-5-20251001",
    "google": "gemini-3-flash-preview",
}
DEFAULT_MODEL = DEFAULT_MODELS["anthropic"]
DEFAULT_MAX_TOKENS = 4096


def generate_ai_response(model_id, system_prompt, messages, max_tokens, upload_folder):
    """
    여러 공급사에 대한 통합 응답 생성 함수.

    Args:
        model_id: 사용자가 선택한 모델 ID(존재하지 않으면 공급사 기본 모델로 대체).
        system_prompt: 시스템 프롬프트(페르소나별 정책 메시지).
        messages: role/content/image_paths가 포함된 대화 기록.
        max_tokens: 응답 길이 제한.
        upload_folder: 이미지 파일이 저장된 업로드 루트 경로.
    """
    model_info = AVAILABLE_MODELS.get(model_id)
    if not model_info:
        if "gpt" in model_id:
            model_id = DEFAULT_MODELS["openai"]
        elif "claude" in model_id:
            model_id = DEFAULT_MODELS["anthropic"]
        elif "gemini" in model_id:
            model_id = DEFAULT_MODELS["google"]
        else:
            model_id = DEFAULT_MODELS["anthropic"]
        model_info = AVAILABLE_MODELS[model_id]

    # 모델 소유 공급사를 기준으로 분기한다.
    provider = model_info["provider"]

    if provider == "anthropic":
        # Anthropic 메시지 포맷(텍스트+이미지)을 구성한다.
        if not anthropic_client:
            raise ValueError("Anthropic API Key가 없거나 초기화되지 않았습니다.")
        anthropic_messages = []
        for msg in messages:
            content_list = []
            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                # 로컬 파일을 base64로 읽어 Anthropic 이미지 형식으로 변환
                try:
                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    with open(full_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                        media_type = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": img_data},
                        })
                except Exception as e:
                    print(f"Anthropic Image Load Warning: {e}")

            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                content_list.extend(msg_content)
            elif isinstance(msg_content, str) and msg_content.strip():
                content_list.append({"type": "text", "text": msg_content})

            if content_list:
                anthropic_messages.append({"role": msg["role"], "content": content_list})

        response = anthropic_client.messages.create(
            model=model_id, max_tokens=max_tokens, system=system_prompt, messages=anthropic_messages
        )
        return response.content[0].text

    if provider == "openai":
        # OpenAI 메시지 포맷(텍스트+이미지)을 구성한다.
        if not openai_client:
            raise ValueError("OpenAI API Key가 없거나 초기화되지 않았습니다.")
        openai_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            content_list = []
            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                content_list.extend(msg_content)
            elif isinstance(msg_content, str) and msg_content:
                content_list.append({"type": "text", "text": msg_content})

            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                # OpenAI는 data URL 방식으로 이미지를 전달한다.
                try:
                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    with open(full_path, "rb") as f:
                        img_b64 = base64.b64encode(f.read()).decode("utf-8")
                        mime = mimetypes.guess_type(full_path)[0] or "image/jpeg"
                        content_list.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                        })
                except Exception:
                    pass

            if content_list:
                openai_messages.append({"role": msg["role"], "content": content_list})

        response = openai_client.chat.completions.create(
            model=model_id, messages=openai_messages, max_tokens=max_tokens
        )
        return response.choices[0].message.content

    if provider == "google":
        # Gemini는 safety 설정과 history 기반 대화 세션을 사용한다.
        if not os.getenv("GOOGLE_API_KEY"):
            raise ValueError("Google API Key가 없습니다.")

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        gen_config = genai.types.GenerationConfig(max_output_tokens=max_tokens)
        gemini_model = genai.GenerativeModel(model_id, system_instruction=system_prompt)

        chat_history = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            parts = []
            msg_content = msg.get("content")
            if isinstance(msg_content, list):
                for item in msg_content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item["text"])
            elif isinstance(msg_content, str) and msg_content:
                parts.append(msg_content)

            img_paths = msg.get("image_paths", [])
            if not img_paths and msg.get("image_path"):
                img_paths = [msg.get("image_path")]

            for img_path in img_paths:
                try:
                    import PIL.Image

                    relative_path = img_path.replace("uploads/", "", 1)
                    full_path = os.path.join(upload_folder, relative_path)
                    img = PIL.Image.open(full_path)
                    parts.append(img)
                except Exception as e:
                    print(f"Gemini Image Load Error: {e}")

            if parts:
                chat_history.append({"role": role, "parts": parts})

        try:
            # 마지막 메시지를 사용자 입력으로 보고 나머지는 history로 전달한다.
            if chat_history and chat_history[-1]["role"] == "user":
                last_msg = chat_history.pop()
                chat_session = gemini_model.start_chat(history=chat_history)
                response = chat_session.send_message(
                    last_msg["parts"], generation_config=gen_config, safety_settings=safety_settings
                )
                return response.text
            chat_session = gemini_model.start_chat(history=chat_history)
            response = chat_session.send_message(
                "Please continue.", generation_config=gen_config, safety_settings=safety_settings
            )
            return response.text
        except ValueError as e:
            print(f"Gemini ValueError: {e}")
            # ValueError는 보통 response.text 접근 시 발생 (candidates가 비어있거나 안전 차단)
            return "⚠️ [Google Gemini Error] 안전 정책에 의해 답변이 차단되었습니다."
        except Exception as e:
            print(f"Gemini API Error details: {e}")
            raise e

    return "Error: Provider not supported"
