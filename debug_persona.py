from app import app
from models import User, PersonaDefinition, PersonaTeacherPermission, PersonaKnowledgeBase
from extensions import db
from routes.admin_persona import get_manageable_persona_ids, is_persona_manager
import json

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
            
            persona_list = []
            for p in personas:
                try:
                    p_dict = {
                        "id": p.id,
                        "role_key": p.role_key,
                        "role_name": p.role_name,
                        "description": p.description,
                        "icon": p.icon,
                        "is_system": p.is_system,
                        "is_active": p.is_active,
                        "use_rag": p.use_rag,
                        "retrieval_strategy": p.retrieval_strategy,
                        "created_at": p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "",
                    }
                    
                    # Test related queries might fail if tables don't exist
                    teacher_count = PersonaTeacherPermission.query.filter_by(persona_id=p.id).count()
                    kb_count = PersonaKnowledgeBase.query.filter_by(persona_id=p.id, is_active=True).count()
                    
                    p_dict["teacher_count"] = teacher_count
                    p_dict["knowledge_base_count"] = kb_count
                    
                    persona_list.append(p_dict)
                    print(f" - Serialized ID {p.id} (Teachers: {teacher_count}, KBs: {kb_count})")
                except Exception as e:
                    print(f" ! Failed to serialize ID {p.id}: {e}")
            
            try:
                json_output = json.dumps(persona_list, ensure_ascii=False, indent=2)
                print("JSON Serialization Successful")
            except Exception as e:
                print(f"JSON Serialization Failed: {e}")

        else:
            print(f"\n[User not found: {username}]")
