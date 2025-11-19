"""
Helper utility functions.
"""

import re
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


def extract_context_before_log_that(markdown: str, max_sentences: int = 5) -> str:
    """
    Extract up to N sentences immediately preceding the first occurrence of 'log that'.
    
    From a single lifelog's markdown, returns up to max_sentences sentences
    immediately preceding the first occurrence of 'log that' (case-insensitive).
    This reduces the amount of text sent to the LLM.
    
    Args:
        markdown: The full markdown content from a lifelog
        max_sentences: Maximum number of sentences to extract (default: 5)
        
    Returns:
        Extracted context text (up to max_sentences sentences before 'log that'),
        or the original markdown if 'log that' is not found.
    """
    if not markdown or not markdown.strip():
        return markdown
    
    # Find the first occurrence of 'log that' (case-insensitive)
    # Use word boundaries to avoid matching within other words
    pattern = r'\b(log\s+that)\b'
    match = re.search(pattern, markdown, re.IGNORECASE)
    
    if not match:
        # 'log that' not found, return original markdown
        return markdown
    
    # Get text before 'log that'
    text_before = markdown[:match.start()].strip()
    
    if not text_before:
        # No text before 'log that', return empty string
        return ""
    
    # Split into sentences using common sentence delimiters
    # Pattern: sentence ending (. ! ?) followed by space or end of string
    # This pattern matches: period/exclamation/question mark, followed by whitespace and capital letter, or end of string
    sentence_pattern = r'([.!?]+)\s+(?=[A-Z])|([.!?]+)\s*$'
    
    # Find all sentence boundaries
    parts = []
    last_end = 0
    
    for sent_match in re.finditer(sentence_pattern, text_before):
        # Include the sentence delimiter
        sentence_end = sent_match.end()
        parts.append(text_before[last_end:sentence_end].strip())
        last_end = sentence_end
    
    # Add any remaining text after the last sentence delimiter
    if last_end < len(text_before):
        remaining = text_before[last_end:].strip()
        if remaining:
            parts.append(remaining)
    
    # If no sentence boundaries found, treat entire text as one sentence
    if not parts:
        parts = [text_before]
    
    # Filter out empty parts
    parts = [p for p in parts if p.strip()]
    
    # Take up to max_sentences sentences (from the end, as they're closest to 'log that')
    if len(parts) > max_sentences:
        parts = parts[-max_sentences:]
    
    # Join sentences back together with spaces
    result = ' '.join(parts).strip()
    
    return result if result else text_before
