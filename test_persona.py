from app import app
from models import PersonaDefinition

with app.app_context():
    personas = PersonaDefinition.query.all()
    print(f"Total Personas: {len(personas)}")
    for p in personas:
        print(f"ID: {p.id}, Role: {p.role_key}, Name: {p.role_name}")
