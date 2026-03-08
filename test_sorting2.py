from app import app
from models import SystemConfig
import json

with app.app_context():
    for provider in ["openai", "xai"]:
        config = SystemConfig.query.filter_by(key=f"available_models_metadata_{provider}").first()
        if config:
            models = json.loads(config.value)
            print(f"--- {provider.upper()} MODELS ---")
            for m in models[:10]:
                print(m.get('id'))
