from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
import os

from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__)

# OAuth 설정
oauth = OAuth()

def init_oauth(app):
    """앱 팩토리에서 호출하여 OAuth 초기화"""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        access_token_url='https://accounts.google.com/o/oauth2/token',
        access_token_params=None,
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        authorize_params=None,
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid email profile'},
    )

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """기존 ID/PW 회원가입 (관리자 승인 필요)"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if User.query.filter_by(username=username).first():
            flash("이미 존재하는 아이디입니다.", "error")
            return redirect(url_for("auth.register"))
        
        # 신규 유저는 is_approved=False (단, 첫 유저는 관리자로 승인)
        new_user = User(username=username)
        new_user.set_password(password)
        if User.query.count() == 0:
            new_user.is_admin = True
            new_user.is_approved = True
        else:
            new_user.is_approved = False
            
        db.session.add(new_user)
        db.session.commit()
        
        if new_user.is_approved:
            flash("가입 완료! 로그인해주세요.", "success")
        else:
            flash("가입 신청되었습니다. 관리자 승인 후 이용 가능합니다.", "info")
            
        return redirect(url_for("auth.login"))
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """로그인 페이지/처리 (승인 여부 확인)"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            # 승인 여부 확인
            if not user.is_approved:
                flash("관리자 승인 대기 중입니다.", "warning")
                return redirect(url_for("auth.login"))
                
            login_user(user)
            return redirect(url_for("chat.index"))
        flash("아이디/비번 확인 필요", "error")
    return render_template("login.html")


@auth_bp.route("/google/login")
def google_login():
    """구글 로그인 페이지로 리다이렉트"""
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    """구글 로그인 콜백 처리"""
    try:
        token = oauth.google.authorize_access_token()
        resp = oauth.google.get('userinfo')
        user_info = resp.json()
    except Exception as e:
        flash(f"구글 로그인 실패: {str(e)}", "error")
        return redirect(url_for("auth.login"))

    google_id = user_info.get("id")
    email = user_info.get("email")
    name = user_info.get("name") or email.split("@")[0]

    # 사용자 조회 (google_id 또는 이메일로 매칭)
    user = User.query.filter((User.google_id == google_id) | (User.email == email)).first()

    if not user:
        # 신규 가입 (승인 대기)
        user = User(
            username=email, # 식별자로 이메일 사용
            email=email,
            google_id=google_id,
            role="user",
            is_approved=False
        )
        # 비밀번호는 랜덤 설정 (구글 로그인 전용)
        user.set_password(os.urandom(16).hex())
        
        # 첫 사용자는 관리자 자동 승인
        if User.query.count() == 0:
            user.is_admin = True
            user.is_approved = True
            
        db.session.add(user)
        db.session.commit()
        
        if user.is_approved:
            login_user(user)
            return redirect(url_for("chat.index"))
        else:
            flash("가입 신청되었습니다. 관리자 승인 후 이용 가능합니다.", "info")
            return redirect(url_for("auth.login"))
    else:
        # 기존 사용자 정보 업데이트 (google_id가 없는 경우 연동)
        if not user.google_id:
            user.google_id = google_id
            db.session.commit()
            
        # 승인 여부 확인
        if not user.is_approved:
            flash("관리자 승인 대기 중입니다.", "warning")
            return redirect(url_for("auth.login"))
            
        login_user(user)
        return redirect(url_for("chat.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
