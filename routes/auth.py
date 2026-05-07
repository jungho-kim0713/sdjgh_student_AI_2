from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required
from authlib.integrations.flask_client import OAuth
import os
import jwt

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
    """자체 회원가입 비활성화 — SSO(플랫폼)로만 가입 가능"""
    flash("회원가입은 학교 플랫폼(SSO)을 통해 이루어집니다.", "info")
    return redirect(url_for("auth.login"))


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
        # 신규 가입 차단 — SSO를 통해서만 계정 생성 가능
        flash("등록되지 않은 계정입니다. 학교 플랫폼(SSO)을 통해 접속해주세요.", "error")
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


@auth_bp.route("/google/register_name", methods=["GET", "POST"])
def google_register_name():
    """Google 신규 가입 비활성화 — SSO(플랫폼)로만 가입 가능"""
    session.pop('pending_google_email', None)
    session.pop('pending_google_id', None)
    flash("등록되지 않은 계정입니다. 학교 플랫폼(SSO)을 통해 접속해주세요.", "error")
    return redirect(url_for("auth.login"))


@auth_bp.route("/sso")
def sso_login():
    """플랫폼 서버에서 발급한 JWT 토큰으로 자동 로그인"""
    token = request.args.get("token", "")
    if not token:
        flash("토큰이 없습니다.", "error")
        return redirect(url_for("auth.login"))

    secret = os.getenv("PLATFORM_JWT_SECRET", "")
    if not secret:
        flash("서버 설정 오류입니다.", "error")
        return redirect(url_for("auth.login"))

    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        flash("로그인 세션이 만료됐습니다. 플랫폼에서 다시 접속해주세요.", "warning")
        return redirect(url_for("auth.login"))
    except jwt.InvalidTokenError:
        flash("유효하지 않은 토큰입니다.", "error")
        return redirect(url_for("auth.login"))

    user_id  = payload.get("userId", "")
    platform_role = payload.get("role", "학생")

    if not user_id:
        flash("토큰에 사용자 정보가 없습니다.", "error")
        return redirect(url_for("auth.login"))

    # 플랫폼 role → 이 앱의 role 매핑
    role_map = {"관리자": "teacher", "교사": "teacher", "학생": "user"}
    role = role_map.get(platform_role, "user")
    is_admin = (platform_role == "관리자")

    user = User.query.filter_by(username=user_id).first()
    if not user:
        user = User(
            username=user_id,
            role=role,
            is_admin=is_admin,
            is_approved=True,
        )
        user.set_password(os.urandom(16).hex())  # SSO 전용 계정, PW 로그인 불가
        db.session.add(user)
        db.session.commit()
    else:
        # 플랫폼에서 권한이 바뀌었을 경우 동기화
        if user.role != role or user.is_admin != is_admin:
            user.role = role
            user.is_admin = is_admin
            db.session.commit()

    login_user(user)
    return redirect(url_for("chat.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    platform_url = os.getenv("PLATFORM_URL", "https://platform.sdjgh-ai.kr/")
    return redirect(platform_url)
