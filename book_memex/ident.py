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
    language = entry.get('language', '').strip()
    creators = entry.get('creators', [])
    title = entry.get('title', '').strip()

    # Canonicalize each field
    language_c = canonicalize_text(language) if language else 'no_language'
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


def normalize_isbn(isbn: str) -> str:
    """Strip formatting from an ISBN: drop hyphens/spaces, uppercase the X
    check digit. So "978-0-13-468599-1" and "9780134685991" canonicalize the
    same and do not split into two book records."""
    return re.sub(r"[^0-9Xx]", "", str(isbn)).upper()


def compute_unique_id(metadata: Dict) -> str:
    """The one canonical durable book id.

    Single source of truth for book unique_ids: import, reconciliation, and
    URI resolution all go through here. Format:

      - ``isbn_<normalized-isbn>`` when the metadata carries an ISBN
        (hyphens/spaces stripped so formatting variants do not split);
      - otherwise the first 16 hex chars of md5 over the canonical
        ``title:creators`` string.

    Known, inherent limitations (not generator bugs): a book imported once
    with an ISBN and once without still gets two ids (ISBN path vs hash
    path), and re-importing after a title/author correction mints a new id.
    Content-derived ids are durable by design; use
    ``book-memex check --identity`` to find rows whose stored id no longer
    matches this function.
    """
    identifiers = metadata.get("identifiers", {}) or {}
    isbn = identifiers.get("isbn")
    if isbn:
        norm = normalize_isbn(isbn)
        if norm:
            return f"isbn_{norm}"

    title = metadata.get("title", "unknown")
    authors = ",".join(metadata.get("creators", ["unknown"]))
    content = f"{title}:{authors}".lower()
    return hashlib.md5(content.encode()).hexdigest()[:16]
