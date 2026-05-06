import csv
import io
import os
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, Response, current_app
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import (User, ChatSession, Message, ChatFile,
                    PersonaDefinition, PersonaSystemPrompt, PersonaTeacherPermission,
                    PersonaStudentPermission, PersonaPromptSnapshot,
                    PersonaKnowledgeBase, KnowledgeDocument)

admin_users_bp = Blueprint("admin_users", __name__)

@admin_users_bp.route("/admin/users", methods=["GET"])
@login_required
def user_management():
    """관리자 사용자 관리 페이지 렌더링"""
    if not current_user.is_admin:
        flash("관리자 권한이 필요합니다.", "error")
        return redirect(url_for("chat.index"))
    
    users = User.query.order_by(User.id.asc()).all()
    return render_template("admin_users.html", users=users)

@admin_users_bp.route("/admin/users/approve/<int:user_id>", methods=["POST"])
@login_required
def approve_user(user_id):
    """사용자 승인 처리"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    
    user = db.session.get(User, user_id)
    if user:
        user.is_approved = True
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "User not found"}), 404

@admin_users_bp.route("/admin/users/export_csv", methods=["GET"])
@login_required
def export_users_csv():
    """현재 사용자 DB를 CSV로 다운로드 (관리자 전용)"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403

    users = User.query.order_by(User.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "email", "google_id", "role", "is_admin", "is_approved", "password_hash"])
    for u in users:
        writer.writerow([
            u.id,
            u.username,
            u.email or "",
            u.google_id or "",
            u.role,
            u.is_admin,
            u.is_approved,
            u.password_hash,
        ])

    csv_bytes = output.getvalue().encode("utf-8-sig")  # BOM 포함 → 엑셀 한글 깨짐 방지
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=users_export.csv"},
    )


@admin_users_bp.route("/admin/users/no_history", methods=["GET"])
@login_required
def preview_no_history_users():
    """대화기록이 없는 사용자 목록 조회 (관리자 전용)"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403

    subq = db.session.query(ChatSession.user_id).distinct().subquery()
    users = (
        User.query
        .filter(~User.id.in_(db.session.query(subq.c.user_id)))
        .filter(User.is_admin == False)
        .filter(User.id != current_user.id)
        .order_by(User.id.asc())
        .all()
    )
    return jsonify([
        {"id": u.id, "username": u.username, "email": u.email or "", "role": u.role, "is_approved": u.is_approved}
        for u in users
    ])


@admin_users_bp.route("/admin/users/delete_no_history", methods=["POST"])
@login_required
def delete_no_history_users():
    """대화기록이 없는 사용자 일괄 삭제 (관리자 전용, 관리자 계정 제외)"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403

    subq = db.session.query(ChatSession.user_id).distinct().subquery()
    users = (
        User.query
        .filter(~User.id.in_(db.session.query(subq.c.user_id)))
        .filter(User.is_admin == False)
        .filter(User.id != current_user.id)
        .all()
    )

    deleted = 0
    try:
        for u in users:
            uid = u.id

            # --- user.id를 참조하는 FK 테이블 순서대로 처리 ---

            # 1) 파일 물리 삭제 + ChatFile 레코드 삭제
            for f in ChatFile.query.filter_by(user_id=uid).all():
                try:
                    base = os.path.basename(f.storage_path)
                    if f.file_type and f.file_type.startswith("image/"):
                        path = os.path.join(current_app.config["UPLOAD_FOLDER"], base)
                    else:
                        path = os.path.join(current_app.config["UPLOAD_FOLDER"], "files", base)
                    if os.path.exists(path):
                        os.remove(path)
                except Exception:
                    pass
                db.session.delete(f)

            # 2) 메시지 / 세션
            Message.query.filter_by(user_id=uid).delete()
            ChatSession.query.filter_by(user_id=uid).delete()

            # 3) 페르소나 권한 — 이 유저가 학생/교사로 등록된 행 삭제
            PersonaStudentPermission.query.filter_by(student_id=uid).delete()
            PersonaTeacherPermission.query.filter_by(teacher_id=uid).delete()

            # 4) granted_by / created_by / updated_by 등 nullable FK → NULL 처리
            PersonaStudentPermission.query.filter_by(granted_by=uid).update({"granted_by": None})
            PersonaTeacherPermission.query.filter_by(granted_by=uid).update({"granted_by": None})
            PersonaDefinition.query.filter_by(created_by=uid).update({"created_by": None})
            PersonaSystemPrompt.query.filter_by(updated_by=uid).update({"updated_by": None})
            PersonaPromptSnapshot.query.filter_by(saved_by=uid).update({"saved_by": None})
            PersonaKnowledgeBase.query.filter_by(created_by=uid).update({"created_by": None})
            KnowledgeDocument.query.filter_by(uploaded_by=uid).update({"uploaded_by": None})

            db.session.delete(u)
            deleted += 1

        db.session.commit()
        return jsonify({"success": True, "deleted": deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@admin_users_bp.route("/admin/users/batch_add", methods=["POST"])
@login_required
def batch_add_users():
    """이메일 일괄 등록 (사전 승인)"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    
    text = request.json.get("users_data", request.json.get("emails", ""))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    added_count = 0
    duplicate_count = 0
    
    for line in lines:
        parts = line.split('\t')
        if len(parts) < 2:
            parts = line.split(',')
        if len(parts) < 2:
            parts = line.split()
            
        if len(parts) >= 2:
            name = parts[0].strip()
            email = parts[-1].strip()
        else:
            email = line.strip()
            name = email.split('@')[0]
            
        # 이메일 중복 확인
        existing = User.query.filter((User.email == email) | (User.username == email) | (User.username == f"{name}/{email}")).first()
        if existing:
            duplicate_count += 1
            if not existing.is_approved:
                existing.is_approved = True
                added_count += 1
        else:
            # 빈 껍데기 유저를 생성. (로그인 로직에서 email로 매칭)
            # username을 이름/이메일 형식으로 저장하여 고유성 확보 및 동명이인 구분 가능하게 함
            new_user = User(
                username=f"{name}/{email}",
                email=email,
                is_approved=True,
                role="user",
                password_hash="google_oauth_user" # 비밀번호 로그인 불가
            )
            db.session.add(new_user)
            added_count += 1
            
    db.session.commit()
    return jsonify({"success": True, "added": added_count, "duplicates": duplicate_count})
