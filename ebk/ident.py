import hashlib
import re
from typing import List, Dict
import uuid

def canonicalize_text(text: str) -> str:
    """
    Canonicalize text by converting to lowercase, removing punctuation,
    stripping whitespace, and replacing spaces with underscores.
    """
    text = text.lower()
    # Remove punctuation using regex
    text = re.sub(r'[^\w\s]', '', text)
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading and trailing whitespace
    text = text.strip()
    # Replace spaces with underscores
    text = text.replace(' ', '_')
    return text

def canonicalize_creators(creators: List[str]) -> str:
    """
    Canonicalize a list of creators (authors) by sorting them,
    canonicalizing each name, and joining with underscores.
    """
    # Sort creators alphabetically for consistency
    sorted_creators = sorted(creators)
    canonical_creators = [canonicalize_text(creator) for creator in sorted_creators]
    # Join multiple creators with underscores
    return '_'.join(canonical_creators)

def generate_composite_string(entry: Dict) -> str:
    """
    Generate a composite string by concatenating canonicalized values
    of ISBN, date, language, publisher, creators, and title.
    
    The order is important for consistency.
    """
    identifiers = entry.get('identifiers', {})
    #isbn = identifiers.get('ISBN', '').strip()
    #date = entry.get('date', '').strip()
    language = entry.get('language', '').strip()
    #publisher = entry.get('publisher', '').strip()
    creators = entry.get('creators', [])
    title = entry.get('title', '').strip()
    
    # Canonicalize each field
    #isbn_c = canonicalize_text(isbn) if isbn else 'no_isbn'
    #date_c = canonicalize_text(date) if date else 'no_date'
    language_c = canonicalize_text(language) if language else 'no_language'
    #publisher_c = canonicalize_text(publisher) if publisher else 'no_publisher'
    creators_c = canonicalize_creators(creators) if creators else 'no_creators'
    title_c = canonicalize_text(title) if title else 'no_title'

    if language_c == 'no_language' and creators_c == 'no_creators' and title_c == 'no_title':
        return None
    
    # Concatenate fields with double underscores as delimiters
    composite_string = f"{language_c}__{creators_c}__{title_c}"
    return composite_string

def generate_hash_id(entry: Dict) -> str:
    """
    Generate a unique hash ID for an eBook entry by hashing the composite string.
    
    Args:
        entry (Dict): The eBook entry metadata.
    
    Returns:
        str: The SHA-256 hash hexadecimal string.
    """
    composite_string = generate_composite_string(entry)
    if composite_string:
        composite_bytes = composite_string.encode('utf-8')
    else:
        composite_bytes = str(uuid.uuid4()).encode('utf-8')

    # Create SHA-256 hash
    hash_obj = hashlib.sha256(composite_bytes)
    hash_hex = hash_obj.hexdigest()
    return hash_hex

def add_unique_id(entry: Dict) -> Dict:
    """
    Add a unique hash ID to the eBook entry.
    
    Args:
        entry (Dict): The original eBook entry metadata.
    
    Returns:
        Dict: The eBook entry with an added 'unique_id' field.
    """
    unique_id = generate_hash_id(entry)
    entry['unique_id'] = unique_id
    return entry
