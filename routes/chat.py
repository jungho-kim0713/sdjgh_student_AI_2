import os
import traceback
import types

from flask import Blueprint, jsonify, request, render_template, url_for, current_app, Response, stream_with_context
from flask_login import login_required, current_user
import json
from models import (
    ChatSession,
    Message,
    ChatFile,
    SystemConfig,
    PersonaConfig,
    User,
    PersonaDefinition,
    PersonaSystemPrompt,
    PersonaStudentPermission,
    PersonaTeacherPermission,
)
from services.ai_service import (
    generate_ai_response_stream,
    DEFAULT_MODELS,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
    AVAILABLE_MODELS,
)
from extensions import db, cache
from tasks import generate_image_async

# ======================================================
# 캐시 헬퍼 (Redis, TTL 60초)
# ======================================================
_PERSONA_CACHE_KEY = 'active_personas'

def _persona_to_dict(p):
    return {
        'id': p.id, 'role_key': p.role_key, 'role_name': p.role_name,
        'description': p.description, 'icon': p.icon, 'is_system': p.is_system,
        'is_active': p.is_active, 'sort_order': p.sort_order,
        'model_openai': p.model_openai, 'model_anthropic': p.model_anthropic,
        'model_google': p.model_google, 'model_xai': p.model_xai,
        'max_tokens': p.max_tokens, 'allow_user': p.allow_user,
        'allow_teacher': p.allow_teacher, 'restrict_google': p.restrict_google,
        'restrict_anthropic': p.restrict_anthropic, 'restrict_openai': p.restrict_openai,
        'restrict_xai': p.restrict_xai, 'use_rag': p.use_rag,
    }

def get_active_personas_cached():
    """활성 페르소나 목록 (60초 Redis 캐시). SimpleNamespace 리스트 반환."""
    data = cache.get(_PERSONA_CACHE_KEY)
    if data is None:
        personas = PersonaDefinition.query.filter_by(is_active=True).order_by(
            PersonaDefinition.sort_order.asc(), PersonaDefinition.id.asc()
        ).all()
        data = [_persona_to_dict(p) for p in personas]
        cache.set(_PERSONA_CACHE_KEY, data, timeout=60)
    return [types.SimpleNamespace(**d) for d in data]

chat_bp = Blueprint("chat", __name__)


# ======================================================
# 헬퍼 함수: DB 기반 페르소나 조회
# ======================================================
def get_persona_from_db(role_key):
    """DB에서 페르소나 조회 (활성화된 것만)"""
    return PersonaDefinition.query.filter_by(role_key=role_key, is_active=True).first()


def get_system_prompt_from_db(persona_id, provider):
    """DB에서 시스템 프롬프트 조회 (provider별, fallback to default)"""
    # 먼저 해당 provider 프롬프트 찾기
    prompt = PersonaSystemPrompt.query.filter_by(
        persona_id=persona_id,
        provider=provider
    ).first()

    if prompt:
        return prompt.system_prompt

    # 없으면 default 프롬프트 fallback
    default_prompt = PersonaSystemPrompt.query.filter_by(
        persona_id=persona_id,
        provider="default"
    ).first()

    return default_prompt.system_prompt if default_prompt else ""


@chat_bp.route("/")
@login_required
def index():
    """메인 채팅 화면 렌더링.

    - 권한: 로그인 사용자
    - 전달: 관리자 여부, 사용자명, 사용자 역할, 교사 패널 접근 여부
    """
    # 교사 패널 접근 권한 체크 (관리 교사 여부)
    is_teacher_manager = False
    if not current_user.is_admin and current_user.role == 'teacher':
        is_teacher_manager = True

    # 페르소나 목록을 서버에서 미리 렌더링 (초기 로딩 시 빈 드롭다운 깜빡임 방지)
    all_active = get_active_personas_cached()
    if current_user.is_admin or getattr(current_user, 'role', '') == 'admin':
        initial_personas = all_active
    else:
        # 학생 배정 사전 조회 (N+1 방지)
        student_restricted_ids = {
            r[0] for r in db.session.query(PersonaStudentPermission.persona_id).distinct().all()
        }
        my_student_ids = {
            r[0] for r in db.session.query(PersonaStudentPermission.persona_id)
                .filter(PersonaStudentPermission.student_id == current_user.id).all()
        }
        # 교사 배정 사전 조회
        teacher_restricted_ids = {
            r[0] for r in db.session.query(PersonaTeacherPermission.persona_id).distinct().all()
        }
        my_teacher_ids = {
            r[0] for r in db.session.query(PersonaTeacherPermission.persona_id)
                .filter(PersonaTeacherPermission.teacher_id == current_user.id).all()
        }
        initial_personas = []
        for p in all_active:
            if getattr(current_user, 'role', '') == 'teacher':
                # 관리 교사 배정이 있으면 → 배정된 교사만, 없으면 allow_teacher 적용
                if p.id in teacher_restricted_ids:
                    if p.id in my_teacher_ids:
                        initial_personas.append(p)
                elif p.allow_teacher:
                    initial_personas.append(p)
            else:
                # 학생 배정이 있으면 → 배정된 학생만, 없으면 allow_user 적용
                if p.id in student_restricted_ids:
                    if p.id in my_student_ids:
                        initial_personas.append(p)
                elif p.allow_user:
                    initial_personas.append(p)

    return render_template(
        "index.html",
        is_admin=current_user.is_admin,
        current_username=current_user.username,
        current_user_role=getattr(current_user, "role", "user"),
        is_teacher_manager=is_teacher_manager,
        initial_personas=initial_personas
    )


@chat_bp.route("/api/get_persona_visibility", methods=["GET"])
@login_required
def get_persona_visibility():
    """페르소나 가시성 목록 제공 (DB 기반).

    - 권한: 로그인 사용자
    - 관리자: 전체 활성화된 페르소나 반환
    - 일반 사용자: allow_user/allow_teacher 설정에 따라 필터링
    """
    all_cached = get_active_personas_cached()

    if current_user.is_admin:
        # 관리자: 모든 활성화된 페르소나
        return jsonify({
            "personas": [
                {"role_key": p.role_key, "role_name": p.role_name, "icon": p.icon, "use_rag": p.use_rag}
                for p in all_cached
            ]
        })

    # 사용자 역할에 맞는 페르소나만 선별
    user_role = getattr(current_user, "role", "user") or "user"
    personas = all_cached

    # 배정 정보 사전 조회 (N+1 방지)
    student_restricted_ids = {
        r[0] for r in db.session.query(PersonaStudentPermission.persona_id).distinct().all()
    }
    my_student_ids = {
        r[0] for r in db.session.query(PersonaStudentPermission.persona_id)
            .filter(PersonaStudentPermission.student_id == current_user.id).all()
    }
    teacher_restricted_ids = {
        r[0] for r in db.session.query(PersonaTeacherPermission.persona_id).distinct().all()
    }
    my_teacher_ids = {
        r[0] for r in db.session.query(PersonaTeacherPermission.persona_id)
            .filter(PersonaTeacherPermission.teacher_id == current_user.id).all()
    }

    allowed = []
    for p in personas:
        if user_role == "teacher":
            # 관리 교사 배정 있으면 → 배정된 교사만, 없으면 allow_teacher 적용
            if p.id in teacher_restricted_ids:
                is_allowed = p.id in my_teacher_ids
            else:
                is_allowed = p.allow_teacher
        else:  # user
            # 학생 배정 있으면 → 배정된 학생만, 없으면 allow_user 적용
            if p.id in student_restricted_ids:
                is_allowed = p.id in my_student_ids
            else:
                is_allowed = p.allow_user

        if is_allowed:
            allowed.append({
                "role_key": p.role_key,
                "role_name": p.role_name,
                "icon": p.icon or "🤖",
                "description": p.description or "",
                "use_rag": p.use_rag
            })

    return jsonify({"personas": allowed})


@chat_bp.route("/api/get_persona_provider_restrictions", methods=["GET"])
@login_required
def get_persona_provider_restrictions():
    """페르소나별 공급사 제한 정보를 반환한다 (DB 기반).

    - 권한: 로그인 사용자
    - 입력: role_key (query param)
    - 응답: restrict_google/restrict_anthropic/restrict_openai
    """
    role_key = request.args.get("role_key")
    if not role_key:
        return jsonify({
            "restrict_google": False,
            "restrict_anthropic": False,
            "restrict_openai": False,
            "restrict_xai": False,
        })
        
    persona = PersonaDefinition.query.filter_by(role_key=role_key, is_active=True).first()

    if not persona:
        return jsonify({"error": "Invalid role"}), 400

    data = {
        "restrict_google": persona.restrict_google,
        "restrict_anthropic": persona.restrict_anthropic,
        "restrict_openai": persona.restrict_openai,
        "restrict_xai": persona.restrict_xai,
    }
    return jsonify(data)


@chat_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    """채팅 요청 처리(텍스트/이미지 생성).

    - 권한: 로그인 사용자
    - 기능: 서비스 점검 체크 → 페르소나/권한 검증 → 세션 생성 → 메시지 저장 → AI 응답 생성
    """
    # 서비스 점검 모드면 즉시 차단 (30초 캐시)
    _svc_status = cache.get('service_status')
    if _svc_status is None:
        _cfg = SystemConfig.query.filter_by(key="service_status").first()
        _svc_status = _cfg.value if _cfg else "active"
        cache.set('service_status', _svc_status, timeout=30)
    if _svc_status == "inactive":
        return jsonify({"response": "서비스 점검 중입니다."})

    # 요청 데이터 추출
    data = request.json
    role_key = data.get("model")
    provider = data.get("provider", "anthropic")
    user_message = data.get("message")
    file_ids = data.get("file_ids", [])

    # 이미지 생성 페르소나: 별도 플로우로 처리
    if role_key == "ai_illustrator":
        try:
            # DB에서 페르소나 조회
            persona = get_persona_from_db(role_key)
            if not persona:
                return jsonify({"error": "페르소나를 찾을 수 없습니다"}), 404

            # 권한 확인
            if not current_user.is_admin:
                if provider == "google" and persona.restrict_google:
                    return jsonify({"error": "권한 없음"}), 403
                if provider == "anthropic" and persona.restrict_anthropic:
                    return jsonify({"error": "권한 없음"}), 403
                if provider == "openai" and persona.restrict_openai:
                    return jsonify({"error": "권한 없음"}), 403
                if provider == "xai" and persona.restrict_xai:
                    return jsonify({"error": "권한 없음"}), 403

            session_id = data.get("session_id")
            if not session_id:
                # 새 세션 생성(이미지 생성 전용 제목)
                title = f"그림 생성: {user_message[:20]}" if user_message else "그림 생성"
                current_session = ChatSession(
                    title=title, user_id=current_user.id, role_key=role_key
                )
                db.session.add(current_session)
                db.session.flush()
                session_id = current_session.id

            # 사용자 메시지 저장
            db.session.add(
                Message(
                    session_id=session_id,
                    user_id=current_user.id,
                    is_user=True,
                    content=user_message,
                    provider=provider,
                )
            )
            db.session.commit()

            # 조기 개입 알림 감지 (채팅 흐름에 영향 없도록 예외 무시)
            try:
                from services.alert_service import check_and_create_alerts
                check_and_create_alerts(current_user.id, session_id, role_key, user_message)
            except Exception:
                pass

            # 페르소나 설정에서 선택된 모델을 사용한다.
            selected_model_id = DEFAULT_MODEL
            if provider == "openai":
                selected_model_id = persona.model_openai
            elif provider == "google":
                selected_model_id = persona.model_google
            elif provider == "anthropic":
                selected_model_id = persona.model_anthropic
            elif provider == "xai":
                selected_model_id = persona.model_xai

            # Imagen 4.0 선택 시 대화/프롬프트는 Gemini 3 Pro로 고정
            prompt_model_id = selected_model_id
            if provider == "google" and selected_model_id == "imagen-4.0-generate-001":
                prompt_model_id = "gemini-3-pro-preview"
            elif provider == "openai" and selected_model_id in ("gpt-image-1.5", "dall-e-3"):
                prompt_model_id = "gpt-4.1-mini"
            elif provider == "xai" and selected_model_id in ("grok-imagine-image", "grok-imagine-video"):
                # xAI 이미지 프롬프트 생성용으로는 일반 grok 모델 사용
                prompt_model_id = "grok-4-1-fast-reasoning"

            # 시스템 프롬프트 조회
            system_prompt = get_system_prompt_from_db(persona.id, provider)

            if provider == "anthropic":
                def generate_unsupported():
                    chunk = "Claude(Anthropic)는 아직 이미지 생성을 지원하지 않습니다. Google이나 GPT를 선택해주세요."
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"
                return Response(stream_with_context(generate_unsupported()), mimetype="text/event-stream")

            # Celery 백그라운드 태스크로 이미지 생성 위임 (워커 블로킹 방지)
            task = generate_image_async.delay(
                session_id=session_id,
                user_id=current_user.id,
                provider=provider,
                selected_model_id=selected_model_id,
                prompt_model_id=prompt_model_id,
                system_prompt=system_prompt,
                user_message=user_message,
                upload_folder=current_app.config["UPLOAD_FOLDER"],
            )

            # 즉시 task_id 반환 → 프론트가 폴링해서 완료 확인
            def generate_task_queued():
                yield f"data: {json.dumps({'task_id': task.id, 'session_id': session_id, 'image_pending': True})}\n\n"
                yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

            return Response(stream_with_context(generate_task_queued()), mimetype="text/event-stream")

        except Exception as e:
            print(f"Image Gen Error: {e}")
            def generate_error_stream():
                yield f"data: {json.dumps({'error': f'이미지 생성 실패: {str(e)}'})}\n\n"
            return Response(stream_with_context(generate_error_stream()), mimetype="text/event-stream")

    image_paths_for_ai = []

    # 업로드된 파일 중 이미지 경로만 AI 입력으로 전달
    if file_ids:
        files = ChatFile.query.filter(ChatFile.id.in_(file_ids)).all()
        for f in files:
            if f and f.user_id == current_user.id:
                if data.get("session_id"):
                    f.session_id = data.get("session_id")
                if f.file_type and f.file_type.startswith("image/"):
                    image_paths_for_ai.append(f.storage_path)

    # DB에서 페르소나 조회
    persona = get_persona_from_db(role_key)
    if not persona:
        return jsonify({"error": "Invalid persona"}), 400

    # 관리자 제외: 페르소나 접근 권한 체크
    if not current_user.is_admin:
        user_role = getattr(current_user, "role", "user") or "user"

        # 사용자 역할별 접근 권한 확인
        if user_role == "user":
            # 학생 배정이 있으면 배정된 학생만, 없으면 allow_user 적용
            has_student_assignments = PersonaStudentPermission.query.filter_by(
                persona_id=persona.id
            ).first() is not None
            if has_student_assignments:
                is_allowed = PersonaStudentPermission.query.filter_by(
                    persona_id=persona.id, student_id=current_user.id
                ).first() is not None
            else:
                is_allowed = persona.allow_user
        else:  # teacher
            # 관리 교사 배정이 있으면 배정된 교사만, 없으면 allow_teacher 적용
            has_teacher_assignments = PersonaTeacherPermission.query.filter_by(
                persona_id=persona.id
            ).first() is not None
            if has_teacher_assignments:
                is_allowed = PersonaTeacherPermission.query.filter_by(
                    persona_id=persona.id, teacher_id=current_user.id
                ).first() is not None
            else:
                is_allowed = persona.allow_teacher

        if not is_allowed:
            return jsonify({"error": "권한 없음"}), 403

        # 페르소나별 공급사 제한 체크
        if provider == "google" and persona.restrict_google:
            return jsonify({"error": "권한 없음"}), 403
        if provider == "anthropic" and persona.restrict_anthropic:
            return jsonify({"error": "권한 없음"}), 403
        if provider == "openai" and persona.restrict_openai:
            return jsonify({"error": "권한 없음"}), 403
        if provider == "xai" and persona.restrict_xai:
            return jsonify({"error": "권한 없음"}), 403

    # 시스템 프롬프트 조회
    system_prompt = get_system_prompt_from_db(persona.id, provider)

    # 페르소나 설정에 따라 모델 선택
    selected_model_id = DEFAULT_MODEL
    if provider == "openai":
        selected_model_id = persona.model_openai
    elif provider == "google":
        selected_model_id = persona.model_google
    elif provider == "anthropic":
        selected_model_id = persona.model_anthropic
    elif provider == "xai":
        selected_model_id = persona.model_xai

    # 모델이 유효하지 않으면 기본값으로 폴백
    if selected_model_id not in AVAILABLE_MODELS:
        if provider == "openai":
            selected_model_id = DEFAULT_MODELS["openai"]
        elif provider == "google":
            selected_model_id = DEFAULT_MODELS["google"]
        elif provider == "xai":
            selected_model_id = DEFAULT_MODELS.get("xai", "grok-4-1-fast-reasoning")
        else:
            selected_model_id = DEFAULT_MODELS["anthropic"]

    selected_max_tokens = persona.max_tokens

    try:
        session_id = data.get("session_id")

        if session_id:
            # 기존 세션 사용 시 소유자 검증
            current_session = db.session.get(ChatSession, session_id)
            if not current_session:
                return jsonify({"error": "Session not found"}), 404
            if current_session.user_id != current_user.id:
                return jsonify({"error": "권한 없음"}), 403
        else:
            # 새 세션 생성
            title = user_message[:30] if user_message else "새 대화"
            current_session = ChatSession(
                title=title, user_id=current_user.id, role_key=role_key
            )
            db.session.add(current_session)
            db.session.flush()
            session_id = current_session.id
            # 첨부 파일에 세션 ID 연결
            if file_ids:
                files = ChatFile.query.filter(ChatFile.id.in_(file_ids)).all()
                for f in files:
                    if f.user_id == current_user.id:
                        f.session_id = session_id

        # 세션 내 기존 메시지 조회(대화 문맥용)
        db_messages = (
            Message.query.filter_by(session_id=session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

        history_for_api = []
        for msg in db_messages:
            role = "user" if msg.is_user else "assistant"
            msg_image_paths = []
            if msg.image_path:
                msg_image_paths = msg.image_path.split(",")

            item = {"role": role, "content": msg.content, "image_paths": msg_image_paths}

            # 연속된 동일 역할 메시지는 합쳐서 전송(토큰 절감)
            if history_for_api and history_for_api[-1]["role"] == role:
                prev_content = history_for_api[-1]["content"] or ""
                curr_content = item["content"] or ""
                history_for_api[-1]["content"] = prev_content + "\n\n" + curr_content
                history_for_api[-1]["image_paths"].extend(item["image_paths"])
            else:
                history_for_api.append(item)

        final_messages = []
        for m in history_for_api:
            final_messages.append(m)

        # 현재 사용자 메시지를 마지막에 추가
        final_messages.append(
            {
                "role": "user",
                "content": user_message,
                "image_paths": image_paths_for_ai,
            }
        )

        saved_img_path_str = ",".join(image_paths_for_ai) if image_paths_for_ai else None

        # 사용자 메시지를 DB에 저장
        db.session.add(
            Message(
                session_id=session_id,
                user_id=current_user.id,
                is_user=True,
                content=user_message,
                image_path=saved_img_path_str,
                provider=provider,
            )
        )
        db.session.commit()

        # 조기 개입 알림 감지 (채팅 흐름에 영향 없도록 예외 무시)
        try:
            from services.alert_service import check_and_create_alerts
            check_and_create_alerts(current_user.id, session_id, role_key, user_message)
        except Exception:
            pass

        # AI 응답을 DB에 저장 (스트리밍 완료 후 저장을 위해, 이 블록은 스트리밍 제너레이터 내에서 처리하거나 프론트/비동기로 위임해야 합니다)
        # HTTP 스트리밍(SSE) 응답 생성
        def generate_sse():
            yield f"data: {json.dumps({'message': '연결됨', 'session_id': session_id, 'provider': provider})}\n\n"
            
            full_content = ""
            try:
                for chunk in generate_ai_response_stream(
                    model_id=selected_model_id,
                    system_prompt=system_prompt,
                    messages=final_messages,
                    max_tokens=selected_max_tokens,
                    upload_folder=current_app.config["UPLOAD_FOLDER"],
                ):
                    full_content += chunk
                    # JSON 포맷으로 이스케이프해서 클라이언트로 전송
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                # 전송이 모두 끝나면 마무리 데이터 알림
                yield f"data: {json.dumps({'done': True})}\n\n"
                
                # 완성된 메시지 DB에 비동기적으로 저장 (Flask app context 이용)
                try:
                    from app import app
                    with app.app_context():
                        db.session.add(
                            Message(
                                session_id=session_id,
                                user_id=current_user.id,
                                is_user=False,
                                content=full_content,
                                provider=provider,
                            )
                        )
                        db.session.commit()
                except Exception as save_err:
                    print(f"SSE 완료 후 DB 저장 오류: {save_err}")
                    
            except Exception as stream_err:
                print(f"SSE 스트리밍 오류: {stream_err}")
                yield f"data: {json.dumps({'error': str(stream_err)})}\n\n"

        return Response(stream_with_context(generate_sse()), mimetype='text/event-stream')

    except Exception as e:
        # 처리 실패 시 롤백 및 오류 응답
        print(f"Chat Error ({provider}): {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": f"AI 응답 오류 ({provider}): {str(e)}"}), 500


@chat_bp.route("/api/image_task_status/<task_id>")
@login_required
def image_task_status(task_id):
    """이미지 생성 Celery 태스크 상태 조회 (프론트 폴링용)"""
    from tasks import generate_image_async
    task = generate_image_async.AsyncResult(task_id)

    if task.state == "PENDING" or task.state == "STARTED":
        return jsonify({"status": "pending"})
    elif task.state == "SUCCESS":
        result = task.result or {}
        if result.get("success"):
            return jsonify({"status": "done", "image_html": result["image_html"], "session_id": result["session_id"]})
        else:
            return jsonify({"status": "error", "error": result.get("error", "알 수 없는 오류")})
    elif task.state == "FAILURE":
        return jsonify({"status": "error", "error": str(task.result)})
    else:
        return jsonify({"status": task.state.lower()})


@chat_bp.route("/api/get_chat_history")
@login_required
def get_chat_history():
    """선택된 페르소나의 최근 대화 목록 조회.

    - 권한: 로그인 사용자
    - 입력: query param role=페르소나 키
    - 응답: 세션 id/title/username 리스트 (최대 50개)
    """
    hist = (
        db.session.query(ChatSession.id, ChatSession.title, User.username)
        .join(User)
        .filter(ChatSession.role_key == request.args.get("role"))
        .order_by(ChatSession.timestamp.desc())
        .limit(50)
        .all()
    )
    return jsonify([{"id": h.id, "title": h.title, "username": h.username} for h in hist])


@chat_bp.route("/api/get_session/<int:session_id>")
@login_required
def get_session(session_id):
    """특정 세션의 메시지 목록 조회.

    - 권한: 로그인 사용자
    - 입력: session_id (path param)
    - 응답: 메시지 목록 + 소유자 이름
    """
    session_info = db.session.get(ChatSession, session_id)
    if not session_info:
        return jsonify({"error": "Session not found"}), 404
    owner = db.session.get(User, session_info.user_id)
    owner_username = owner.username if owner else "Unknown"

    # 메시지와 작성자명을 조인해서 가져온다 (AI 메시지는 User가 없으므로 outerjoin 사용)
    msgs = (
        db.session.query(Message, User.username)
        .outerjoin(User, Message.user_id == User.id)
        .filter(Message.session_id == session_id)
        .order_by(Message.timestamp.asc())
        .all()
    )

    message_list = []
    for m in msgs:
        img_urls = []
        if m.Message.image_path:
            for path in m.Message.image_path.split(","):
                path = path.strip()
                if path:
                    img_urls.append(url_for("static", filename=path))

        # 프론트에서 바로 렌더링 가능한 형태로 변환
        message_list.append(
            {
                "text": m.Message.content,
                "image_paths": img_urls,
                "sender": "user" if m.Message.is_user else "ai",
                "username": m.username if m.Message.is_user else "AI",
            }
        )

    return jsonify({"owner_username": owner_username, "messages": message_list})


@chat_bp.route("/api/rename_session/<int:session_id>", methods=["POST"])
@login_required
def rename_session(session_id):
    """세션 제목 변경.

    - 권한: 세션 소유자 또는 관리자
    - 입력: new_title (JSON)
    """
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403
    s.title = request.json.get("new_title")
    db.session.commit()
    return jsonify({"success": True})


@chat_bp.route("/api/delete_session/<int:session_id>", methods=["POST"])
@login_required
def delete_session(session_id):
    """세션 삭제(연관 파일/메시지 포함).

    - 권한: 세션 소유자 또는 관리자
    - 동작: 파일 삭제 → 메시지 삭제 → 세션 삭제
    """
    s = db.session.get(ChatSession, session_id)
    if not s or (s.user_id != current_user.id and not current_user.is_admin):
        return jsonify({"error": "Fail"}), 403

    try:
        # 세션에 연결된 파일 제거
        files = ChatFile.query.filter_by(session_id=session_id).all()
        for f in files:
            try:
                if f.file_type.startswith("image/"):
                    # 이미지 파일은 uploads 루트 경로
                    path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"], os.path.basename(f.storage_path)
                    )
                else:
                    # 일반 파일은 uploads/files 하위 경로
                    path = os.path.join(
                        current_app.config["UPLOAD_FOLDER"],
                        "files",
                        os.path.basename(f.storage_path),
                    )

                # 파일이 없으면 static 폴더 경로도 확인 (safe_join으로 경로 조작 방지)
                if not os.path.exists(path):
                    from werkzeug.security import safe_join
                    path = safe_join(current_app.static_folder, f.storage_path)

                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"File removal error: {e}")

            # 파일 레코드 삭제
            db.session.delete(f)

        # 메시지/세션 레코드 삭제
        Message.query.filter_by(session_id=session_id).delete()
        db.session.delete(s)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        # 오류 발생 시 롤백
        db.session.rollback()
        print(f"Error deleting session {session_id}: {e}")
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500


@chat_bp.route("/api/personas/available", methods=["GET"])
@login_required
def get_available_personas():
    """
    현재 사용자가 선택 가능한 페르소나 목록 반환

    - 관리자: 모든 활성 페르소나
    - 교사: allow_teacher=True인 페르소나
    - 학생: allow_user=True인 페르소나
    """
    try:
        user = current_user

        # 캐시에서 활성화된 페르소나 조회 후 Python에서 필터링
        _all = get_active_personas_cached()

        # 권한에 따라 필터링
        if user.is_admin or user.role == 'admin':
            personas = _all
        elif user.role == 'teacher':
            personas = [p for p in _all if p.allow_teacher]
        else:
            personas = [p for p in _all if p.allow_user]

        # 응답 형식
        persona_list = [
            {
                "role_key": p.role_key,
                "role_name": p.role_name,
                "icon": p.icon or "🤖",
                "description": p.description or "",
                "use_rag": p.use_rag
            }
            for p in personas
        ]

        return jsonify({"success": True, "personas": persona_list})

    except Exception as e:
        print(f"Error getting available personas: {e}")
        return jsonify({"error": f"서버 오류: {str(e)}"}), 500
