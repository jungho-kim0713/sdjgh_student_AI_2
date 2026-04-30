import csv
import io
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, Response
from flask_login import login_required, current_user
from extensions import db
from models import User

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
