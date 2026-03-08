from app import app
from models import SystemConfig
import json

with app.app_context():
    for provider in ["openai", "anthropic", "google", "xai"]:
        conf = SystemConfig.query.filter_by(key=f"available_models_metadata_{provider}").first()
        if conf:
            print(f"--- {provider} length ---")
            try:
                data = json.loads(conf.value)
                print(f"Type: {type(data)}")
                if isinstance(data, list):
                    print(f"List length: {len(data)}")
                else:
                    print(f"Dict length: {len(data)}")
            except Exception as e:
                print(f"JSON load error: {e}")
        else:
            print(f"--- {provider} Not Found ---")
