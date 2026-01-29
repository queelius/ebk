"""
Metadata extraction integrations for EBK.

This integration provides metadata extraction from various sources:
- Google Books API
- Open Library API (free, no API key required)
- CrossRef API (future)
- Library of Congress (future)

Installation:
    pip install ebk[metadata]  # Installs all metadata extractors
    pip install ebk[google-books]  # Just Google Books
"""

from .google_books import GoogleBooksExtractor, GoogleBooksExtractorSync
from .open_library import OpenLibraryExtractor, OpenLibraryExtractorSync

__all__ = [
    'GoogleBooksExtractor',
    'GoogleBooksExtractorSync',
    'OpenLibraryExtractor',
    'OpenLibraryExtractorSync',
]