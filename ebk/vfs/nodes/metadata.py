"""Metadata file nodes for books."""

from typing import Optional, Dict, Any

from ebk.vfs.base import FileNode, DirectoryNode
from ebk.db.models import Book


class TitleFileNode(FileNode):
    """Book title as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="title", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read book title.

        Returns:
            Book title
        """
        return self.book.title or "(No title)"

    def get_info(self) -> Dict[str, Any]:
        """Get file info with title preview."""
        title = self.book.title or ""
        # Truncate to 60 chars
        preview = title[:60] + "..." if len(title) > 60 else title
        return {
            "type": "file",
            "name": "title",
            "preview": preview,
        }


class AuthorsFileNode(FileNode):
    """Book authors as a readable file (one per line)."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="authors", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read authors list.

        Returns:
            Authors, one per line
        """
        if not self.book.authors:
            return "(No authors)"

        return "\n".join(author.name for author in self.book.authors)

    def get_info(self) -> Dict[str, Any]:
        """Get file info with authors preview."""
        if not self.book.authors:
            preview = ""
        else:
            authors = ", ".join(a.name for a in self.book.authors)
            preview = authors[:60] + "..." if len(authors) > 60 else authors
        return {
            "type": "file",
            "name": "authors",
            "preview": preview,
        }


class SubjectsFileNode(FileNode):
    """Book subjects/tags as a readable file (one per line)."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="subjects", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read subjects list.

        Returns:
            Subjects, one per line
        """
        if not self.book.subjects:
            return "(No subjects)"

        return "\n".join(subject.name for subject in self.book.subjects)

    def get_info(self) -> Dict[str, Any]:
        """Get file info with subjects preview."""
        if not self.book.subjects:
            preview = ""
        else:
            subjects = ", ".join(s.name for s in self.book.subjects)
            preview = subjects[:60] + "..." if len(subjects) > 60 else subjects
        return {
            "type": "file",
            "name": "subjects",
            "preview": preview,
        }


class DescriptionFileNode(FileNode):
    """Book description as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="description", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read book description.

        Returns:
            Book description or placeholder
        """
        return self.book.description or "(No description)"


class TextFileNode(FileNode):
    """Extracted full text as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="text", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read extracted text.

        Returns:
            Full extracted text or message if not available
        """
        # Check if any file has extracted text
        if self.book.files:
            for file in self.book.files:
                if file.extracted_text and file.extracted_text.content:
                    return file.extracted_text.content

        return "(No text extracted)"

    def get_info(self) -> Dict[str, Any]:
        """Get text file info with size.

        Returns:
            Dict with file information
        """
        info = super().get_info()

        # Calculate size from extracted text
        if self.book.files:
            for file in self.book.files:
                if file.extracted_text and file.extracted_text.content:
                    info["size"] = len(file.extracted_text.content)
                    break

        return info


class YearFileNode(FileNode):
    """Publication year as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="year", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read publication year.

        Returns:
            Publication year or placeholder
        """
        if self.book.publication_date:
            # Try to extract year from date string
            date_str = str(self.book.publication_date)
            if len(date_str) >= 4:
                return date_str[:4]
            return date_str

        return "(Unknown)"

    def get_info(self) -> Dict[str, Any]:
        """Get file info with year preview."""
        if self.book.publication_date:
            date_str = str(self.book.publication_date)
            preview = date_str[:4] if len(date_str) >= 4 else date_str
        else:
            preview = ""
        return {
            "type": "file",
            "name": "year",
            "preview": preview,
        }


class LanguageFileNode(FileNode):
    """Language code as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="language", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read language code.

        Returns:
            Language code or placeholder
        """
        return self.book.language or "(Unknown)"

    def get_info(self) -> Dict[str, Any]:
        """Get file info with language preview."""
        return {
            "type": "file",
            "name": "language",
            "preview": self.book.language or "",
        }


class PublisherFileNode(FileNode):
    """Publisher name as a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="publisher", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read publisher name.

        Returns:
            Publisher name or placeholder
        """
        return self.book.publisher or "(Unknown)"

    def get_info(self) -> Dict[str, Any]:
        """Get file info with publisher preview."""
        publisher = self.book.publisher or ""
        preview = publisher[:60] + "..." if len(publisher) > 60 else publisher
        return {
            "type": "file",
            "name": "publisher",
            "preview": preview,
        }


class MetadataFileNode(FileNode):
    """All metadata formatted in a readable file."""

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        super().__init__(name="metadata", parent=parent)
        self.book = book

    def read_content(self) -> str:
        """Read all metadata formatted nicely.

        Returns:
            Formatted metadata
        """
        lines = []

        # Basic info
        lines.append(f"Title: {self.book.title or '(No title)'}")

        if self.book.subtitle:
            lines.append(f"Subtitle: {self.book.subtitle}")

        # Authors
        if self.book.authors:
            authors_str = ", ".join(a.name for a in self.book.authors)
            lines.append(f"Authors: {authors_str}")

        # Publication info
        if self.book.publication_date:
            lines.append(f"Published: {self.book.publication_date}")

        if self.book.publisher:
            lines.append(f"Publisher: {self.book.publisher}")

        # Language and series
        if self.book.language:
            lines.append(f"Language: {self.book.language}")

        if self.book.series:
            series_str = self.book.series
            if self.book.series_index:
                series_str += f" #{self.book.series_index}"
            lines.append(f"Series: {series_str}")

        # Physical info
        if self.book.page_count:
            lines.append(f"Pages: {self.book.page_count}")

        # Subjects
        if self.book.subjects:
            subjects_str = ", ".join(s.name for s in self.book.subjects)
            lines.append(f"Subjects: {subjects_str}")

        # Files
        if self.book.files:
            formats = ", ".join(f.format.upper() for f in self.book.files)
            lines.append(f"Formats: {formats}")
            lines.append(f"Files: {len(self.book.files)}")

        # Description
        if self.book.description:
            lines.append(f"\nDescription:")
            lines.append(self.book.description)

        return "\n".join(lines)


class BookColorFile(FileNode):
    """Book color as a writable file."""

    def __init__(self, book: Book, library, parent: Optional[DirectoryNode] = None):
        """Initialize book color file.

        Args:
            book: Book database model
            library: Library instance for database access
            parent: Parent BookNode
        """
        super().__init__(name="color", parent=parent)
        self.book = book
        self.library = library

    def read_content(self) -> str:
        """Read book color.

        Returns:
            Hex color code or empty string
        """
        return self.book.color or ""

    def write_content(self, content: str) -> None:
        """Write book color.

        Args:
            content: Hex color code (e.g., "#FF5733" or "FF5733") or named color
        """
        import re

        color = content.strip()

        if not color:
            # Empty string clears the color
            self.book.color = None
            self.library.session.commit()
            return

        # Support common named colors
        named_colors = {
            'red': '#FF0000',
            'green': '#00FF00',
            'blue': '#0000FF',
            'yellow': '#FFFF00',
            'orange': '#FFA500',
            'purple': '#800080',
            'pink': '#FFC0CB',
            'cyan': '#00FFFF',
            'magenta': '#FF00FF',
            'lime': '#00FF00',
            'navy': '#000080',
            'teal': '#008080',
            'gray': '#808080',
            'grey': '#808080',
            'black': '#000000',
            'white': '#FFFFFF',
        }

        # Check if it's a named color first
        color_lower = color.lower()
        if color_lower in named_colors:
            color = named_colors[color_lower]
        else:
            # Add # prefix if not present for hex codes
            if not color.startswith('#'):
                color = '#' + color

            # Validate hex color format (#RGB or #RRGGBB)
            hex_pattern = r'^#[0-9A-Fa-f]{3}$|^#[0-9A-Fa-f]{6}$'
            if not re.match(hex_pattern, color):
                raise ValueError(
                    f"Invalid color format: '{content}'. "
                    f"Use hex codes (#FF5733 or #F73) or named colors "
                    f"({', '.join(sorted(named_colors.keys()))})"
                )

        self.book.color = color
        self.library.session.commit()
