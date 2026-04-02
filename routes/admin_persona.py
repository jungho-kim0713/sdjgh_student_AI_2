"""
관리자 페르소나 관리 API

관리자가 웹 UI에서 페르소나를 동적으로 생성/수정/삭제하고,
교사에게 페르소나 관리 권한을 부여할 수 있습니다.
"""

from flask import Blueprint, jsonify, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import (
    PersonaDefinition,
    PersonaSystemPrompt,
    PersonaTeacherPermission,
    PersonaStudentPermission,
    PersonaPromptSnapshot,
    PersonaKnowledgeBase,
    KnowledgeDocument,
    DocumentChunk,
    User,
    SystemConfig
)
from services.ai_service import AVAILABLE_MODELS
from services.rag_service import get_rag_statistics
from prompts import AI_PERSONAS
from tasks import process_document_async
import datetime
import os
import json
from werkzeug.utils import secure_filename

admin_persona_bp = Blueprint("admin_persona", __name__)


def get_enabled_models_merged():
    """DB에서 활성화된 모델과 메타데이터를 병합하여 반환합니다."""
    enabled_models_merged = {}
    for provider in ["openai", "anthropic", "google", "xai"]:
        enabled_key = f"enabled_models_{provider}"
        enabled_conf = SystemConfig.query.filter_by(key=enabled_key).first()
        enabled_models = []
        if enabled_conf:
            try:
                enabled_models = json.loads(enabled_conf.value)
            except:
                pass
        
        metadata_key = f"available_models_metadata_{provider}"
        metadata_conf = SystemConfig.query.filter_by(key=metadata_key).first()
        metadata_dict = {}
        if metadata_conf:
            try:
                available = json.loads(metadata_conf.value)
                for item in available:
                    metadata_dict[item["id"]] = item
            except:
                pass
                
        for m_id in enabled_models:
            if m_id in metadata_dict:
                info = metadata_dict[m_id]
                info["provider"] = provider
                enabled_models_merged[m_id] = info
            elif m_id in AVAILABLE_MODELS:
                info = AVAILABLE_MODELS[m_id].copy()
                info["id"] = m_id
                enabled_models_merged[m_id] = info
            else:
                enabled_models_merged[m_id] = {
                    "id": m_id,
                    "name": m_id,
                    "provider": provider,
                    "input_price": 0,
                    "output_price": 0,
                    "description": "새로운 활성화 모델"
                }
                
    if not enabled_models_merged:
        return AVAILABLE_MODELS
        
    return enabled_models_merged



# =============================================================================
# 권한 체크 헬퍼 함수
# =============================================================================

def get_manageable_persona_ids(user):
    """
    사용자가 관리할 수 있는 페르소나 ID 리스트 반환

    - 관리자: 모든 페르소나
    - 교사: 관리 권한이 부여된 페르소나만
    - 학생: 빈 리스트
    """
    if user.is_admin or user.role == 'admin' or user.username in ['admin', '관리자']:
        return None  # None = 전체 접근

    if user.role == 'teacher':
        permissions = PersonaTeacherPermission.query.filter_by(
            teacher_id=user.id
        ).all()
        return [p.persona_id for p in permissions]

    return []  # 학생은 관리 권한 없음


def can_manage_persona(user, persona_id):
    """
    특정 페르소나 관리 권한 체크

    Args:
        user: 현재 사용자
        persona_id: 페르소나 ID

    Returns:
        bool: 관리 권한 여부
    """
    if user.is_admin or getattr(user, 'role', '') == 'admin' or getattr(user, 'username', '') in ['admin', '관리자']:
        return True

    if user.role == 'teacher':
        permission = PersonaTeacherPermission.query.filter_by(
            persona_id=persona_id,
            teacher_id=user.id
        ).first()
        return permission is not None

    return False


def has_persona_permission(user, persona_id, permission_type='can_edit_prompt'):
    """
    특정 페르소나의 세부 권한 체크

    Args:
        user: 현재 사용자
        persona_id: 페르소나 ID
        permission_type: 'can_edit_prompt' | 'can_manage_knowledge' | 'can_view_analytics'

    Returns:
        bool: 권한 여부
    """
    if user.is_admin or getattr(user, 'role', '') == 'admin' or getattr(user, 'username', '') in ['admin', '관리자']:
        return True

    if user.role == 'teacher':
        permission = PersonaTeacherPermission.query.filter_by(
            persona_id=persona_id,
            teacher_id=user.id
        ).first()

        if permission:
            return getattr(permission, permission_type, False)

    return False


def is_persona_manager(user):
    """
    사용자가 페르소나 관리자인지 확인 (관리자 또는 관리 교사)

    Returns:
        bool: 페르소나 관리 권한 여부
    """
    if user.is_admin or getattr(user, 'role', '') == 'admin' or getattr(user, 'username', '') in ['admin', '관리자']:
        return True

    if user.role == 'teacher':
        return True

    return False


# =============================================================================
# 데코레이터
# =============================================================================

def admin_required(f):
    """관리자 권한 확인 데코레이터"""
    @login_required
    def decorated_function(*args, **kwargs):
        if not (current_user.is_admin or getattr(current_user, 'role', '') == 'admin' or getattr(current_user, 'username', '') in ['admin', '관리자']):
            return jsonify({"error": "관리자 권한이 필요합니다."}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@admin_persona_bp.route("/admin/persona", methods=["GET"])
@login_required
def persona_management():
    """
    페르소나 관리 페이지 렌더링

    - 관리자: 모든 페르소나 관리 가능
    - 관리 교사: 권한이 부여된 페르소나만 관리 가능
    """
    print(f"[DEBUG] 페르소나 관리 화면 접근: user_id={current_user.id}, username={current_user.username}, role={current_user.role}")

    is_manager = is_persona_manager(current_user)
    print(f"[DEBUG] is_persona_manager 결과: {is_manager}")

    if not is_manager:
        print(f"[DEBUG] 권한 없음 - 리다이렉트")
        flash("페르소나 관리 권한이 필요합니다.", "error")
        return redirect(url_for("chat.index"))

    print(f"[DEBUG] 권한 확인 완료 - 페르소나 관리 화면 렌더링")
    # 교사용 페르소나 관리 화면 (관리자와 동일한 UI 사용)
    # 관리자는 role이 'teacher'여도 교사 제한을 받지 않아야 함
    is_teacher_restricted = (current_user.role == 'teacher' and not current_user.is_admin)
    return render_template("admin_persona.html", is_teacher=is_teacher_restricted)


@admin_persona_bp.route("/api/admin/persona/list", methods=["GET"])
@login_required
def get_persona_list():
    """
    페르소나 목록 조회 (권한 기반 필터링)

    - 관리자: 모든 페르소나
    - 관리 교사: 권한이 부여된 페르소나만

    Returns:
        {
            "personas": [
                {
                    "id": 1,
                    "role_key": "math_tutor",
                    "role_name": "수학 튜터",
                    "description": "...",
                    "icon": "🧮",
                    "is_system": false,
                    "is_active": true,
                    "use_rag": false,
                    "created_at": "2026-02-08 10:00:00"
                },
                ...
            ],
            "available_models": {...}
        }
    """
    # 권한 체크
    print(f"[DEBUG] get_persona_list 요청: user={current_user.username}, is_admin={current_user.is_admin}, role={current_user.role}")
    if not is_persona_manager(current_user):
        print(f"[DEBUG] 권한 부족")
        return jsonify({"error": "페르소나 관리 권한이 필요합니다."}), 403

    # 관리 가능한 페르소나 ID 조회
    manageable_ids = get_manageable_persona_ids(current_user)
    print(f"[DEBUG] manageable_ids: {manageable_ids}")

    # 쿼리 구성 (관리자는 전체, 교사는 필터링)
    query = PersonaDefinition.query.order_by(PersonaDefinition.id.asc())
    if manageable_ids is not None:  # None = 관리자(전체 접근)
        query = query.filter(PersonaDefinition.id.in_(manageable_ids))

    personas = query.all()
    print(f"[DEBUG] 조회된 페르소나 개수: {len(personas)}")

    persona_list = []
    for p in personas:
        # 교사 수 계산
        teacher_count = PersonaTeacherPermission.query.filter_by(
            persona_id=p.id
        ).count()

        # 지식 베이스 통계
        kb_count = PersonaKnowledgeBase.query.filter_by(
            persona_id=p.id,
            is_active=True
        ).count()

        # 학생 배정 수
        student_count = PersonaStudentPermission.query.filter_by(
            persona_id=p.id
        ).count()

        persona_list.append({
            "id": p.id,
            "role_key": p.role_key,
            "role_name": p.role_name,
            "description": p.description,
            "icon": p.icon,
            "is_system": p.is_system,
            "is_active": p.is_active,
            "use_rag": p.use_rag,
            "retrieval_strategy": p.retrieval_strategy,
            "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "teacher_count": teacher_count,
            "knowledge_base_count": kb_count,
            "student_count": student_count
        })

    return jsonify({
        "personas": persona_list,
        "available_models": get_enabled_models_merged()
    })


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>", methods=["GET"])
@login_required
def get_persona_detail(persona_id):
    """
    페르소나 상세 정보 조회 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Returns:
        전체 페르소나 설정 정보
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    # 권한 체크: 관리자 또는 해당 페르소나의 관리 교사
    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "해당 페르소나에 대한 접근 권한이 없습니다."}), 403

    # 권한 있는 교사 목록
    permissions = PersonaTeacherPermission.query.filter_by(
        persona_id=persona_id
    ).all()

    teachers = []
    for perm in permissions:
        teacher = db.session.get(User, perm.teacher_id)
        if teacher:
            teachers.append({
                "id": teacher.id,
                "username": teacher.username,
                "email": teacher.email,
                "can_edit_prompt": perm.can_edit_prompt,
                "can_manage_knowledge": perm.can_manage_knowledge,
                "can_view_analytics": perm.can_view_analytics,
                "granted_at": perm.granted_at.strftime("%Y-%m-%d %H:%M:%S")
            })

    # 지식 베이스 청크 설정 (첫 번째 지식 베이스 또는 기본값)
    kb = PersonaKnowledgeBase.query.filter_by(
        persona_id=persona_id,
        is_active=True
    ).first()

    chunk_strategy = kb.chunk_strategy if kb else 'paragraph'
    chunk_size = kb.chunk_size if kb else 500
    chunk_overlap = kb.chunk_overlap if kb else 100

    return jsonify({
        "id": persona.id,
        "role_key": persona.role_key,
        "role_name": persona.role_name,
        "description": persona.description,
        "icon": persona.icon,
        "is_system": persona.is_system,
        "is_active": persona.is_active,
        # AI 모델 설정
        "model_openai": persona.model_openai,
        "model_anthropic": persona.model_anthropic,
        "model_google": persona.model_google,
        "model_xai": persona.model_xai,
        "max_tokens": persona.max_tokens,
        # 권한 설정
        "allow_user": persona.allow_user,
        "allow_teacher": persona.allow_teacher,
        "restrict_google": persona.restrict_google,
        "restrict_anthropic": persona.restrict_anthropic,
        "restrict_openai": persona.restrict_openai,
        "restrict_xai": persona.restrict_xai,
        # RAG 설정
        "use_rag": persona.use_rag,
        "retrieval_strategy": persona.retrieval_strategy,
        "rag_top_k": persona.rag_top_k,
        "rag_max_k": persona.rag_max_k,
        "rag_similarity_threshold": persona.rag_similarity_threshold,
        "rag_gap_threshold": persona.rag_gap_threshold,
        # 청크 설정
        "chunk_strategy": chunk_strategy,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        # 메타데이터
        "created_at": persona.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "updated_at": persona.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        "teachers": teachers
    })


@admin_persona_bp.route("/api/admin/persona/create", methods=["POST"])
@admin_required
def create_persona():
    """
    새 페르소나 생성

    Request Body:
        {
            "role_key": "prob_stats_tutor",
            "role_name": "확률과 통계 튜터",
            "description": "확률과 통계 과목 전문 튜터",
            "icon": "📊",
            "use_rag": true,
            "retrieval_strategy": "soft_topk",
            ...
        }

    Returns:
        {"success": true, "persona_id": 123}
    """
    data = request.json

    # 필수 필드 확인
    role_key = data.get("role_key")
    role_name = data.get("role_name")

    if not role_key or not role_name:
        return jsonify({"error": "role_key와 role_name은 필수입니다."}), 400

    # 중복 확인
    existing = PersonaDefinition.query.filter_by(role_key=role_key).first()
    if existing:
        return jsonify({"error": "이미 존재하는 role_key입니다."}), 400

    try:
        # 새 페르소나 생성
        persona = PersonaDefinition(
            role_key=role_key,
            role_name=role_name,
            description=data.get("description", ""),
            icon=data.get("icon", "🤖"),
            is_system=False,  # 관리자가 만든 것은 시스템 페르소나 아님
            is_active=data.get("is_active", True),
            created_by=current_user.id,
            # AI 모델 설정
            model_openai=data.get("model_openai", "gpt-4o-mini"),
            model_anthropic=data.get("model_anthropic", "claude-haiku-4-5-20251001"),
            model_google=data.get("model_google", "gemini-3-flash-preview"),
            model_xai=data.get("model_xai", "grok-4-1-fast-reasoning"),
            max_tokens=data.get("max_tokens", 4096),
            # 권한 설정
            allow_user=data.get("allow_user", True),
            allow_teacher=data.get("allow_teacher", True),
            restrict_google=data.get("restrict_google", False),
            restrict_anthropic=data.get("restrict_anthropic", False),
            restrict_openai=data.get("restrict_openai", False),
            restrict_xai=data.get("restrict_xai", False),
            # RAG 설정
            use_rag=data.get("use_rag", False),
            retrieval_strategy=data.get("retrieval_strategy", "soft_topk"),
            rag_top_k=data.get("rag_top_k", 3),
            rag_max_k=data.get("rag_max_k", 7),
            rag_similarity_threshold=data.get("rag_similarity_threshold", 0.5),
            rag_gap_threshold=data.get("rag_gap_threshold", 0.1)
        )

        db.session.add(persona)
        db.session.commit()

        # 지식 베이스 생성 (RAG 사용 시)
        if data.get("use_rag", False):
            kb = PersonaKnowledgeBase(
                persona_id=persona.id,
                created_by=current_user.id,
                chunk_strategy=data.get("chunk_strategy", "paragraph"),
                chunk_size=data.get("chunk_size", 500),
                chunk_overlap=data.get("chunk_overlap", 100)
            )
            db.session.add(kb)
            db.session.commit()

        # 기본 시스템 프롬프트 생성 (optional)
        default_prompt = data.get("default_prompt")
        if default_prompt:
            prompt = PersonaSystemPrompt(
                persona_id=persona.id,
                provider="default",
                system_prompt=default_prompt,
                updated_by=current_user.id
            )
            db.session.add(prompt)
            db.session.commit()

        return jsonify({
            "success": True,
            "persona_id": persona.id,
            "role_key": persona.role_key
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"페르소나 생성 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>", methods=["PUT"])
@login_required
def update_persona(persona_id):
    """
    페르소나 설정 수정 (권한 체크)

    Args:
        persona_id: 수정할 페르소나 ID

    Request Body:
        수정할 필드들 (전체 또는 일부)

    Returns:
        {"success": true}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    # 권한 체크: 관리자 또는 해당 페르소나의 관리 교사
    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "해당 페르소나에 대한 수정 권한이 없습니다."}), 403

    data = request.json

    try:
        # 기본 정보 수정
        if "role_name" in data:
            persona.role_name = data["role_name"]
        if "description" in data:
            persona.description = data["description"]
        if "icon" in data:
            persona.icon = data["icon"]
        if "is_active" in data:
            persona.is_active = data["is_active"]

        # AI 모델 설정
        if "model_openai" in data:
            persona.model_openai = data["model_openai"]
        if "model_anthropic" in data:
            persona.model_anthropic = data["model_anthropic"]
        if "model_google" in data:
            persona.model_google = data["model_google"]
        if "model_xai" in data:
            persona.model_xai = data["model_xai"]
        if "max_tokens" in data:
            persona.max_tokens = data["max_tokens"]

        # 권한 설정
        if "allow_user" in data:
            persona.allow_user = data["allow_user"]
        if "allow_teacher" in data:
            persona.allow_teacher = data["allow_teacher"]
        if "restrict_google" in data:
            persona.restrict_google = data["restrict_google"]
        if "restrict_anthropic" in data:
            persona.restrict_anthropic = data["restrict_anthropic"]
        if "restrict_openai" in data:
            persona.restrict_openai = data["restrict_openai"]
        if "restrict_xai" in data:
            persona.restrict_xai = data["restrict_xai"]

        # RAG 설정
        if "use_rag" in data:
            persona.use_rag = data["use_rag"]
        if "retrieval_strategy" in data:
            persona.retrieval_strategy = data["retrieval_strategy"]
        if "rag_top_k" in data:
            persona.rag_top_k = data["rag_top_k"]
        if "rag_max_k" in data:
            persona.rag_max_k = data["rag_max_k"]
        if "rag_similarity_threshold" in data:
            persona.rag_similarity_threshold = data["rag_similarity_threshold"]
        if "rag_gap_threshold" in data:
            persona.rag_gap_threshold = data["rag_gap_threshold"]

        # 청크 설정 (지식 베이스 업데이트)
        if any(k in data for k in ["chunk_strategy", "chunk_size", "chunk_overlap"]):
            # 페르소나의 지식 베이스 가져오기 (없으면 생성)
            kb = PersonaKnowledgeBase.query.filter_by(
                persona_id=persona_id,
                is_active=True
            ).first()

            if not kb:
                # 지식 베이스가 없으면 생성
                kb = PersonaKnowledgeBase(
                    persona_id=persona_id,
                    name=f"{persona.role_name} 지식 베이스",
                    description=f"{persona.role_name}의 참고 자료",
                    created_by=current_user.id,
                    chunk_strategy=data.get("chunk_strategy", "paragraph"),
                    chunk_size=data.get("chunk_size", 500),
                    chunk_overlap=data.get("chunk_overlap", 100)
                )
                db.session.add(kb)
            else:
                # 기존 지식 베이스 업데이트
                if "chunk_strategy" in data:
                    kb.chunk_strategy = data["chunk_strategy"]
                if "chunk_size" in data:
                    kb.chunk_size = data["chunk_size"]
                if "chunk_overlap" in data:
                    kb.chunk_overlap = data["chunk_overlap"]
                kb.updated_at = datetime.datetime.utcnow()

        persona.updated_at = datetime.datetime.utcnow()
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"수정 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>", methods=["DELETE"])
@admin_required
def delete_persona(persona_id):
    """
    페르소나 삭제 (CASCADE로 연관 데이터 모두 삭제)

    Args:
        persona_id: 삭제할 페르소나 ID

    Returns:
        {"success": true}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    # 시스템 페르소나는 삭제 불가
    if persona.is_system:
        return jsonify({"error": "시스템 페르소나는 삭제할 수 없습니다."}), 400

    try:
        role_name = persona.role_name
        db.session.delete(persona)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"'{role_name}' 페르소나가 삭제되었습니다."
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"삭제 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/teachers", methods=["GET"])
@admin_required
def get_persona_teachers(persona_id):
    """
    페르소나의 권한 있는 교사 목록 조회

    Args:
        persona_id: 페르소나 ID

    Returns:
        {"teachers": [...], "available_teachers": [...]}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    # 현재 권한 있는 교사
    permissions = PersonaTeacherPermission.query.filter_by(
        persona_id=persona_id
    ).all()

    current_teachers = []
    teacher_ids = set()
    for perm in permissions:
        teacher = db.session.get(User, perm.teacher_id)
        if teacher:
            current_teachers.append({
                "id": teacher.id,
                "username": teacher.username,
                "email": teacher.email,
                "can_edit_prompt": perm.can_edit_prompt,
                "can_manage_knowledge": perm.can_manage_knowledge,
                "can_view_analytics": perm.can_view_analytics
            })
            teacher_ids.add(teacher.id)

    # 권한 부여 가능한 교사 (role='teacher')
    all_teachers = User.query.filter_by(role="teacher", is_approved=True).all()
    available_teachers = [
        {"id": t.id, "username": t.username, "email": t.email}
        for t in all_teachers
        if t.id not in teacher_ids
    ]

    return jsonify({
        "teachers": current_teachers,
        "available_teachers": available_teachers
    })


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/grant-teacher", methods=["POST"])
@admin_required
def grant_teacher_permission(persona_id):
    """
    교사에게 페르소나 관리 권한 부여

    Args:
        persona_id: 페르소나 ID

    Request Body:
        {
            "teacher_id": 123,
            "can_edit_prompt": true,
            "can_manage_knowledge": true,
            "can_view_analytics": true
        }

    Returns:
        {"success": true}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    data = request.json
    teacher_id = data.get("teacher_id")

    if not teacher_id:
        return jsonify({"error": "teacher_id가 필요합니다."}), 400

    teacher = db.session.get(User, teacher_id)
    if not teacher or teacher.role != "teacher":
        return jsonify({"error": "유효한 교사가 아닙니다."}), 400

    # 중복 확인
    existing = PersonaTeacherPermission.query.filter_by(
        persona_id=persona_id,
        teacher_id=teacher_id
    ).first()

    if existing:
        return jsonify({"error": "이미 권한이 부여되어 있습니다."}), 400

    try:
        permission = PersonaTeacherPermission(
            persona_id=persona_id,
            teacher_id=teacher_id,
            can_edit_prompt=data.get("can_edit_prompt", True),
            can_manage_knowledge=data.get("can_manage_knowledge", True),
            can_view_analytics=data.get("can_view_analytics", True),
            granted_by=current_user.id
        )

        db.session.add(permission)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"권한 부여 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/revoke-teacher/<int:teacher_id>", methods=["DELETE"])
@admin_required
def revoke_teacher_permission(persona_id, teacher_id):
    """
    교사의 페르소나 관리 권한 회수

    Args:
        persona_id: 페르소나 ID
        teacher_id: 교사 ID

    Returns:
        {"success": true}
    """
    permission = PersonaTeacherPermission.query.filter_by(
        persona_id=persona_id,
        teacher_id=teacher_id
    ).first()

    if not permission:
        return jsonify({"error": "권한을 찾을 수 없습니다."}), 404

    try:
        db.session.delete(permission)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"권한 회수 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/students", methods=["GET"])
@login_required
def get_persona_students(persona_id):
    """
    페르소나에 배정된 학생 목록 조회

    Args:
        persona_id: 페르소나 ID

    Returns:
        {"students": [...], "available_students": [...], "is_restricted": bool}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    # 현재 배정된 학생 ID 집합
    permissions = PersonaStudentPermission.query.filter_by(persona_id=persona_id).all()
    assigned_ids = {perm.student_id for perm in permissions}

    # 전체 승인된 학생 목록 (is_assigned 플래그 포함)
    all_students_q = User.query.filter_by(role="user", is_approved=True).order_by(User.username.asc()).all()
    all_students = [
        {
            "id": s.id,
            "username": s.username,
            "email": s.email,
            "is_assigned": s.id in assigned_ids
        }
        for s in all_students_q
    ]

    # 배정된 학생만 따로 (섹션 목록용)
    current_students = [s for s in all_students if s["is_assigned"]]

    return jsonify({
        "students": current_students,
        "all_students": all_students,
        "is_restricted": len(current_students) > 0
    })


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/assign-student", methods=["POST"])
@login_required
def assign_student_permission(persona_id):
    """
    학생에게 페르소나 접근 권한 부여

    Args:
        persona_id: 페르소나 ID

    Request Body:
        {"student_id": 123}

    Returns:
        {"success": true}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다."}), 404

    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    data = request.json or {}
    student_id = data.get("student_id")

    if not student_id:
        return jsonify({"error": "student_id가 필요합니다."}), 400

    student = db.session.get(User, student_id)
    if not student or student.role != "user":
        return jsonify({"error": "유효한 학생이 아닙니다."}), 400

    # 중복 확인
    existing = PersonaStudentPermission.query.filter_by(
        persona_id=persona_id,
        student_id=student_id
    ).first()

    if existing:
        return jsonify({"error": "이미 배정되어 있습니다."}), 400

    try:
        permission = PersonaStudentPermission(
            persona_id=persona_id,
            student_id=student_id,
            granted_by=current_user.id
        )
        db.session.add(permission)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"학생 배정 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/unassign-student/<int:student_id>", methods=["DELETE"])
@login_required
def unassign_student_permission(persona_id, student_id):
    """
    학생의 페르소나 접근 권한 회수

    Args:
        persona_id: 페르소나 ID
        student_id: 학생 ID

    Returns:
        {"success": true}
    """
    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    permission = PersonaStudentPermission.query.filter_by(
        persona_id=persona_id,
        student_id=student_id
    ).first()

    if not permission:
        return jsonify({"error": "배정 정보를 찾을 수 없습니다."}), 404

    try:
        db.session.delete(permission)
        db.session.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"배정 취소 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/prompts", methods=["GET"])
@login_required
def get_persona_prompts(persona_id):
    """페르소나의 모든 시스템 프롬프트 조회 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Returns:
        {"prompts": [{"provider": "default", "system_prompt": "..."}, ...]}
    """
    # 권한 체크: 관리자 또는 프롬프트 조회 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_edit_prompt'):
        return jsonify({"error": "프롬프트 조회 권한이 없습니다."}), 403

    prompts = PersonaSystemPrompt.query.filter_by(persona_id=persona_id).all()

    return jsonify({
        "prompts": [
            {
                "provider": p.provider,
                "system_prompt": p.system_prompt
            }
            for p in prompts
        ]
    })


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/prompt", methods=["PUT"])
@login_required
def update_persona_prompt(persona_id):
    """시스템 프롬프트 수정 또는 생성 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Request Body:
        {
            "provider": "default|openai|anthropic|google",
            "system_prompt": "..."
        }

    Returns:
        {"success": true}
    """
    persona = db.session.get(PersonaDefinition, persona_id)
    if not persona:
        return jsonify({"error": "페르소나를 찾을 수 없습니다"}), 404

    # 권한 체크: 관리자 또는 프롬프트 수정 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_edit_prompt'):
        return jsonify({"error": "프롬프트 수정 권한이 없습니다."}), 403

    data = request.json
    provider = data.get("provider", "default")
    system_prompt = data.get("system_prompt", "")

    if not system_prompt:
        return jsonify({"error": "프롬프트 내용이 필요합니다"}), 400

    try:
        # 기존 프롬프트 찾기
        prompt = PersonaSystemPrompt.query.filter_by(
            persona_id=persona_id,
            provider=provider
        ).first()

        if prompt:
            # 수정
            prompt.system_prompt = system_prompt
            prompt.updated_by = current_user.id
            prompt.updated_at = datetime.datetime.utcnow()
        else:
            # 생성
            prompt = PersonaSystemPrompt(
                persona_id=persona_id,
                provider=provider,
                system_prompt=system_prompt,
                updated_by=current_user.id
            )
            db.session.add(prompt)

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"저장 실패: {str(e)}"}), 500


# ================================================================
# 시스템 프롬프트 스냅샷 API
# ================================================================

@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/prompt-snapshots", methods=["GET"])
@login_required
def get_prompt_snapshots(persona_id):
    """페르소나의 프롬프트 스냅샷 5개 슬롯 목록 반환."""
    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    snapshots = PersonaPromptSnapshot.query.filter_by(persona_id=persona_id).all()
    slot_map = {s.slot_number: s for s in snapshots}

    slots = []
    for i in range(1, 6):
        s = slot_map.get(i)
        slots.append({
            "slot": i,
            "memo": s.memo if s else None,
            "saved_at": s.saved_at.strftime("%Y-%m-%d %H:%M") if s else None,
            "empty": s is None
        })

    return jsonify({"slots": slots})


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/prompt-snapshots/<int:slot>", methods=["POST"])
@login_required
def save_prompt_snapshot(persona_id, slot):
    """현재 공급사별 프롬프트를 슬롯에 저장."""
    if slot < 1 or slot > 5:
        return jsonify({"error": "슬롯 번호는 1~5 사이여야 합니다."}), 400

    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    # 현재 페르소나의 모든 provider 프롬프트 수집
    prompts = {p.provider: p.system_prompt for p in
               PersonaSystemPrompt.query.filter_by(persona_id=persona_id).all()}

    data = request.json or {}
    memo = (data.get("memo") or "").strip()[:50]

    try:
        existing = PersonaPromptSnapshot.query.filter_by(
            persona_id=persona_id, slot_number=slot
        ).first()

        if existing:
            existing.memo = memo
            existing.prompt_default   = prompts.get("default", "")
            existing.prompt_openai    = prompts.get("openai", "")
            existing.prompt_anthropic = prompts.get("anthropic", "")
            existing.prompt_google    = prompts.get("google", "")
            existing.prompt_xai       = prompts.get("xai", "")
            existing.saved_at = datetime.datetime.utcnow()
            existing.saved_by = current_user.id
        else:
            snap = PersonaPromptSnapshot(
                persona_id=persona_id,
                slot_number=slot,
                memo=memo,
                prompt_default=prompts.get("default", ""),
                prompt_openai=prompts.get("openai", ""),
                prompt_anthropic=prompts.get("anthropic", ""),
                prompt_google=prompts.get("google", ""),
                prompt_xai=prompts.get("xai", ""),
                saved_by=current_user.id
            )
            db.session.add(snap)

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"저장 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/prompt-snapshots/<int:slot>/restore", methods=["POST"])
@login_required
def restore_prompt_snapshot(persona_id, slot):
    """슬롯에서 프롬프트를 복원하여 반환 (DB에 즉시 덮어씀)."""
    if not can_manage_persona(current_user, persona_id):
        return jsonify({"error": "권한이 없습니다."}), 403

    snap = PersonaPromptSnapshot.query.filter_by(
        persona_id=persona_id, slot_number=slot
    ).first()

    if not snap:
        return jsonify({"error": "해당 슬롯에 저장된 내용이 없습니다."}), 404

    provider_map = {
        "default":   snap.prompt_default,
        "openai":    snap.prompt_openai,
        "anthropic": snap.prompt_anthropic,
        "google":    snap.prompt_google,
        "xai":       snap.prompt_xai,
    }

    try:
        for provider, prompt_text in provider_map.items():
            existing = PersonaSystemPrompt.query.filter_by(
                persona_id=persona_id, provider=provider
            ).first()
            if existing:
                existing.system_prompt = prompt_text
                existing.updated_by = current_user.id
                existing.updated_at = datetime.datetime.utcnow()
            elif prompt_text:
                db.session.add(PersonaSystemPrompt(
                    persona_id=persona_id,
                    provider=provider,
                    system_prompt=prompt_text,
                    updated_by=current_user.id
                ))

        db.session.commit()

        return jsonify({
            "success": True,
            "prompts": provider_map
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"복원 실패: {str(e)}"}), 500


# ================================================================
# RAG 지식 베이스 관리 API
# ================================================================

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'docx', 'doc'}
UPLOAD_FOLDER = 'static/uploads/knowledge'

def allowed_file(filename):
    """허용된 파일 확장자 확인"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/knowledge/upload", methods=["POST"])
@login_required
def upload_knowledge_document(persona_id):
    """
    지식 베이스에 문서 업로드 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Request:
        - file: 업로드할 파일 (multipart/form-data)

    Returns:
        {
            "success": True,
            "document_id": 생성된 문서 ID,
            "filename": 파일명,
            "message": "업로드 성공. 벡터화 작업이 백그라운드에서 진행됩니다."
        }
    """
    # 권한 체크: 관리자 또는 지식 베이스 관리 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_manage_knowledge'):
        return jsonify({"error": "지식 베이스 관리 권한이 없습니다."}), 403

    try:
        # 페르소나 확인
        persona = db.session.get(PersonaDefinition, persona_id)
        if not persona:
            return jsonify({"error": "페르소나를 찾을 수 없습니다"}), 404

        # RAG 활성화 확인
        if not persona.use_rag:
            return jsonify({"error": "이 페르소나는 RAG가 활성화되지 않았습니다"}), 400

        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"error": "파일이 없습니다"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "파일명이 비어있습니다"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": f"허용되지 않은 파일 형식입니다. 허용: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

        # 지식 베이스 조회 또는 생성
        kb = PersonaKnowledgeBase.query.filter_by(persona_id=persona_id, is_active=True).first()
        if not kb:
            # 기본 지식 베이스 생성
            kb = PersonaKnowledgeBase(
                persona_id=persona_id,
                name=f"{persona.role_name} 지식 베이스",
                description=f"{persona.role_name}의 참고 자료",
                chunk_strategy='paragraph',
                chunk_size=1000,
                chunk_overlap=200,
                is_active=True
            )
            db.session.add(kb)
            db.session.flush()  # kb.id 생성

        # 파일 저장
        original_filename = file.filename  # 원본 파일명 유지 (한글 포함)
        safe_filename = secure_filename(file.filename)  # 저장용 안전한 파일명
        timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{safe_filename}"

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(file_path)

        file_size = os.path.getsize(file_path)

        # 문서 메타데이터 저장
        doc = KnowledgeDocument(
            knowledge_base_id=kb.id,
            filename=original_filename,  # 원본 파일명 저장 (한글 포함)
            file_path=file_path,
            file_size=file_size,
            file_type=original_filename.rsplit('.', 1)[1].lower(),
            uploaded_by=current_user.id,
            processing_status='pending'
        )
        db.session.add(doc)
        db.session.commit()

        # 백그라운드 작업 시작 (Celery)
        process_document_async.delay(doc.id)

        return jsonify({
            "success": True,
            "document_id": doc.id,
            "filename": original_filename,
            "message": "업로드 성공. 벡터화 작업이 백그라운드에서 진행됩니다."
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"업로드 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/knowledge/documents", methods=["GET"])
@login_required
def get_knowledge_documents(persona_id):
    """
    페르소나의 지식 베이스 문서 목록 조회 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Returns:
        {
            "documents": [
                {
                    "id": 문서 ID,
                    "filename": "파일명.pdf",
                    "file_size": 파일 크기(bytes),
                    "file_type": "pdf",
                    "uploaded_at": "2026-02-15T10:30:00",
                    "processing_status": "completed" | "processing" | "failed" | "pending",
                    "chunk_count": 청크 개수,
                    "error_message": "에러 메시지 (failed일 때만)"
                },
                ...
            ]
        }
    """
    # 권한 체크: 관리자 또는 지식 베이스 관리 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_manage_knowledge'):
        return jsonify({"error": "지식 베이스 조회 권한이 없습니다."}), 403

    try:
        # 지식 베이스 조회
        kb = PersonaKnowledgeBase.query.filter_by(persona_id=persona_id, is_active=True).first()
        if not kb:
            return jsonify({"documents": []})

        # 문서 목록 조회
        documents = KnowledgeDocument.query.filter_by(knowledge_base_id=kb.id).order_by(KnowledgeDocument.uploaded_at.desc()).all()

        doc_list = []
        for doc in documents:
            doc_list.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "file_type": doc.file_type,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "processing_status": doc.processing_status,
                "chunk_count": doc.chunk_count or 0,
                "error_message": doc.error_message
            })

        return jsonify({"documents": doc_list})

    except Exception as e:
        return jsonify({"error": f"조회 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/knowledge/document/<int:doc_id>", methods=["DELETE"])
@login_required
def delete_knowledge_document(persona_id, doc_id):
    """
    지식 베이스에서 문서 삭제 (권한 체크)

    Args:
        persona_id: 페르소나 ID
        doc_id: 문서 ID

    Returns:
        {
            "success": True,
            "message": "문서가 삭제되었습니다"
        }
    """
    # 권한 체크: 관리자 또는 지식 베이스 관리 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_manage_knowledge'):
        return jsonify({"error": "지식 베이스 삭제 권한이 없습니다."}), 403

    try:
        # 문서 조회
        doc = db.session.get(KnowledgeDocument, doc_id)
        if not doc:
            return jsonify({"error": "문서를 찾을 수 없습니다"}), 404

        # 페르소나 일치 확인
        kb = db.session.get(PersonaKnowledgeBase, doc.knowledge_base_id)
        if not kb or kb.persona_id != persona_id:
            return jsonify({"error": "페르소나가 일치하지 않습니다"}), 403

        # 관련 청크 삭제
        DocumentChunk.query.filter_by(document_id=doc_id).delete()

        # 파일 삭제
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except Exception as e:
                print(f"⚠️ 파일 삭제 실패: {e}")

        # 문서 삭제
        db.session.delete(doc)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "문서가 삭제되었습니다"
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"삭제 실패: {str(e)}"}), 500


@admin_persona_bp.route("/api/admin/persona/<int:persona_id>/knowledge/stats", methods=["GET"])
@login_required
def get_knowledge_stats(persona_id):
    """
    페르소나의 RAG 통계 조회 (권한 체크)

    Args:
        persona_id: 페르소나 ID

    Returns:
        {
            "knowledge_base_count": 지식 베이스 개수,
            "document_count": 총 문서 수,
            "completed_count": 완료된 문서 수,
            "processing_count": 처리 중인 문서 수,
            "failed_count": 실패한 문서 수,
            "chunk_count": 총 청크 수
        }
    """
    # 권한 체크: 관리자 또는 분석 조회 권한이 있는 교사
    if not has_persona_permission(current_user, persona_id, 'can_view_analytics'):
        return jsonify({"error": "통계 조회 권한이 없습니다."}), 403

    try:
        stats = get_rag_statistics(persona_id)
        return jsonify(stats)

    except Exception as e:
        return jsonify({"error": f"통계 조회 실패: {str(e)}"}), 500
