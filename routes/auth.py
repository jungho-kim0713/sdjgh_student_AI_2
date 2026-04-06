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
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """기존 ID/PW 회원가입 (관리자 승인 필요)"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirm = request.form.get("password_confirm")

        if len(password) < 5:
            flash("비밀번호가 너무 짧습니다. 5자 이상 입력해주세요.", "error")
            return redirect(url_for("auth.register"))

        if password != password_confirm:
            flash("비밀번호가 일치하지 않습니다.", "error")
            return redirect(url_for("auth.register"))

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
    # [Fix] Proxy 중첩으로 인한 Host 헤더 중복 발생(domain,domain) 및 http 프로토콜 문제 해결
    # url_for(..., _external=True)를 사용하면 오염된 Host 헤더를 그대로 사용하여 리디렉션 URI가 망가짐
    # 따라서 프로덕션 도메인이 감지되면 강제로 올바른 URI를 박아버림
    
    current_host = request.headers.get("Host", "")
    
    if "student-ai.sdjgh-ai.kr" in current_host:
        # 배포 환경: 헤더를 믿지 않고 강제로 고정
        redirect_uri = "https://student-ai.sdjgh-ai.kr/google/callback"
    else:
        # 로컬/개발 환경
        redirect_uri = url_for("auth.google_callback", _external=True)
        
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/google/callback")
def google_callback():
    """구글 로그인 콜백 처리"""
    try:
        token = oauth.google.authorize_access_token()
        resp = oauth.google.get('https://www.googleapis.com/oauth2/v1/userinfo')
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
        # 신규 가입 (승인 대기) - 이름을 입력받기 위해 세션에 저장 후 리다이렉트
        session['pending_google_email'] = email
        session['pending_google_id'] = google_id
        return redirect(url_for("auth.google_register_name"))
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


@auth_bp.route("/google/register_name", methods=["GET", "POST"])
def google_register_name():
    """구글 로그인 후 이름 입력받기"""
    if 'pending_google_email' not in session or 'pending_google_id' not in session:
        return redirect(url_for("auth.login"))
        
    email = session['pending_google_email']
    google_id = session['pending_google_id']
    
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            flash("이름을 입력해주세요.", "error")
            return redirect(url_for("auth.google_register_name"))
            
        user = User(
            username=f"{name}/{email}",
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
        
        # 세션에서 임시 데이터 삭제
        session.pop('pending_google_email', None)
        session.pop('pending_google_id', None)
        
        if user.is_approved:
            login_user(user)
            return redirect(url_for("chat.index"))
        else:
            flash("가입 신청되었습니다. 관리자 승인 후 이용 가능합니다.", "info")
            return redirect(url_for("auth.login"))
            
    return render_template("google_register.html", email=email)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
