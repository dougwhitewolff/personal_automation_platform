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
    Extract all chunks containing 'log that' commands with context.
    
    Finds ALL occurrences of 'log that' (case-insensitive) in the markdown.
    For each occurrence, extracts up to max_sentences sentences before it,
    includes the 'log that' keyword, and merges overlapping chunks.
    
    Args:
        markdown: The full markdown content from a lifelog
        max_sentences: Maximum number of sentences to extract before each 'log that' (default: 5)
        
    Returns:
        Combined string of all chunks (5 sentences before + 'log that' keyword for each occurrence),
        or empty string if no 'log that' is found.
    """
    if not markdown or not markdown.strip():
        return ""
    
    # Find all occurrences of 'log that' (case-insensitive)
    # Use word boundaries to avoid matching within other words
    pattern = r'\b(log\s+that)\b'
    matches = list(re.finditer(pattern, markdown, re.IGNORECASE))
    
    if not matches:
        # No 'log that' found, return empty string
        return ""
    
    # Split markdown into sentences
    # Pattern: sentence ending (. ! ?) followed by space and capital letter, or end of string
    sentence_pattern = r'([.!?]+)\s+(?=[A-Z])|([.!?]+)\s*$'
    
    # Find all sentence boundaries in the markdown
    sentence_boundaries = []
    last_end = 0
    
    for sent_match in re.finditer(sentence_pattern, markdown):
        sentence_end = sent_match.end()
        sentence_boundaries.append((last_end, sentence_end))
        last_end = sentence_end
    
    # Add the remaining text as the last sentence if any
    if last_end < len(markdown):
        sentence_boundaries.append((last_end, len(markdown)))
    
    # If no sentence boundaries found, treat entire text as one sentence
    if not sentence_boundaries:
        sentence_boundaries = [(0, len(markdown))]
    
    # Map each "log that" match to its containing sentence index
    log_that_sentence_indices = []
    for match in matches:
        match_pos = match.start()
        # Find which sentence contains this match
        for i, (start, end) in enumerate(sentence_boundaries):
            if start <= match_pos < end:
                log_that_sentence_indices.append(i)
                break
        else:
            # If not found in any sentence (shouldn't happen), add last sentence
            log_that_sentence_indices.append(len(sentence_boundaries) - 1)
    
    # Build ranges: for each "log that", get max_sentences sentences before it
    ranges = []
    for sentence_idx in log_that_sentence_indices:
        start_sentence = max(0, sentence_idx - max_sentences)
        end_sentence = sentence_idx  # Include the sentence with "log that"
        ranges.append((start_sentence, end_sentence))
    
    # Merge ranges where "log that" commands are within max_sentences of each other
    if not ranges:
        return ""
    
    # Create a list of (sentence_idx, range) pairs to track which "log that" each range belongs to
    range_with_indices = list(zip(log_that_sentence_indices, ranges))
    # Sort by the sentence index of the "log that"
    range_with_indices.sort(key=lambda x: x[0])
    
    merged_ranges = []
    if not range_with_indices:
        return ""
    
    current_idx, (current_start, current_end) = range_with_indices[0]
    
    for sentence_idx, (start, end) in range_with_indices[1:]:
        # Check if this "log that" is within max_sentences of the current one
        distance = sentence_idx - current_idx
        if distance <= max_sentences:
            # Merge: extend current range to include this one
            # The merged range should go from 5 before the first to 5 before the second (or end of second)
            current_start = min(current_start, start)
            current_end = max(current_end, end)
            # Update current_idx to the later one for next comparison
            current_idx = sentence_idx
        else:
            # Too far apart, save current range and start new one
            merged_ranges.append((current_start, current_end))
            current_idx, current_start, current_end = sentence_idx, start, end
    
    # Add the last range
    merged_ranges.append((current_start, current_end))
    
    # Extract text for each merged range
    chunks = []
    for start_sent, end_sent in merged_ranges:
        # Get the character positions for this sentence range
        if start_sent >= len(sentence_boundaries):
            continue
        
        range_start = sentence_boundaries[start_sent][0]
        range_end = sentence_boundaries[min(end_sent, len(sentence_boundaries) - 1)][1]
        
        # Ensure we include any "log that" keywords that might be at the boundary
        # Find all "log that" matches that should be in this range
        for match in matches:
            match_start = match.start()
            match_end = match.end()
            # If match starts before range_end, extend range to include it
            if match_start < range_end and match_end > range_start:
                range_start = min(range_start, match_start)
                range_end = max(range_end, match_end)
        
        # Extract the text for this range
        chunk_text = markdown[range_start:range_end].strip()
        
        if chunk_text:
            chunks.append(chunk_text)
    
    # Combine all chunks into a single string
    if not chunks:
        return ""
    
    # Join chunks with double newlines to separate them
    result = "\n\n".join(chunks).strip()
    
    return result
