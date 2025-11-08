"""
Core infrastructure for the Personal Automation Platform.

This package contains shared services used by all modules:
- Database management
- Limitless API client
- OpenAI client wrapper
- Discord bot (lazy import to avoid audioop issues on Python 3.13)
- Task scheduler
"""

from .database import init_database
from .limitless_client import LimitlessClient
from .openai_client import OpenAIClient
from .scheduler import Scheduler


def get_setup_bot():
    """
    Lazy import for Discord bot setup.
    Prevents importing discord.py (and its audioop dependency)
    unless the bot is explicitly started (main.py).
    """
    from .discord_bot import setup_bot
    return setup_bot


__all__ = [
    "init_database",
    "LimitlessClient",
    "OpenAIClient",
    "Scheduler",
    "get_setup_bot",
]
