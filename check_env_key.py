import sys
import os
import reprlib

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env

val = get_env("OPENAI_API_KEY")

print("Raw repr:", reprlib.repr(val))
print("First/Last few chars:", val[:10], "...", val[-6:] if val else None)
print("Length:", len(val) if val else None)