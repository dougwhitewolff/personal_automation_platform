#!/usr/bin/env python3
"""
Test OpenAI Response Debug

This mimics what your bot is doing when it processes a nutrition log.
Run this to see exactly what OpenAI returns.
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env
from openai import OpenAI

print("=" * 70)
print("  OpenAI Response Diagnostic")
print("=" * 70)
print()

# Get API key
api_key = get_env('OPENAI_API_KEY')
if not api_key:
    print("❌ No API key found")
    sys.exit(1)

masked = f"{api_key[:12]}...{api_key[-6:]}"
print(f"Using API key: {masked}")
print()

# Create client
client = OpenAI(api_key=api_key)

# This is the actual transcript from your terminal output
transcript = """So far today, I've eaten a large portion of smoothie and I've taken my morning supplements including D3, K2, fish oil, 5 milligrams of creatine.

I've also had two cups of hyacinth tea and one cup of coffee.

Log that."""

print("Testing with your actual transcript:")
print("-" * 70)
print(transcript)
print("-" * 70)
print()

# Build the prompt (similar to what nutrition module does)
prompt = f"""Extract relevant information for the nutrition module from this transcript.

TRANSCRIPT:
{transcript}

Respond with ONLY valid JSON. Do not include markdown code blocks or any text outside the JSON."""

print("Making API call to gpt-5-nano...")
print()

try:
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {
                "role": "system",
                "content": "You are a precise data extraction assistant. Always respond with valid JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        # IMPORTANT: correct parameter name
        max_completion_tokens=9000
    )

    print("✅ API call succeeded!")
    print()
    print(f"Model used: {response.model}")
    print(f"Finish reason: {response.choices[0].finish_reason}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print()

    # Check content
    content = response.choices[0].message.content

    if content is None:
        print("❌ ERROR: Content is None!")
        print()
        print("Possible causes: content filtering, model internal error, or token limits.")
    elif not content.strip():
        print("❌ ERROR: Content is empty string!")
    else:
        print("✅ Got content!")
        print()
        print("Raw response:")
        print("=" * 70)
        print(content)
        print("=" * 70)
        print()
        print(f"Length: {len(content)} characters")

        # Try to parse as JSON
        import json
        try:
            cleaned = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)
            print()
            print("✅ Valid JSON!")
            print()
            print("Parsed data:")
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError as e:
            print()
            print(f"❌ JSON parse failed: {e}")
            print()
            print("This means OpenAI returned text but not valid JSON.")

except Exception as e:
    print(f"❌ API call failed: {e}")
    print()
    print(f"Error type: {type(e).__name__}")

    import traceback
    traceback.print_exc()
