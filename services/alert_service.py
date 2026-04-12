"""
조기 개입 알림 감지 서비스.

학생 메시지가 저장될 때마다 호출되어 두 가지 패턴을 감지한다:
  1. 혼란 키워드 — "모르겠다", "이해가 안 된다" 류의 표현
  2. 반복 질문   — 동일 세션 내에서 유사한 질문을 3회 이상 반복

중복 알림 방지:
  - 키워드 알림: 같은 세션에서 1시간 이내에 동일 유형 알림이 없을 때만 생성
  - 반복 알림:   같은 세션에서 2시간 이내에 동일 유형 알림이 없을 때만 생성
"""

import datetime
import re

from extensions import db
from models import LearningAlert, Message

# ---------------------------------------------------------------------------
# 혼란 키워드 목록
# ---------------------------------------------------------------------------
CONFUSION_KEYWORDS: list[str] = [
    "모르겠",       # 모르겠어, 모르겠다, 모르겠는데
    "이해가 안",    # 이해가 안 가, 이해가 안 돼
    "이해 안",      # 이해 안 됨
    "이해 못",      # 이해 못 했어
    "무슨 말",      # 무슨 말인지
    "무슨 뜻",      # 무슨 뜻인지
    "헷갈",         # 헷갈려, 헷갈리는데
    "다시 설명",    # 다시 설명해줘
    "잘 모르",      # 잘 모르겠어
    "뭔 소리",      # 뭔 소리야
    "뭔소리",
    "어떤 건지 모르",
    "무슨 건지",
    "이해가 어렵",
    "이해하기 어렵",
    "알 수가 없",
    "알 수 없",
]

# 반복 감지 설정
REPEAT_SIMILARITY_THRESHOLD = 0.45  # Jaccard 유사도 임계값
REPEAT_MIN_SIMILAR_COUNT = 2        # 현재 메시지와 유사한 과거 메시지 수 (이 수 이상이면 총 3회 이상)
REPEAT_LOOKBACK = 20                # 과거 메시지 탐색 범위
REPEAT_MIN_LEN = 8                  # 너무 짧은 메시지(감사합니다, 네 등)는 제외

# 중복 알림 방지 시간 창
KEYWORD_COOLDOWN_HOURS = 1
REPEAT_COOLDOWN_HOURS = 2


# ---------------------------------------------------------------------------
# 공개 진입점
# ---------------------------------------------------------------------------

def check_and_create_alerts(
    user_id: int,
    session_id: int,
    role_key: str,
    content: str,
) -> None:
    """
    학생 메시지 저장 직후 호출한다.
    감지된 패턴이 있으면 LearningAlert 레코드를 생성하고 커밋한다.
    예외는 호출자(chat.py)에서 catch — 채팅 흐름에 영향 없음.
    """
    if not content or not content.strip():
        return

    content = content.strip()
    now = datetime.datetime.utcnow()

    _check_keyword(user_id, session_id, role_key, content, now)
    _check_repetition(user_id, session_id, role_key, content, now)


# ---------------------------------------------------------------------------
# 키워드 감지
# ---------------------------------------------------------------------------

def _check_keyword(
    user_id: int,
    session_id: int,
    role_key: str,
    content: str,
    now: datetime.datetime,
) -> None:
    matched = next(
        (kw for kw in CONFUSION_KEYWORDS if kw in content),
        None,
    )
    if not matched:
        return

    cooldown = now - datetime.timedelta(hours=KEYWORD_COOLDOWN_HOURS)
    already_exists = (
        LearningAlert.query
        .filter_by(student_id=user_id, session_id=session_id, alert_type="keyword")
        .filter(LearningAlert.created_at >= cooldown)
        .first()
    )
    if already_exists:
        return

    alert = LearningAlert(
        student_id=user_id,
        session_id=session_id,
        role_key=role_key,
        alert_type="keyword",
        detail=f'키워드 감지: "{matched}"',
        trigger_content=content[:300],
    )
    db.session.add(alert)
    db.session.commit()


# ---------------------------------------------------------------------------
# 반복 질문 감지
# ---------------------------------------------------------------------------

def _jaccard(a: str, b: str) -> float:
    """두 문자열의 어절(공백 분리) 기준 Jaccard 유사도를 반환한다."""
    # 짧은 단어(1~2글자) 제거: 조사·부사 등 노이즈 감소
    def tokens(s: str) -> set[str]:
        return {w for w in re.split(r"\s+", s.strip()) if len(w) > 2}

    set_a, set_b = tokens(a), tokens(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _check_repetition(
    user_id: int,
    session_id: int,
    role_key: str,
    content: str,
    now: datetime.datetime,
) -> None:
    if len(content) < REPEAT_MIN_LEN:
        return

    # 최근 N개의 학생 메시지를 가져온다 (현재 메시지는 이미 저장된 상태)
    past_msgs = (
        Message.query
        .filter_by(session_id=session_id, is_user=True)
        .order_by(Message.timestamp.desc())
        .limit(REPEAT_LOOKBACK + 1)   # +1: 방금 저장된 현재 메시지 포함
        .all()
    )

    # 방금 저장된 현재 메시지(content가 동일한 가장 최근 것)는 제외
    past_contents = [
        m.content for m in past_msgs
        if m.content and m.content.strip() != content
    ][:REPEAT_LOOKBACK]

    similar_count = sum(
        1 for pc in past_contents
        if _jaccard(content, pc) >= REPEAT_SIMILARITY_THRESHOLD
    )

    if similar_count < REPEAT_MIN_SIMILAR_COUNT:
        return

    cooldown = now - datetime.timedelta(hours=REPEAT_COOLDOWN_HOURS)
    already_exists = (
        LearningAlert.query
        .filter_by(student_id=user_id, session_id=session_id, alert_type="repetition")
        .filter(LearningAlert.created_at >= cooldown)
        .first()
    )
    if already_exists:
        return

    alert = LearningAlert(
        student_id=user_id,
        session_id=session_id,
        role_key=role_key,
        alert_type="repetition",
        detail=f"유사 질문 {similar_count + 1}회 반복",
        trigger_content=content[:300],
    )
    db.session.add(alert)
    db.session.commit()
