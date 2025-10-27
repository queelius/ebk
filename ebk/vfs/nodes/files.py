"""File-related VFS nodes."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import DirectoryNode, FileNode, Node
from ebk.db.models import Book, File as DBFile


class FilesDirectoryNode(DirectoryNode):
    """/books/42/files/ - Directory listing physical file formats.

    Each child is a PhysicalFileNode representing an actual ebook file
    (PDF, EPUB, etc.).
    """

    def __init__(self, book: Book, parent: Optional[DirectoryNode] = None):
        """Initialize files directory.

        Args:
            book: Book database model
            parent: Parent node (usually BookNode)
        """
        super().__init__(name="files", parent=parent)
        self.book = book

    def list_children(self) -> List[Node]:
        """List all physical files for this book.

        Returns:
            List of PhysicalFileNode instances
        """
        if not self.book.files:
            return []

        file_nodes = []
        for db_file in self.book.files:
            # Use original filename if available, otherwise use format
            filename = f"{self.book.title or 'book'}.{db_file.format.lower()}"
            node = PhysicalFileNode(db_file, filename, parent=self)
            file_nodes.append(node)

        return file_nodes

    def get_child(self, name: str) -> Optional[Node]:
        """Get a physical file by name.

        Args:
            name: Filename (e.g., "book.pdf")

        Returns:
            PhysicalFileNode or None
        """
        if not self.book.files:
            return None

        # Try to match by format extension
        for db_file in self.book.files:
            filename = f"{self.book.title or 'book'}.{db_file.format.lower()}"
            if filename == name or name.endswith(f".{db_file.format.lower()}"):
                return PhysicalFileNode(db_file, filename, parent=self)

        return None

    def get_info(self) -> Dict[str, Any]:
        """Get files directory info.

        Returns:
            Dict with directory information
        """
        total_size = sum(f.size_bytes for f in self.book.files if f.size_bytes is not None) if self.book.files else 0
        return {
            "type": "directory",
            "name": "files",
            "file_count": len(self.book.files) if self.book.files else 0,
            "total_size": total_size,
            "path": self.get_path(),
        }


class PhysicalFileNode(FileNode):
    """A physical ebook file (PDF, EPUB, etc.).

    When cat'd, shows file metadata.
    Use 'open' command to actually open the file.
    """

    def __init__(
        self,
        db_file: DBFile,
        filename: str,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize physical file node.

        Args:
            db_file: File database model
            filename: Display filename
            parent: Parent node (usually FilesDirectoryNode)
        """
        super().__init__(name=filename, parent=parent, size=db_file.size_bytes)
        self.db_file = db_file

    def read_content(self) -> str:
        """Read file metadata (not the actual file content).

        Returns:
            Formatted file metadata
        """
        lines = []
        lines.append(f"Format: {self.db_file.format.upper()}")

        if self.db_file.size_bytes:
            # Format size nicely
            size_mb = self.db_file.size_bytes / (1024 * 1024)
            if size_mb < 1:
                size_kb = self.db_file.size_bytes / 1024
                lines.append(f"Size: {size_kb:.1f} KB")
            else:
                lines.append(f"Size: {size_mb:.1f} MB")

        lines.append(f"Hash: {self.db_file.file_hash[:16]}...")
        lines.append(f"Path: {self.db_file.path}")

        # Check if text was extracted
        if self.db_file.extracted_text:
            lines.append("Text: Extracted")
        else:
            lines.append("Text: Not extracted")

        return "\n".join(lines)

    def get_info(self) -> Dict[str, Any]:
        """Get file metadata.

        Returns:
            Dict with file information
        """
        return {
            "type": "file",
            "name": self.name,
            "format": self.db_file.format,
            "size": self.db_file.size_bytes,
            "hash": self.db_file.file_hash,
            "path": self.get_path(),
        }

    def get_physical_path(self) -> str:
        """Get the actual filesystem path to this file.

        Returns:
            Absolute path to physical file
        """
        # This will be used by the 'open' command
        # Reconstruct from library path + relative path
        return str(self.db_file.path)
