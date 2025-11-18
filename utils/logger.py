"""
Logging utility for the Personal Automation Platform.

Provides a centralized logging configuration with consistent formatting.
"""

import logging
import sys
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str = "automation_platform",
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up and configure a logger with consistent formatting.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter
    if format_string is None:
        format_string = (
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        )
    
    formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger


# Global logger instance
_logger: Optional[logging.Logger] = None


def get_logger(name: str = "automation_platform") -> logging.Logger:
    """
    Get or create the global logger instance.
    
    Args:
        name: Logger name (default: "automation_platform")
        
    Returns:
        Logger instance
    """
    global _logger
    if _logger is None:
        _logger = setup_logger(name)
    return _logger

