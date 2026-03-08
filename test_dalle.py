import os
from openai import OpenAI

client = OpenAI()
models = client.models.list()
filtered = [m.id for m in models if "dal" in m.id.lower()]
print("Found DALL-E models:", filtered)
