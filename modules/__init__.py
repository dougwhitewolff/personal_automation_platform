"""
Pluggable automation modules.

Each module is self-contained and handles:
- Keyword detection
- Data logging
- Question answering
- Image processing
- Scheduled tasks
"""

from .base import BaseModule
from .registry import ModuleRegistry

__all__ = ["BaseModule", "ModuleRegistry"]
