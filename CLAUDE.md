# 서대전여고 학생용 AI 플랫폼 — 프로젝트 컨텍스트

## 1. 프로젝트 개요

- **서비스명**: 서대전여고 수업용 AI 플랫폼
- **URL**: https://student-ai.sdjgh-ai.kr
- **목적**: 교사가 페르소나와 지식 베이스를 관리하고, 학생이 AI와 채팅하는 교육용 플랫폼
- **GitHub**: https://github.com/jungho-kim0713/sdjgh_student_AI_2.git

## 2. 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | Flask (Python 3.12) + Gunicorn |
| DB | PostgreSQL 15 + pgvector (벡터 검색) |
| 캐시/브로커 | Redis 7 (DB0: Celery, DB1: Flask-Caching) |
| 백그라운드 | Celery (--pool=gevent) |
| 컨테이너 | Docker + Docker Compose |
| AI 모델 | OpenAI GPT-4o / Anthropic Claude / Google Gemini + Imagen |
| 임베딩 | OpenAI text-embedding-3-small (1536차원) |
| 네트워크 | Cloudflare Proxy + HTTPS (Flexible SSL) |

## 3. 인프라 구성

- **서버**: OCI VM.Standard.A1.Flex (ARM/Ampere Altra, OCPU 4, RAM 24GB)
- **OS**: Ubuntu (aarch64)
- **외부 포트**: 8081 → Docker 내부 8080

### Docker Compose 서비스

```
web     : Flask + Gunicorn (--workers 8, --pool gevent, --keep-alive 5)
db      : pgvector/pgvector:pg15 (max_connections=200, port 5432)
redis   : redis:7-alpine (port 6379)
worker  : Celery (--pool=gevent --concurrency=4)
```

> **ARM 주의**: `gevent.monkey.patch_all()`과 Celery prefork가 충돌함. Celery는 반드시 `--pool=gevent` 사용.

### DB 연결 수 계산

(8 Gunicorn + 2 Celery) × (pool_size 8 + max_overflow 8) = 최대 160개 → PostgreSQL max_connections=200으로 여유 40개

## 4. 폴더 구조

```
├── routes/
│   ├── admin.py            # 관리자 기능
│   ├── admin_analyze.py    # 분석 탭 (클래스/학생 분석, 조기 알람)
│   ├── admin_persona.py    # 페르소나 CRUD + 권한 관리
│   ├── admin_users.py      # 사용자 관리
│   ├── auth.py             # 로그인/회원가입 (Google OAuth 포함)
│   ├── chat.py             # 채팅 API (스트리밍 포함)
│   ├── files.py            # 파일 업로드/다운로드
│   └── status.py           # 서비스 상태 관리
├── services/
│   ├── ai_service.py       # AI 모델 통합 (generate_ai_response_stream)
│   ├── alert_service.py    # 조기 개입 알림 (키워드/반복 질문 감지)
│   ├── chunking_service.py # 텍스트 청킹 (paragraph/sentence/fixed)
│   ├── embedding_service.py# OpenAI 임베딩 생성
│   ├── file_service.py     # 파일 처리
│   └── rag_service.py      # RAG 파이프라인
├── templates/
│   ├── index.html          # 메인 채팅 UI
│   ├── admin_persona.html  # 페르소나 관리 UI
│   ├── admin_users.html    # 사용자 관리 UI
│   ├── admin_analyze.html  # 분석 대시보드
│   ├── login.html
│   ├── register.html
│   └── google_register.html
├── static/
│   ├── css/, js/modules/   # 모듈화된 프론트엔드
│   ├── manifest.json       # PWA 매니페스트
│   ├── service-worker.js   # PWA 서비스 워커
│   └── uploads/            # 채팅 파일 + RAG 지식 베이스 문서
├── migrations/             # DB 마이그레이션 SQL
├── app.py                  # Flask 앱 메인 (확장 초기화, 라우트 등록)
├── ai_core.py              # AI 핵심 로직 (스트리밍, 이미지 처리)
├── extensions.py           # Flask 확장 (db, cache 등)
├── models.py               # SQLAlchemy 모델 (RAG 포함)
├── prompts.py              # AI 페르소나 시스템 프롬프트
└── tasks.py                # Celery 백그라운드 작업
```

**Git에서 제외되는 파일** (서버에 별도 관리): `.env`, `certs/`, `static/uploads/`

## 5. 개발 및 배포 명령어

### 로컬 개발 (Windows)

```powershell
# 가상환경 활성화
.\venv\Scripts\Activate.ps1

# Flask만 실행 (UI 확인용, Redis/Celery 불필요)
# → .env에서 CELERY_BROKER_URL 주석 처리 필요
python app.py
# 접속: http://127.0.0.1:8081

# 이미지 생성까지 테스트 시 터미널 3개 필요
# 터미널 1: .\redis_win\redis-server.exe
# 터미널 2: celery -A tasks worker --loglevel=info
# 터미널 3: python app.py
```

### Docker 명령어

```bash
# 로컬(Windows) — sudo 없이
docker-compose up -d                          # 서버 시작
docker-compose restart web                    # 코드 수정 후 재시작
docker-compose up -d --build --force-recreate # Dockerfile/의존성 변경 시
docker-compose down                           # 서버 종료
docker-compose logs -f web                    # 로그 확인

# 서버(Linux OCI) — sudo 필수
sudo docker-compose up -d --build --force-recreate
```

### 서버 배포 (Git 기반)

```bash
# 1. 로컬에서 푸시
git add .  &&  git commit -m "메시지"  &&  git push origin main

# 2. 서버 배포 (원라이너, PowerShell)
git push origin main; ssh oracle-student-ai "cd ~/sdjgh_ai; git pull origin main; docker-compose up -d --build --force-recreate"

# 서버 SSH 접속
ssh oracle-student-ai
cd ~/sdjgh_ai
```

## 6. 환경 변수 (.env 핵심 키)

```
DB_HOST, DB_NAME, DB_USER, DB_PASS
ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY
SECRET_KEY
CELERY_BROKER_URL   ← 로컬 UI 테스트 시 주석 처리
```

> API 키 변경 시 `--force-recreate`로 재시작 필요.

## 7. 완료된 성능 최적화 (중복 작업 방지)

- **DB 풀링**: pool_size=8, max_overflow=8, pool_pre_ping=True, pool_recycle=3600
- **Gunicorn**: workers=8, --reload 제거, --keep-alive 5
- **Celery**: prefork → gevent (ARM 충돌 해결)
- **캐싱**: Flask-Caching + Redis DB1. `get_active_personas_cached()` (60초 TTL), `service_status` (30초 TTL)
- **N+1 쿼리 제거**: admin_persona.py 페르소나 목록 → GROUP BY 집계 쿼리
- **이미지 생성 비동기**: Celery 백그라운드 태스크 + `/api/image_task_status/<task_id>` 폴링
- **임베딩 병렬 처리**: ThreadPoolExecutor(max_workers=5) (tasks.py)
- **이미지 파일 I/O 병렬 로딩**: ai_core.py에서 ThreadPoolExecutor로 병렬 로드

## 8. 개발 히스토리 요약

| Season | 내용 | 상태 |
|--------|------|------|
| 2 | OCI 이관 (GCP → OCI), Docker 도입 | 완료 |
| 3 | 멀티 LLM (GPT/Claude/Gemini), prompts.py 분리 | 완료 |
| 3.5 | 보안 강화 (읽기 전용 모드), 모바일 최적화 | 완료 |
| 4 | AI 화가 (Google Imagen 4.0) | 완료 |
| 5 | 도메인 + HTTPS + 보이스 STT | 완료 |
| 5.5 | 실시간 자막 STT, 스마트 복사 버튼 | 완료 |
| 6 | 코드 모듈화 (app.py → routes/services), Git 배포 | 완료 |
| 6.5 | Imagen 이미지 오류 수정 (이중 base64 decode 제거) | 완료 |
| 7 | RAG 시스템 + 분석 탭 + 조기 알림 + PWA | 진행 중 |

## 9. Season 7 진행 상황

### RAG 시스템
- ✅ Week 1: Docker Compose, DB 마이그레이션, 서비스 레이어 (embedding/chunking/rag)
- ✅ Week 2: 관리자 페르소나 동적 관리 (CRUD + 권한 위임)
- ⏳ Week 3: 교사 대시보드, 시스템 프롬프트 편집 UI, 지식 베이스 관리 UI
- ⏳ Week 4: 문서 벡터화 처리, RAG 검색 통합 (chat.py 수정), 출처 표시 UI

**스마트 인덱싱 (Contextual Retrieval)**: 청크 임베딩 시 Gemini/GPT로 문맥 요약을 생성하여 함께 임베딩 → 검색 품질 향상

### 학습 분석 탭 (완료)
- `routes/admin_analyze.py` — 블루프린트, `/admin/analyze` 페이지 + API 6종
- `templates/admin_analyze.html` — 클래스 분석 / 학생 분석 / 조기 개입 알림 3탭, SSE 스트리밍, multi-provider 모델 선택
- 분석 모델: SystemConfig의 활성화된 모델 목록에서 선택 (Anthropic/OpenAI/Google/xAI)
- `ANALYSIS_MAX_TOKENS = 16000`

### 조기 개입 알림 (완료)
- `services/alert_service.py` — 학생 메시지 저장 후 자동 호출
- 감지 유형 2가지: 혼란 키워드 (1시간 쿨다운), 반복 질문 Jaccard≥0.45 (2시간 쿨다운)
- `models.py`에 `LearningAlert` 테이블 추가 → **DB에 `learning_alert` 테이블 생성 필요**
  ```bash
  docker-compose exec web python -c "from extensions import db; from app import app; app.app_context().push(); db.create_all()"
  ```
- `routes/chat.py`에 감지 훅 추가 (메시지 저장 직후, 예외 무시)

### PWA 지원 (완료)
- `static/manifest.json`, `static/service-worker.js` 추가
- `app.py`에 `/manifest.json`, `/service-worker.js` 루트 라우트 추가 (서비스 워커 scope `/` 필수)
- `templates/index.html` `<head>`에 manifest 링크 및 SW 등록 스크립트 추가
