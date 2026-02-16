"""Test if anthropic_client has models attribute"""
import sys
sys.path.insert(0, '/app')

from services.ai_service import anthropic_client

if anthropic_client is None:
    print("❌ anthropic_client is None - API key not set")
    exit(1)

print(f"✅ anthropic_client type: {type(anthropic_client)}")
print(f"✅ anthropic_client has 'models' attribute: {hasattr(anthropic_client, 'models')}")

if hasattr(anthropic_client, 'models'):
    try:
        print("\n🧪 Testing models.list()...")
        models_page = anthropic_client.models.list()

        print(f"\n📋 Found models:")
        count = 0
        for model in models_page:
            print(f"   - {model.id}")
            count += 1

        print(f"\n✅ Total: {count} models")
    except Exception as e:
        print(f"❌ Error calling models.list(): {e}")
else:
    print("❌ anthropic_client does NOT have 'models' attribute")
    print(f"Available attributes: {dir(anthropic_client)}")
