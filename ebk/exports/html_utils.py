"""HTML sanitization utilities for secure template rendering."""

import json
import html
from typing import Any, Dict, List
import re


def sanitize_for_html(text: str) -> str:
    """
    Sanitize text for safe HTML output.
    
    Escapes HTML special characters to prevent XSS attacks.
    """
    if not text:
        return ""
    return html.escape(str(text))


def sanitize_for_javascript(obj: Any) -> str:
    """
    Safely encode data for embedding in JavaScript.
    
    This prevents XSS attacks when embedding data in script tags.
    """
    # Convert to JSON with proper escaping
    json_str = json.dumps(obj, ensure_ascii=False)
    
    # Additional escaping for script context
    # Replace </script> to prevent breaking out of script tags
    json_str = json_str.replace('</script>', '<\\/script>')
    json_str = json_str.replace('<!--', '<\\!--')
    json_str = json_str.replace('-->', '--\\>')
    
    return json_str


def sanitize_metadata(entry: Dict) -> Dict:
    """
    Sanitize metadata fields that will be displayed in HTML.
    
    Preserves structure but escapes string values.
    """
    sanitized = {}
    
    for key, value in entry.items():
        if isinstance(value, str):
            # Don't sanitize file paths and IDs (they're not displayed as HTML)
            if key in ('file_paths', 'cover_path', 'unique_id', '_entry_id'):
                sanitized[key] = value
            else:
                sanitized[key] = sanitize_for_html(value)
        elif isinstance(value, list):
            # Sanitize list items if they're strings
            sanitized[key] = [
                sanitize_for_html(item) if isinstance(item, str) else item 
                for item in value
            ]
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = sanitize_metadata(value)
        else:
            sanitized[key] = value
    
    return sanitized


def sanitize_entries_for_javascript(entries: List[Dict]) -> str:
    """
    Prepare entries for safe embedding in JavaScript.
    
    This sanitizes user content while preserving the data structure.
    """
    # Create a sanitized copy of entries
    sanitized_entries = []
    
    for entry in entries:
        # Create a minimal, safe version for JavaScript
        safe_entry = {
            'unique_id': entry.get('unique_id', ''),
            'title': sanitize_for_html(entry.get('title', '')),
            'creators': [sanitize_for_html(c) for c in entry.get('creators', [])],
            'subjects': [sanitize_for_html(s) for s in entry.get('subjects', [])],
            'language': sanitize_for_html(entry.get('language', '')),
            'date': sanitize_for_html(str(entry.get('date', ''))),
            'publisher': sanitize_for_html(str(entry.get('publisher', ''))),
            'description': sanitize_for_html(entry.get('description', '')),
            'cover_path': entry.get('cover_path', ''),
            'file_paths': entry.get('file_paths', []),
            '_readable_name': sanitize_for_html(entry.get('_readable_name', '')),
            '_entry_id': entry.get('_entry_id', '')
        }
        sanitized_entries.append(safe_entry)
    
    return sanitize_for_javascript(sanitized_entries)


def create_safe_filename(text: str, max_length: int = 255) -> str:
    """
    Create a safe filename from text.
    
    Removes/replaces characters that could cause issues in filenames.
    """
    # Remove HTML tags if any
    text = re.sub(r'<[^>]+>', '', text)
    
    # Replace unsafe characters
    safe_chars = re.sub(r'[<>:"/\\|?*]', '_', text)
    
    # Remove control characters
    safe_chars = ''.join(char for char in safe_chars if ord(char) >= 32)
    
    # Truncate if too long
    if len(safe_chars) > max_length:
        safe_chars = safe_chars[:max_length-3] + '...'
    
    return safe_chars.strip()