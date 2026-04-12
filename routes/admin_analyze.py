"""
학습 분석 라우트 모듈.

교사/관리자가 클래스(페르소나) 또는 개별 학생의 대화 이력을 AI로 분석하여
학생들의 흥미 영역과 어려움을 파악할 수 있도록 지원한다.

Routes:
    GET  /admin/analyze                       - 분석 페이지 렌더링
    GET  /api/admin/analyze/models            - 분석에 사용 가능한 모델 목록
    GET  /api/admin/analyze/personas          - 접근 가능한 페르소나 목록
    GET  /api/admin/analyze/students          - 전체 접근 가능 학생 목록
    GET  /api/admin/analyze/students/<id>     - 특정 페르소나의 학생 목록
    POST /api/admin/analyze/class             - 클래스 분석 (SSE 스트리밍)
    POST /api/admin/analyze/student           - 학생 분석 (SSE 스트리밍)
    GET  /api/admin/analyze/alerts            - 조기 개입 알림 목록
    GET  /api/admin/analyze/alerts/unread-count - 미확인 알림 수
    POST /api/admin/analyze/alerts/<id>/read  - 알림 읽음 처리
    POST /api/admin/analyze/alerts/read-all   - 전체 읽음 처리
"""

import datetime
import json
from collections import defaultdict

from flask import (Blueprint, Response, jsonify, redirect,
                   render_template, request, stream_with_context, url_for)
from flask_login import current_user, login_required

from extensions import db
from models import (ChatSession, LearningAlert, Message, PersonaDefinition,
                    PersonaStudentPermission, PersonaTeacherPermission,
                    SystemConfig, User)
from services.ai_service import generate_ai_response_stream

admin_analyze_bp = Blueprint("admin_analyze", __name__)

# 분석 출력 토큰 상한 (공급사 공통)
ANALYSIS_MAX_TOKENS = 16000

# 공급사별 표시 이름
PROVIDER_LABELS = {
    "anthropic": "Anthropic (Claude)",
    "openai":    "OpenAI (GPT)",
    "google":    "Google (Gemini)",
    "xai":       "xAI (Grok)",
}

# 과도한 토큰 소비 방지를 위한 메시지 수 상한
MAX_MESSAGES_CLASS = 1500   # 클래스 분석: 전체 학생 메시지 합산
MAX_MESSAGES_STUDENT = 500  # 학생 분석: 개별 학생 메시지
# 메시지 한 건당 내용 최대 길이 (chars)
MAX_CONTENT_LEN = 400


# ---------------------------------------------------------------------------
# 권한 헬퍼
# ---------------------------------------------------------------------------

def _can_access_analytics() -> bool:
    """현재 사용자가 분석 기능에 접근할 수 있는지 확인."""
    if current_user.is_admin:
        return True
    if current_user.role == "teacher":
        return (PersonaTeacherPermission.query
                .filter_by(teacher_id=current_user.id, can_view_analytics=True)
                .first() is not None)
    return False


def _can_access_persona(persona_id: int) -> bool:
    """현재 사용자가 특정 페르소나의 분석 권한을 갖는지 확인."""
    if current_user.is_admin:
        return True
    return (PersonaTeacherPermission.query
            .filter_by(persona_id=persona_id,
                       teacher_id=current_user.id,
                       can_view_analytics=True)
            .first() is not None)


def _get_accessible_personas():
    """현재 사용자가 접근 가능한 활성 페르소나 목록 반환."""
    if current_user.is_admin:
        return (PersonaDefinition.query
                .filter_by(is_active=True)
                .order_by(PersonaDefinition.sort_order)
                .all())
    perms = (PersonaTeacherPermission.query
             .filter_by(teacher_id=current_user.id, can_view_analytics=True)
             .all())
    persona_ids = [p.persona_id for p in perms]
    return (PersonaDefinition.query
            .filter(PersonaDefinition.id.in_(persona_ids),
                    PersonaDefinition.is_active == True)
            .order_by(PersonaDefinition.sort_order)
            .all())


# ---------------------------------------------------------------------------
# 분석 가능 모델 목록 API
# ---------------------------------------------------------------------------

@admin_analyze_bp.route("/api/admin/analyze/models")
@login_required
def get_analysis_models():
    """활성화된 공급사+모델 목록을 반환한다 (분석 모델 선택용)."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    providers = ["anthropic", "openai", "google", "xai"]
    result = []

    for provider in providers:
        # 공급사 활성화 여부 확인
        status_conf = SystemConfig.query.filter_by(
            key=f"provider_status_{provider}").first()
        if status_conf and status_conf.value == "restricted":
            continue

        # 해당 공급사의 활성화된 모델 목록
        model_conf = SystemConfig.query.filter_by(
            key=f"enabled_models_{provider}").first()
        try:
            models = json.loads(model_conf.value) if model_conf else []
        except (json.JSONDecodeError, AttributeError):
            models = []

        label_prefix = PROVIDER_LABELS.get(provider, provider)
        for model_id in models:
            result.append({
                "model_id":  model_id,
                "provider":  provider,
                "label":     f"{model_id}  [{label_prefix}]",
            })

    return jsonify(result)


# ---------------------------------------------------------------------------
# 페이지 & 목록 API
# ---------------------------------------------------------------------------

@admin_analyze_bp.route("/admin/analyze")
@login_required
def analyze_page():
    """학습 분석 페이지 렌더링."""
    if not _can_access_analytics():
        return redirect(url_for("chat.index"))
    return render_template(
        "admin_analyze.html",
        is_admin=current_user.is_admin,
        current_user_role=getattr(current_user, "role", "user"),
        is_teacher_manager=(
            not current_user.is_admin and current_user.role == "teacher"
        ),
        initial_personas=[],
    )


@admin_analyze_bp.route("/api/admin/analyze/personas")
@login_required
def get_personas():
    """접근 가능한 페르소나 목록 반환."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403
    personas = _get_accessible_personas()
    return jsonify([
        {"id": p.id, "role_key": p.role_key,
         "role_name": p.role_name, "icon": p.icon}
        for p in personas
    ])


@admin_analyze_bp.route("/api/admin/analyze/students")
@login_required
def get_all_students():
    """접근 가능한 전체 학생 목록 반환 (페르소나 필터 없음)."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    if current_user.is_admin:
        students = (User.query
                    .filter(User.is_admin == False)  # noqa: E712
                    .order_by(User.username)
                    .all())
    else:
        personas = _get_accessible_personas()
        all_student_ids: set = set()
        for persona in personas:
            perms = (PersonaStudentPermission.query
                     .filter_by(persona_id=persona.id).all())
            if perms:
                all_student_ids.update(p.student_id for p in perms)
            else:
                sessions = (ChatSession.query
                            .filter_by(role_key=persona.role_key).all())
                all_student_ids.update(s.user_id for s in sessions)
        students = (User.query
                    .filter(User.id.in_(all_student_ids))
                    .order_by(User.username)
                    .all())

    return jsonify([
        {"id": s.id, "display_name": s.display_name}
        for s in students
    ])


@admin_analyze_bp.route("/api/admin/analyze/students/<int:persona_id>")
@login_required
def get_students_for_persona(persona_id: int):
    """특정 페르소나에 배정된 학생 목록 반환."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403
    if not _can_access_persona(persona_id):
        return jsonify({"error": "Denied"}), 403

    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "Persona not found"}), 404

    perms = PersonaStudentPermission.query.filter_by(persona_id=persona_id).all()
    if perms:
        student_ids = [p.student_id for p in perms]
        students = (User.query
                    .filter(User.id.in_(student_ids))
                    .order_by(User.username)
                    .all())
    else:
        # 명시 배정 없으면 실제 대화 이력으로 추론
        subq = (db.session.query(ChatSession.user_id)
                .filter_by(role_key=persona.role_key)
                .distinct()
                .subquery())
        students = (User.query
                    .filter(User.id.in_(subq))
                    .order_by(User.username)
                    .all())

    return jsonify([
        {"id": s.id, "display_name": s.display_name}
        for s in students
    ])


# ---------------------------------------------------------------------------
# 대화 포맷 헬퍼
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int = MAX_CONTENT_LEN) -> str:
    if not text:
        return ""
    text = text.strip()
    return text[:max_len] + "..." if len(text) > max_len else text


def _format_class_conversations(persona: PersonaDefinition):
    """클래스 분석용 대화 텍스트 생성.

    Returns:
        (formatted_text, total_message_count)
    """
    sessions = (ChatSession.query
                .filter_by(role_key=persona.role_key)
                .order_by(ChatSession.user_id, ChatSession.timestamp)
                .all())
    if not sessions:
        return None, 0

    sessions_by_user: dict = defaultdict(list)
    for s in sessions:
        sessions_by_user[s.user_id].append(s)

    user_ids = list(sessions_by_user.keys())
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()}

    parts = []
    total = 0

    for user_id, user_sessions in sessions_by_user.items():
        user = users.get(user_id)
        if not user:
            continue

        user_parts = [f"\n{'=' * 40}\n학생: {user.display_name}\n{'=' * 40}"]

        for session in user_sessions:
            messages = (Message.query
                        .filter_by(session_id=session.id)
                        .order_by(Message.timestamp)
                        .all())
            if not messages:
                continue

            session_lines = [f"\n[대화: {session.title}]"]
            for msg in messages:
                content = _truncate(msg.content or "")
                if not content:
                    continue
                prefix = "학생" if msg.is_user else "AI"
                session_lines.append(f"{prefix}: {content}")
                total += 1
                if total >= MAX_MESSAGES_CLASS:
                    break

            if len(session_lines) > 1:
                user_parts.extend(session_lines)

            if total >= MAX_MESSAGES_CLASS:
                break

        if len(user_parts) > 1:
            parts.append("\n".join(user_parts))

        if total >= MAX_MESSAGES_CLASS:
            break

    return "\n".join(parts) if parts else None, total


def _format_student_conversations(user: User, persona: PersonaDefinition | None):
    """학생 분석용 대화 텍스트 생성.

    Returns:
        (formatted_text, total_message_count)
    """
    query = ChatSession.query.filter_by(user_id=user.id)
    if persona:
        query = query.filter_by(role_key=persona.role_key)
    sessions = query.order_by(ChatSession.timestamp).all()

    if not sessions:
        return None, 0

    parts = []
    total = 0

    for session in sessions:
        messages = (Message.query
                    .filter_by(session_id=session.id)
                    .order_by(Message.timestamp)
                    .all())
        if not messages:
            continue

        session_lines = [f"\n[{session.title}]"]
        for msg in messages:
            content = _truncate(msg.content or "", MAX_CONTENT_LEN + 100)
            if not content:
                continue
            prefix = "학생" if msg.is_user else "AI"
            session_lines.append(f"{prefix}: {content}")
            total += 1
            if total >= MAX_MESSAGES_STUDENT:
                break

        if len(session_lines) > 1:
            parts.append("\n".join(session_lines))

        if total >= MAX_MESSAGES_STUDENT:
            break

    return "\n".join(parts) if parts else None, total


# ---------------------------------------------------------------------------
# SSE 이벤트 헬퍼
# ---------------------------------------------------------------------------

def _sse(event_type: str, text: str) -> str:
    return f"data: {json.dumps({'type': event_type, 'text': text}, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# 분석 API (SSE 스트리밍)
# ---------------------------------------------------------------------------

def _analysis_chunks(prompt: str, model_id: str):
    """공통 분석 청크 생성기 — 선택된 모델로 프롬프트를 실행하고 SSE 이벤트 문자열을 yield한다.

    Response 객체가 아닌 generator를 반환하므로 외부 generator에서 yield from으로 안전하게 사용할 수 있다.
    """
    try:
        for chunk in generate_ai_response_stream(
            model_id=model_id,
            system_prompt="당신은 교육 데이터 분석 전문가입니다.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=ANALYSIS_MAX_TOKENS,
            upload_folder="",   # 분석에는 이미지 없음
        ):
            # ai_service는 오류 문자열도 yield하므로 그대로 전달
            yield _sse("chunk", chunk)
        yield _sse("done", "")
    except Exception as e:
        yield _sse("error", str(e))


@admin_analyze_bp.route("/api/admin/analyze/class", methods=["POST"])
@login_required
def analyze_class():
    """클래스(페르소나) 전체 대화를 분석하여 SSE로 스트리밍 반환."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    data = request.get_json() or {}
    persona_id = data.get("persona_id")
    model_id   = data.get("model_id", "claude-sonnet-4-6")

    if not persona_id:
        return jsonify({"error": "persona_id required"}), 400
    if not _can_access_persona(int(persona_id)):
        return jsonify({"error": "Denied"}), 403

    persona = db.session.get(PersonaDefinition, int(persona_id))
    if not persona:
        return jsonify({"error": "Persona not found"}), 404

    def generate():
        try:
            yield _sse("status", "대화 데이터를 수집하는 중...")

            conv_text, total = _format_class_conversations(persona)

            if not conv_text or total == 0:
                yield _sse("error", "이 페르소나와 나눈 대화가 없습니다.")
                return

            note = f" (최대 {MAX_MESSAGES_CLASS}건 기준)" if total >= MAX_MESSAGES_CLASS else ""
            yield _sse("status", f"총 {total}개 메시지를 분석하는 중...{note}")

            prompt = f"""아래는 '{persona.role_name}' AI와 나눈 학생들의 실제 대화 기록입니다.

이 대화들을 분석하여 다음 항목을 교사에게 보고해주세요:

## 1. 학생들이 흥미를 보인 주제와 개념
자주 등장하는 호기심 있는 질문, 심화 탐구 패턴, 자발적 연관 질문 등을 구체적인 예시와 함께 서술해 주세요.

## 2. 학생들이 어려워하는 주제와 개념
반복 질문, 재설명 요청, 오개념이 보이는 패턴 등을 구체적인 예시와 함께 서술해 주세요.

## 3. 교사에게 드리는 제언
위 분석을 바탕으로 보완이 필요한 수업 내용과 학생들의 관심을 활용할 수 있는 수업 방향을 제안해 주세요.

---

[대화 기록]
{conv_text}
"""

            yield from _analysis_chunks(prompt, model_id)

        except Exception as e:
            yield _sse("error", str(e))

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@admin_analyze_bp.route("/api/admin/analyze/student", methods=["POST"])
@login_required
def analyze_student():
    """특정 학생의 대화를 분석하여 SSE로 스트리밍 반환."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    data = request.get_json() or {}
    student_id = data.get("student_id")
    persona_id = data.get("persona_id")   # optional
    model_id   = data.get("model_id", "claude-sonnet-4-6")

    if not student_id:
        return jsonify({"error": "student_id required"}), 400

    student = db.session.get(User, int(student_id))
    if not student:
        return jsonify({"error": "Student not found"}), 404

    persona = None
    if persona_id:
        if not _can_access_persona(int(persona_id)):
            return jsonify({"error": "Denied"}), 403
        persona = db.session.get(PersonaDefinition, int(persona_id))

    def generate():
        try:
            yield _sse("status", "대화 데이터를 수집하는 중...")

            conv_text, total = _format_student_conversations(student, persona)

            if not conv_text or total == 0:
                yield _sse("error", "이 학생의 대화 기록이 없습니다.")
                return

            scope = f"'{persona.role_name}' 한정" if persona else "전체 페르소나"
            note = f" (최대 {MAX_MESSAGES_STUDENT}건 기준)" if total >= MAX_MESSAGES_STUDENT else ""
            yield _sse("status", f"총 {total}개 메시지를 분석하는 중... [{scope}]{note}")

            prompt = f"""아래는 '{student.display_name}' 학생이 AI와 나눈 실제 대화 기록입니다.

이 대화들을 분석하여 다음 항목을 교사에게 보고해주세요:

## 1. 이 학생이 흥미를 보인 주제와 개념
자주 등장하는 호기심 있는 질문, 심화 탐구 패턴 등을 구체적인 예시와 함께 서술해 주세요.

## 2. 이 학생이 어려워하는 주제와 개념
반복 질문, 재설명 요청, 오개념이 보이는 패턴 등을 구체적인 예시와 함께 서술해 주세요.

## 3. 이 학생의 학습 특성
질문 방식(구체적/추상적, 이론/실습 지향 등), 이해 속도, 대화 패턴 등을 서술해 주세요.

## 4. 교사에게 드리는 제언
이 학생을 위한 맞춤 지도 방향을 제안해 주세요.

---

[대화 기록]
{conv_text}
"""

            yield from _analysis_chunks(prompt, model_id)

        except Exception as e:
            yield _sse("error", str(e))

    return Response(
        stream_with_context(generate()),
        content_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# 조기 개입 알림 API
# ---------------------------------------------------------------------------

def _accessible_role_keys() -> list[str] | None:
    """현재 사용자가 접근 가능한 role_key 목록 반환. 관리자는 None(전체)."""
    if current_user.is_admin:
        return None
    personas = _get_accessible_personas()
    return [p.role_key for p in personas]


@admin_analyze_bp.route("/api/admin/analyze/alerts")
@login_required
def get_alerts():
    """조기 개입 알림 목록 반환 (최신순, 최대 200건)."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    only_unread = request.args.get("unread_only", "false").lower() == "true"
    role_keys = _accessible_role_keys()

    query = LearningAlert.query
    if only_unread:
        query = query.filter_by(is_read=False)
    if role_keys is not None:
        query = query.filter(LearningAlert.role_key.in_(role_keys))

    alerts = query.order_by(LearningAlert.created_at.desc()).limit(200).all()

    # 학생명 / 페르소나명 / 세션 제목 일괄 조회
    student_ids = list({a.student_id for a in alerts})
    session_ids  = list({a.session_id  for a in alerts})
    role_key_set = list({a.role_key    for a in alerts})

    students = {u.id: u.display_name for u in
                User.query.filter(User.id.in_(student_ids)).all()}
    personas = {p.role_key: f"{p.icon} {p.role_name}" for p in
                PersonaDefinition.query.filter(
                    PersonaDefinition.role_key.in_(role_key_set)).all()}
    sessions = {s.id: s.title for s in
                ChatSession.query.filter(ChatSession.id.in_(session_ids)).all()}

    result = []
    for a in alerts:
        result.append({
            "id":            a.id,
            "student_name":  students.get(a.student_id, f"학생#{a.student_id}"),
            "persona_name":  personas.get(a.role_key, a.role_key),
            "session_title": sessions.get(a.session_id, ""),
            "alert_type":    a.alert_type,
            "detail":        a.detail,
            "trigger_content": a.trigger_content,
            "created_at":    a.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_read":       a.is_read,
        })

    return jsonify(result)


@admin_analyze_bp.route("/api/admin/analyze/alerts/unread-count")
@login_required
def get_unread_count():
    """미확인 알림 수 반환."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    role_keys = _accessible_role_keys()
    query = LearningAlert.query.filter_by(is_read=False)
    if role_keys is not None:
        query = query.filter(LearningAlert.role_key.in_(role_keys))

    return jsonify({"count": query.count()})


@admin_analyze_bp.route("/api/admin/analyze/alerts/<int:alert_id>/read", methods=["POST"])
@login_required
def mark_alert_read(alert_id: int):
    """특정 알림을 읽음 처리."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    alert = db.session.get(LearningAlert, alert_id)
    if not alert:
        return jsonify({"error": "Not found"}), 404

    role_keys = _accessible_role_keys()
    if role_keys is not None and alert.role_key not in role_keys:
        return jsonify({"error": "Denied"}), 403

    alert.is_read = True
    db.session.commit()
    return jsonify({"success": True})


@admin_analyze_bp.route("/api/admin/analyze/alerts/read-all", methods=["POST"])
@login_required
def mark_all_alerts_read():
    """접근 가능한 전체 미확인 알림을 읽음 처리."""
    if not _can_access_analytics():
        return jsonify({"error": "Denied"}), 403

    role_keys = _accessible_role_keys()
    query = LearningAlert.query.filter_by(is_read=False)
    if role_keys is not None:
        query = query.filter(LearningAlert.role_key.in_(role_keys))

    query.update({"is_read": True}, synchronize_session=False)
    db.session.commit()
    return jsonify({"success": True})
