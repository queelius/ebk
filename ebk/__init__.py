"""
ebk - A lightweight tool for managing eBook metadata.

Main API (Database-backed):
    from ebk import Library

    # Open or create a library (database-backed)
    lib = Library.open("/path/to/library")

    # Add books
    lib.add_book(file_path, metadata_dict)
    lib.add_calibre_book(metadata_opf_path)

    # Search with full-text search
    results = lib.search("Python programming")

    # Query with filters
    books = lib.query().filter_by_author("Knuth").filter_by_language("en").all()

    # Get statistics
    stats = lib.stats()

    # Close when done
    lib.close()
"""

from .library_db import Library
from .db import Book, Author, Subject, File

__version__ = "0.3.0"
__all__ = ["Library", "Book", "Author", "Subject", "File"]