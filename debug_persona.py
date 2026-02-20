from app import app
from models import User, PersonaDefinition
from extensions import db
from routes.admin_persona import get_manageable_persona_ids, is_persona_manager

with app.app_context():
    # Try multiple admin usernames
    for username in ['관리자', 'admin']:
        user = User.query.filter_by(username=username).first()
        if user:
            print(f"\n[Checking user: {username}]")
            print(f"User ID: {user.id}")
            print(f"Is Admin: {user.is_admin} (Type: {type(user.is_admin)})")
            print(f"Role: {user.role}")
            
            is_manager = is_persona_manager(user)
            print(f"Is Persona Manager: {is_manager}")
            
            manageable_ids = get_manageable_persona_ids(user)
            print(f"Manageable IDs: {manageable_ids}")
            
            query = PersonaDefinition.query.order_by(PersonaDefinition.id.asc())
            if manageable_ids is not None:
                print(f"Applying filter: ID in {manageable_ids}")
                query = query.filter(PersonaDefinition.id.in_(manageable_ids))
            else:
                print("No filter applied (Admin access)")
            
            personas = query.all()
            print(f"Personas found: {len(personas)}")
            for p in personas:
                print(f" - ID {p.id}: {p.role_name} ({p.role_key})")
        else:
            print(f"\n[User not found: {username}]")
