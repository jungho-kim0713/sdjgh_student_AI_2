"""Direct test of Anthropic client without importing ai_service"""
import os
from dotenv import load_dotenv
import anthropic

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

if not api_key:
    print("❌ ANTHROPIC_API_KEY not found")
    exit(1)

print(f"✅ API Key found: {api_key[:5]}...{api_key[-5:]}")

try:
    # Create client directly without httpx parameter
    client = anthropic.Anthropic(api_key=api_key)

    print(f"✅ Client type: {type(client)}")
    print(f"✅ Has models attribute: {hasattr(client, 'models')}")

    if hasattr(client, 'models'):
        print("\n🧪 Testing models.list()...")
        models_page = client.models.list()

        print("\n📋 Found models:")
        count = 0
        for model in models_page:
            print(f"   - {model.id}")
            count += 1

        print(f"\n✅ Total: {count} models")
    else:
        print(f"❌ No models attribute. Available: {dir(client)[:10]}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
