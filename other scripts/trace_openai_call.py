from openai import OpenAI
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env

client = OpenAI(api_key=get_env("OPENAI_API_KEY"))

# monkey-patch to log outgoing requests
orig_request = client._client.request
def debug_request(*a, **kw):
    print("DEBUG OUTGOING REQUEST BODY:")
    print(kw.get("json", {}))
    return orig_request(*a, **kw)
client._client.request = debug_request

client.chat.completions.create(
    model="gpt-5-nano",
    messages=[
        {"role": "system", "content": "You are a test assistant."},
        {"role": "user", "content": "Reply with only the word SUCCESS"}
    ],
    # IMPORTANT: correct parameter name
    max_completion_tokens=1000
)
