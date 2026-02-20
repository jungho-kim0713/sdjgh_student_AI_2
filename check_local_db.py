from app import app
from models import User, PersonaDefinition
from extensions import db

with app.app_context():
    print("=== Checking Local User '관리자' ===")
    user = User.query.filter_by(username='관리자').first()
    if user:
        print(f"ID: {user.id}")
        print(f"Username: {user.username}")
        print(f"Is Admin: {user.is_admin}")
        print(f"Role: {user.role}")
    else:
        print("User '관리자' not found!")
    
    print("\n=== Checking Persona Definitions ===")
    count = PersonaDefinition.query.count()
    print(f"Total Personas: {count}")
    personas = PersonaDefinition.query.all()
    for p in personas:
        print(f" - {p.role_name} ({p.role_key})")
