import os
from dotenv import load_dotenv
load_dotenv()
from services.ai_service import get_openai_client

client = get_openai_client()
if client:
    print("OpenAI client initialized successfully")
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True
        )
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end='')
        print()
    except Exception as e:
        print("Error during generation:", e)
else:
    print("OpenAI client failed to initialize")
