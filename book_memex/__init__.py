"""
book-memex - A powerful eBook metadata management tool with SQLAlchemy + SQLite backend.

Renamed from ebk. The `ebk` CLI entrypoint is retained as a deprecation shim.

Main API:
    from book_memex.library_db import Library
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

# Read the installed-package version at runtime. This is robust to
# pytest configurations where a shadow package could hide the real one
# — importlib.metadata always consults dist-info.
try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("book-memex")
except Exception:
    __version__ = "unknown"

__all__ = ["Library"]