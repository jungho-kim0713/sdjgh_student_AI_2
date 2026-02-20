from app import app
from extensions import db
from models import User, PersonaDefinition
from prompts import AI_PERSONAS

with app.app_context():
    print("=== [1] Fixing Admin User Permissions ===")
    target_username = '관리자'
    user = User.query.filter_by(username=target_username).first()
    
    if user:
        if not user.is_admin or user.role != 'admin':
            print(f"User '{target_username}' found. Updating permissions...")
            user.is_admin = True
            user.role = 'admin'
            db.session.commit()
            print("✅ Permissions updated: is_admin=True, role='admin'")
        else:
            print(f"User '{target_username}' already has correct permissions.")
    else:
        print(f"User '{target_username}' not found. Please register first.")

    print("\n=== [2] Seeding Personas ===")
    
    # Check existing count
    current_count = PersonaDefinition.query.count()
    print(f"Current Persona Count: {current_count}")
    
    if current_count == 0:
        print("Seeding default personas...")
        # Import the logic from seed_personas.py dynamically or just run it as a subprocess
        import sys
        import os
        # Run seed_personas.py logic here simplified
        from migrations.seed_personas import seed_personas
        seed_personas()
    else:
        print("Personas already verify existing.")
        # Double check if all 5 exist
        for key in AI_PERSONAS.keys():
            exists = PersonaDefinition.query.filter_by(role_key=key).first()
            if not exists:
                print(f"⚠️ Missing persona: {key} -> running seed check")
                from migrations.seed_personas import seed_personas
                seed_personas()
                break
            else:
                print(f" - {key}: OK")

    print("\n✅ Local environment fix completed.")
