import re

def sort_score(m):
    m_id = str(m.get("id", "")).lower()
    score = 0
    
    # 1. Family priority (lower is top)
    if "o3" in m_id: score -= 110
    elif "o1" in m_id: score -= 100
    elif "gpt-4.5" in m_id: score -= 95
    elif "gpt-4o" in m_id: score -= 90
    elif "gpt-4-turbo" in m_id: score -= 80
    elif "gpt-4" in m_id: score -= 70
    elif "gpt-3.5" in m_id: score -= 50
    elif "gpt-5" in m_id: score -= 120 # Add GPT-5 logic!
    
    if "sonnet" in m_id: score -= 90
    elif "opus" in m_id: score -= 85
    elif "haiku" in m_id: score -= 75
    
    if "gemini-2.5" in m_id: score -= 90
    elif "gemini-1.5" in m_id: score -= 70
    elif "gemini-1.0" in m_id: score -= 50
    
    if "grok-4" in m_id: score -= 90
    elif "grok-3" in m_id: score -= 80
    elif "grok-2" in m_id: score -= 60
    elif "grok" in m_id: score -= 50
    
    # 2. Extract versions using regex to sort descending (negative float)
    nums = re.findall(r'\d+(?:\.\d+)?', m_id)
    num_score = 0
    if nums:
        try:
            num_score = -float(nums[0])
        except:
            pass
            
    # 3. Tie-breaker suffixes
    if "latest" in m_id: num_score -= 0.5
    if "preview" in m_id: num_score -= 0.2
    if "vision" in m_id: num_score += 0.1
    if "mini" in m_id or "flash" in m_id or "haiku" in m_id or "nano" in m_id: num_score += 0.2
    
    return (score, num_score, m_id)

test_models = [
    {"id": "gpt-4.1-mini"},
    {"id": "gpt-5.1"},
    {"id": "gpt-5.2"},
    {"id": "gpt-5"},
    {"id": "gpt-4o"},
    {"id": "grok-3"},
    {"id": "grok-4-0709"},
    {"id": "grok-4.1-fast"}
]

test_models.sort(key=sort_score)
for m in test_models:
    print(m["id"], "->", sort_score(m))
