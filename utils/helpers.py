"""
Helper utility functions.
"""

from datetime import datetime, timedelta
from typing import Optional


def format_duration(minutes: int) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        minutes: Duration in minutes
        
    Returns:
        Formatted string (e.g., "1h 30m", "45m")
    """
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    mins = minutes % 60
    
    if mins == 0:
        return f"{hours}h"
    
    return f"{hours}h {mins}m"


def parse_time(time_str: str) -> Optional[datetime]:
    """
    Parse time string to datetime.
    
    Args:
        time_str: Time string in various formats
        
    Returns:
        datetime object or None if parsing fails
    """
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%d'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    return None


def calculate_percentage(value: float, total: float) -> float:
    """
    Calculate percentage safely.
    
    Args:
        value: Current value
        total: Total value
        
    Returns:
        Percentage (0-100)
    """
    if total == 0:
        return 0.0
    
    return (value / total) * 100


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text with ellipsis.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."
