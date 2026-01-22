from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """회원가입 페이지/처리.

    - GET: 회원가입 화면 렌더링
    - POST: 아이디 중복 확인 → 비밀번호 해시 저장 → 첫 가입자는 관리자 지정
    """
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # 동일 아이디가 있으면 가입 차단
        if User.query.filter_by(username=username).first():
            flash("이미 존재하는 아이디입니다.", "error")
            return redirect(url_for("auth.register"))
        new_user = User(username=username)
        new_user.set_password(password)
        # 첫 번째 가입자를 관리자 계정으로 자동 지정
        if User.query.count() == 0:
            new_user.is_admin = True
        db.session.add(new_user)
        db.session.commit()
        flash("가입 완료!", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지/처리.

    - GET: 로그인 화면 렌더링
    - POST: 사용자 조회 → 비밀번호 검증 → 세션 로그인
    """
    if request.method == "POST":
        user = User.query.filter_by(username=request.form.get("username")).first()
        # 아이디/비밀번호 검증 성공 시 로그인 처리
        if user and user.check_password(request.form.get("password")):
            login_user(user)
            return redirect(url_for("chat.index"))
        flash("아이디/비번 확인 필요", "error")
    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """로그아웃 처리 후 로그인 페이지로 이동."""
    logout_user()
    return redirect(url_for("auth.login"))
