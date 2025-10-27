"""Find command implementation for REPL shell."""

from typing import List, Dict, Any, Optional
from ebk.library_db import Library
from ebk.db.models import Book


class FindQuery:
    """Book finder with metadata filters."""

    def __init__(self, library: Library):
        """Initialize find query.

        Args:
            library: Library instance
        """
        self.library = library

    def find(self, filters: Dict[str, Any]) -> List[Book]:
        """Find books matching filters.

        Args:
            filters: Dictionary of field:value filters
                Supported fields:
                - title: Book title (partial match)
                - author: Author name (partial match)
                - subject: Subject/tag (partial match)
                - text: Full-text search (FTS5 across title, description, extracted text)
                - language: Language code (exact match)
                - year: Publication year (exact match)
                - publisher: Publisher name (partial match)
                - format: File format (exact match, e.g., pdf, epub)
                - limit: Maximum results (default: 50)

        Returns:
            List of matching books
        """
        query = self.library.query()

        # Apply filters
        if "title" in filters:
            query = query.filter_by_title(filters["title"])

        if "author" in filters:
            query = query.filter_by_author(filters["author"])

        if "subject" in filters:
            query = query.filter_by_subject(filters["subject"])

        if "language" in filters:
            query = query.filter_by_language(filters["language"])

        if "year" in filters:
            try:
                year = int(filters["year"])
                query = query.filter_by_year(year)
            except ValueError:
                pass  # Skip invalid year

        if "publisher" in filters:
            query = query.filter_by_publisher(filters["publisher"])

        if "format" in filters:
            query = query.filter_by_format(filters["format"])

        if "text" in filters:
            query = query.filter_by_text(filters["text"])

        # Apply limit
        limit = filters.get("limit", 50)
        try:
            # Convert to int if it's a string
            if isinstance(limit, str):
                limit = int(limit)
            if isinstance(limit, int):
                query = query.limit(limit)
        except (ValueError, TypeError):
            # Invalid limit, use default
            query = query.limit(50)

        # Execute query
        return query.all()

    def parse_filters(self, args: List[str]) -> Dict[str, Any]:
        """Parse command-line arguments into filter dictionary.

        Args:
            args: List of filter arguments in format "field:value"

        Returns:
            Dictionary of filters

        Raises:
            ValueError: If argument format is invalid
        """
        filters = {}

        for arg in args:
            if ":" not in arg:
                raise ValueError(f"Invalid filter format: {arg}. Use field:value")

            field, value = arg.split(":", 1)
            field = field.lower().strip()
            value = value.strip()

            # Validate field
            valid_fields = {
                "title",
                "author",
                "subject",
                "text",
                "language",
                "year",
                "publisher",
                "format",
                "limit",
            }

            if field not in valid_fields:
                raise ValueError(
                    f"Unknown field: {field}. Valid fields: {', '.join(sorted(valid_fields))}"
                )

            filters[field] = value

        return filters
