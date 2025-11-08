# core/env_loader.py
"""
Environment variable loader with .env file precedence.

- Loads .env from the project root derived from this file's location.
- ENV_FILE can override the path to the .env file.
- .env values override OS environment values (override=True).
"""
import os
from pathlib import Path
from typing import List, Tuple, Optional
from dotenv import load_dotenv

# Determine project root from this file path: <root>/core/env_loader.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ENV_PATH = _PROJECT_ROOT / ".env"

def _load_env() -> None:
    """
    Load .env with precedence over OS environment variables.
    If ENV_FILE is set, it takes priority. If the resolved file doesn't
    exist, python-dotenv will still look in the current working directory.
    """
    candidate = Path(os.getenv("ENV_FILE", str(_DEFAULT_ENV_PATH)))
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=True)
    else:
        # Fall back to default search; still override any cached values.
        load_dotenv(override=True)

# Load immediately at import time
_load_env()

def get_env(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """Return the environment variable or default if not present."""
    return os.getenv(var_name, default)

def get_env_required(var_name: str) -> str:
    """Return the environment variable or raise a clear error."""
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"Missing required environment variable: {var_name}")
    return value

def validate_required_vars(var_names: List[str]) -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are present.

    Returns:
        (all_present, missing_list)
    """
    missing = [name for name in var_names if not os.getenv(name)]
    return (len(missing) == 0, missing)
