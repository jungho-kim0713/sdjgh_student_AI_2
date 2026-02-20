from app import app, db
from models import User

with app.app_context():
    users = User.query.all()
    print(f"{'ID':<5} {'Username':<20} {'Is Admin':<10} {'Role':<10}")
    print("-" * 50)
    for user in users:
        print(f"{user.id:<5} {user.username:<20} {user.is_admin:<10} {user.role:<10}")
