from app import app
from models import SystemConfig
import json

with app.app_context():
    for provider in ["openai", "xai"]:
        config = SystemConfig.query.filter_by(key=f"available_models_metadata_{provider}").first()
        if config:
            models = json.loads(config.value)
            print(f"--- {provider.upper()} MODELS ---")
            for i, m in enumerate(models[:10]):  # Print first 10
                print(f"{i+1}. {m.get('name')} (ID: {m.get('id')})")
        else:
            print(f"No metadata found for {provider}")
