from app import app
from routes.status import refresh_models
from flask import g
import os
import json

# mock current user
class MockUser:
    is_admin = True
    role = "admin"

with app.app_context():
    from flask_login import login_user
    # bypass login_required by hacking the refresh_models or just calling the inner logic
    # Actually, it's easier to just call the logic since refresh_models depends on current_user
    from services.ai_service import get_openai_client
    from routes.status import generate_model_metadata_via_claude
    from models import SystemConfig
    
    print("Fetching OpenAI models...")
    client = get_openai_client()
    api_models = [m.id for m in client.models.list()]
    print(f"Fetched {len(api_models)} models from OpenAI.")
    
    print("Calling Claude for metadata generation...")
    metadata = generate_model_metadata_via_claude("openai", api_models)
    
    if metadata:
        print(f"Claude returned {len(metadata)} models.")
        print(json.dumps(metadata[:2], indent=2))
    else:
        print("Claude returned None")
