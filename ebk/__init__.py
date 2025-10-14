"""
ebk - A powerful eBook metadata management tool with SQLAlchemy + SQLite backend.

Main API:
    from ebk.library_db import Library
    from pathlib import Path

    # Open or create a library
    lib = Library.open(Path("/path/to/library"))

    # Add a book
    book = lib.add_book(
        Path("book.pdf"),
        metadata={"title": "My Book", "creators": ["Author"]},
        extract_text=True
    )

    # Search with full-text search
    results = lib.search("python programming", limit=50)

    # Query with fluent API
    results = (lib.query()
        .filter_by_language("en")
        .filter_by_author("Knuth")
        .limit(20)
        .all())

    # Always close when done
    lib.close()
"""

from .library_db import Library

__version__ = "0.3.1"
__all__ = ["Library"]