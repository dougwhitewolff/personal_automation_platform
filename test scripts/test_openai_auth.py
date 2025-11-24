#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI API Authentication Diagnostic

Tests the exact authentication flow used by your platform.
"""
import sys
import os

# Add project root to path to import core modules
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env

print("="*70)
print("  OpenAI API Authentication Diagnostic")
print("="*70)
print()

# Step 1: Check environment variable
print("Step 1: Environment Variable Check")
print("-" * 70)

api_key = get_env('OPENAI_API_KEY')

if not api_key:
    print("ERROR: OPENAI_API_KEY not found in environment")
    print()
    print("Troubleshooting:")
    print("1. Check if .env file exists in project root")
    print("2. Verify .env contains: OPENAI_API_KEY=sk-proj-...")
    print("3. Ensure no quotes around the key value")
    print("4. Restart terminal/IDE after editing .env")
    sys.exit(1)

# Mask for security
if len(api_key) > 20:
    masked = f"{api_key[:10]}...{api_key[-6:]}"
else:
    masked = f"{api_key[:4]}...{api_key[-2:]}"

print(f"SUCCESS: API key found in environment")
print(f"   Masked value: {masked}")
print(f"   Length: {len(api_key)} characters")
print(f"   Prefix: {api_key[:7]}")

if not api_key.startswith('sk-'):
    print("WARNING: API key doesn't start with 'sk-'")
    print("   OpenAI keys typically start with 'sk-proj-' or 'sk-'")
    print()

print()

# Step 2: Test OpenAI client initialization
print("Step 2: Client Initialization")
print("-" * 70)

try:
    from openai import OpenAI
    print("SUCCESS: OpenAI library imported successfully")
except ImportError as e:
    print(f"ERROR: Failed to import OpenAI library: {e}")
    print("   Run: pip install openai --upgrade")
    sys.exit(1)

try:
    client = OpenAI(api_key=api_key)
    print("SUCCESS: OpenAI client initialized")
except Exception as e:
    print(f"ERROR: Client initialization failed: {e}")
    sys.exit(1)

print()

# Step 3: Test actual API call (mimicking your platform's usage)
print("Step 3: API Authentication Test")
print("-" * 70)
print("Testing with GPT-5 Nano (as used in your platform)...")
print()

try:
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[
            {"role": "system", "content": "You are a test assistant."},
            {"role": "user", "content": "Reply with only the word 'SUCCESS'"},
        ],
        # IMPORTANT: correct parameter name
        max_completion_tokens=1000,
    )

    result = (response.choices[0].message.content or "").strip()
    print("SUCCESS: API CALL SUCCESSFUL!")
    print(f"   Model: gpt-5-nano")
    print(f"   Response: '{result}'")
    print(f"   Tokens used: {response.usage.total_tokens}")
    print()
    print("="*70)
    print("  SUCCESS: AUTHENTICATION WORKING - Your API key is valid!")
    print("="*70)
    print()
    print("Next steps:")
    print("1. The OpenAI integration should work in your platform")
    print("2. If still seeing 401 errors, the issue is elsewhere")
    print("3. Check that modules are calling openai_client correctly")

except Exception as e:
    error_str = str(e)
    print(f"ERROR: API CALL FAILED")
    print(f"   Error: {error_str}")
    sys.exit(1)

print()
print("Diagnostic complete!")
