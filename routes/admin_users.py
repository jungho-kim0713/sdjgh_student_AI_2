from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
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
    
    users = User.query.order_by(User.id.desc()).all()
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

@admin_users_bp.route("/admin/users/batch_add", methods=["POST"])
@login_required
def batch_add_users():
    """이메일 일괄 등록 (사전 승인)"""
    if not current_user.is_admin:
        return jsonify({"error": "Denied"}), 403
    
    text = request.json.get("emails", "")
    emails = [e.strip() for e in text.splitlines() if e.strip()]
    
    added_count = 0
    duplicate_count = 0
    
    for email in emails:
        # 이메일 중복 확인
        existing = User.query.filter((User.email == email) | (User.username == email)).first()
        if existing:
            duplicate_count += 1
            if not existing.is_approved:
                existing.is_approved = True
                added_count += 1
        else:
            # 구글 로그인 시 매칭될 수 있도록 email과 username을 동일하게 설정하거나
            # google_id는 비워두고 email만 매칭 키로 사용.
            # 여기서는 빈 껍데기 유저를 생성. (로그인 로직에서 email로 매칭)
            new_user = User(
                username=email, # 닉네임을 이메일로 임시 설정
                email=email,
                is_approved=True,
                role="user",
                password_hash="google_oauth_user" # 비밀번호 로그인 불가
            )
            db.session.add(new_user)
            added_count += 1
            
    db.session.commit()
    return jsonify({"success": True, "added": added_count, "duplicates": duplicate_count})
