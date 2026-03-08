import requests
session = requests.Session()
# Assuming we can't easily bypass login, let's just run get_enabled_models_merged outside the request context
from app import app
from routes.admin_persona import get_enabled_models_merged
with app.app_context():
    try:
        models = get_enabled_models_merged()
        print("Success! Models:", len(models))
    except Exception as e:
        import traceback
        traceback.print_exc()
