# -*- coding: utf-8 -*-
"""
Minimal test script to debug Limitless API issues.
Tests progressively simpler requests to identify the problem.
"""

import requests
import sys
import os
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env

API_KEY = get_env('LIMITLESS_API_KEY')
BASE_URL = "https://api.limitless.ai/v1"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

print("="*60)
print("LIMITLESS API DIAGNOSTIC TEST")
print("="*60)
print()

# Test 1: Absolute simplest request (no filters)
print("TEST 1: Simplest possible request (no date filters)")
print("-"*60)
params1 = {
    "limit": 3
}
print(f"URL: {BASE_URL}/lifelogs")
print(f"Params: {params1}")
print(f"Headers: X-API-Key: {API_KEY[:10]}...{API_KEY[-10:]}")
print()

response1 = requests.get(f"{BASE_URL}/lifelogs", params=params1, headers=headers, timeout=15)
print(f"Status: {response1.status_code}")
print(f"Response: {response1.text[:500]}")
print()

if response1.status_code != 200:
    print("ERROR: Even the simplest request failed!")
    print("   Possible issues:")
    print("   1. Invalid API key")
    print("   2. API key doesn't have proper permissions")
    print("   3. Limitless API is having issues")
    print()
else:
    print("SUCCESS: Basic request worked!")
    print()

# Test 2: Add just date parameter
print("TEST 2: Date-only request")
print("-"*60)
params2 = {
    "date": "2025-11-05",
    "limit": 3
}
print(f"Params: {params2}")
response2 = requests.get(f"{BASE_URL}/lifelogs", params=params2, headers=headers, timeout=15)
print(f"Status: {response2.status_code}")
print(f"Response: {response2.text[:500]}")
print()

# Test 3: Add timezone
print("TEST 3: Date + timezone")
print("-"*60)
params3 = {
    "date": "2025-11-05",
    "timezone": "America/Los_Angeles",
    "limit": 3
}
print(f"Params: {params3}")
response3 = requests.get(f"{BASE_URL}/lifelogs", params=params3, headers=headers, timeout=15)
print(f"Status: {response3.status_code}")
print(f"Response: {response3.text[:500]}")
print()

# Test 4: Add includeMarkdown
print("TEST 4: Date + timezone + includeMarkdown")
print("-"*60)
params4 = {
    "date": "2025-11-05",
    "timezone": "America/Los_Angeles",
    "includeMarkdown": True,
    "limit": 3
}
print(f"Params: {params4}")
response4 = requests.get(f"{BASE_URL}/lifelogs", params=params4, headers=headers, timeout=15)
print(f"Status: {response4.status_code}")
print(f"Response: {response4.text[:500]}")
print()

# Test 5: Try start/end format
print("TEST 5: Using start/end instead of date")
print("-"*60)
params5 = {
    "start": "2025-11-05 00:00:00",
    "end": "2025-11-05 23:59:59",
    "timezone": "America/Los_Angeles",
    "limit": 3
}
print(f"Params: {params5}")
response5 = requests.get(f"{BASE_URL}/lifelogs", params=params5, headers=headers, timeout=15)
print(f"Status: {response5.status_code}")
print(f"Response: {response5.text[:500]}")
print()

# Test 6: Try with just date string (YYYY-MM-DD format for start/end)
print("TEST 6: Using YYYY-MM-DD format for start/end")
print("-"*60)
params6 = {
    "start": "2025-11-05",
    "end": "2025-11-05",
    "timezone": "America/Los_Angeles",
    "limit": 3
}
print(f"Params: {params6}")
response6 = requests.get(f"{BASE_URL}/lifelogs", params=params6, headers=headers, timeout=15)
print(f"Status: {response6.status_code}")
print(f"Response: {response6.text[:500]}")
print()

# Summary
print("="*60)
print("SUMMARY")
print("="*60)
print(f"Test 1 (no filters): {response1.status_code}")
print(f"Test 2 (date only): {response2.status_code}")
print(f"Test 3 (date + timezone): {response3.status_code}")
print(f"Test 4 (+ includeMarkdown): {response4.status_code}")
print(f"Test 5 (start/end with time): {response5.status_code}")
print(f"Test 6 (start/end date only): {response6.status_code}")
print()

if all(r.status_code == 400 for r in [response1, response2, response3, response4, response5, response6]):
    print("ERROR: ALL TESTS FAILED - This suggests:")
    print("   - API key is invalid or expired")
    print("   - API key lacks permissions")
    print("   - Account issue")
    print()
    print("   Next steps:")
    print("   1. Go to https://limitless.ai")
    print("   2. Settings -> Developer")
    print("   3. Create a NEW API key")
    print("   4. Replace LIMITLESS_API_KEY in .env")
elif response1.status_code == 200:
    print("SUCCESS: API key works! Issue is with specific parameters.")
    print()
    if response3.status_code != 200:
        print("   Problem: date + timezone combination is being rejected")
    if response4.status_code != 200:
        print("   Problem: includeMarkdown parameter")