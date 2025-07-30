"""
ebk - A lightweight tool for managing eBook metadata.

Main API:
    from ebk import Library
    
    # Create or open a library
    lib = Library.create("/path/to/library")
    lib = Library.open("/path/to/library")
    
    # Search and filter
    results = lib.search("Python")
    filtered = lib.filter(lambda e: e.get("year") > 2020)
    
    # Add and modify
    lib.add_entry(title="Book", creators=["Author"])
    lib.save()
"""

from .library import Library, Entry, QueryBuilder
from .manager import LibraryManager  # Keep for backward compatibility

__version__ = "0.3.0"
__all__ = ["Library", "Entry", "QueryBuilder", "LibraryManager"]