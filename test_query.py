from app import app
from extensions import db
from models import ChatSession, Message, User

with app.app_context():
    try:
        msgs = (
            db.session.query(Message, User.username)
            .outerjoin(User, Message.user_id == User.id)
            .filter(Message.session_id == 140)
            .order_by(Message.timestamp.asc())
            .all()
        )

        message_list = []
        for m in msgs:
            img_url = None
            if m.Message.image_path:
                first_path = m.Message.image_path.split(',')[0]
                img_url = first_path # replace url_for for offline test

            message_list.append(
                {
                    "text": m.Message.content,
                    "image_path": img_url,
                    "sender": "user" if m.Message.is_user else "ai",
                    "username": m.username if m.Message.is_user else "AI",
                }
            )
        import json
        print(json.dumps(message_list))
    except Exception as e:
        import traceback
        traceback.print_exc()
