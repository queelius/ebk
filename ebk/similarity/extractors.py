"""Concrete extractor implementations."""

from typing import Optional, Set

from ebk.db.models import Book
from ebk.similarity.base import Extractor


class ContentExtractor(Extractor[str]):
    """Extracts full text content from a book.

    Uses extracted_text from primary file if available, otherwise combines
    title and description.
    """

    def extract(self, book: Book) -> str:
        """Extract text content from book.

        Args:
            book: Book to extract from

        Returns:
            Full text content as string
        """
        # Try to get extracted text from primary file
        if book.files:
            for file in book.files:
                if file.extracted_text and file.extracted_text.full_text:
                    return file.extracted_text.full_text

        # Fallback to title + description
        parts = []
        if book.title:
            parts.append(book.title)
        if book.description:
            parts.append(book.description)

        return " ".join(parts)


class AuthorsExtractor(Extractor[Set[str]]):
    """Extracts set of author names from a book."""

    def extract(self, book: Book) -> Set[str]:
        """Extract author names from book.

        Args:
            book: Book to extract from

        Returns:
            Set of author names (normalized to lowercase)
        """
        if not book.authors:
            return set()

        return {author.name.lower() for author in book.authors}


class SubjectsExtractor(Extractor[Set[str]]):
    """Extracts set of subjects/tags from a book."""

    def extract(self, book: Book) -> Set[str]:
        """Extract subjects from book.

        Args:
            book: Book to extract from

        Returns:
            Set of subject names (normalized to lowercase)
        """
        if not book.subjects:
            return set()

        return {subject.name.lower() for subject in book.subjects}


class PublicationYearExtractor(Extractor[Optional[int]]):
    """Extracts publication year from a book."""

    def extract(self, book: Book) -> Optional[int]:
        """Extract publication year from book.

        Args:
            book: Book to extract from

        Returns:
            Publication year as int, or None if not available
        """
        if not book.publication_date:
            return None

        # Handle various date formats
        date_str = str(book.publication_date)

        # Try to extract year
        if len(date_str) >= 4:
            try:
                return int(date_str[:4])
            except ValueError:
                return None

        return None


class LanguageExtractor(Extractor[Optional[str]]):
    """Extracts language code from a book."""

    def extract(self, book: Book) -> Optional[str]:
        """Extract language from book.

        Args:
            book: Book to extract from

        Returns:
            Language code (normalized to lowercase), or None
        """
        if not book.language:
            return None

        return book.language.lower()


class PublisherExtractor(Extractor[Optional[str]]):
    """Extracts publisher name from a book."""

    def extract(self, book: Book) -> Optional[str]:
        """Extract publisher from book.

        Args:
            book: Book to extract from

        Returns:
            Publisher name (normalized to lowercase), or None
        """
        if not book.publisher:
            return None

        return book.publisher.lower()


class PageCountExtractor(Extractor[Optional[int]]):
    """Extracts page count from a book."""

    def extract(self, book: Book) -> Optional[int]:
        """Extract page count from book.

        Args:
            book: Book to extract from

        Returns:
            Page count, or None if not available
        """
        return book.page_count


class DescriptionExtractor(Extractor[str]):
    """Extracts description/summary from a book."""

    def extract(self, book: Book) -> str:
        """Extract description from book.

        Args:
            book: Book to extract from

        Returns:
            Description text (empty string if not available)
        """
        return book.description or ""
