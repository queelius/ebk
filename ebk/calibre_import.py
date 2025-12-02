"""
Calibre library import functionality.

Provides functions to import books from a Calibre library into an ebk library.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def import_calibre_library(
    calibre_path: Path,
    library,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Import books from a Calibre library.

    Args:
        calibre_path: Path to the Calibre library folder
        library: An open ebk Library instance
        limit: Maximum number of books to import

    Returns:
        Dictionary with import results:
        - total: Number of books found
        - imported: Number of books successfully imported
        - failed: Number of books that failed to import
        - errors: List of error messages
    """
    results = {
        "total": 0,
        "imported": 0,
        "failed": 0,
        "errors": []
    }

    # Find all metadata.opf files
    opf_files = list(calibre_path.rglob("metadata.opf"))

    if limit:
        opf_files = opf_files[:limit]

    results["total"] = len(opf_files)

    if len(opf_files) == 0:
        results["errors"].append("No books found. Make sure this is a Calibre library directory.")
        return results

    for opf_path in opf_files:
        try:
            book = library.add_calibre_book(opf_path)
            if book:
                results["imported"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed to import: {opf_path.parent.name}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{opf_path.parent.name}: {str(e)}")
            logger.debug(f"Failed to import {opf_path.parent.name}: {e}")

    return results
