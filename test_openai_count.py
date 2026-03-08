import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

models_list = client.models.list()
api_models = [m.id for m in models_list if m.id.startswith("gpt") or m.id.startswith("o1") or m.id.startswith("o3") or "dall-e" in m.id]

print(f"Total matching: {len(api_models)}")

# Filter out old snapshots
filtered = [
    m for m in api_models 
    if not (
        "-0301" in m or "-0613" in m or "-1106" in m or "0125" in m or "vision-preview" in m
        or "0314" in m or "0409" in m or "11-06" in m
    )
]

print(f"Filtered: {len(filtered)}")
for m in sorted(filtered):
    print(m)
