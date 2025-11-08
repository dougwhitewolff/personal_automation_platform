# core/__init__.py
"""
Core infrastructure for the Personal Automation Platform.
"""

from .database import init_database
from .limitless_client import LimitlessClient
from .openai_client import OpenAIClient
from .scheduler import Scheduler

# Lazy import to avoid Discord dependency in tests
def get_setup_bot():
    from .discord_bot import setup_bot
    return setup_bot

__all__ = [
    "init_database",
    "LimitlessClient",
    "OpenAIClient",
    "get_setup_bot",
    "Scheduler",
]
