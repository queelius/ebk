"""Author-related VFS nodes."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import VirtualNode, DirectoryNode, SymlinkNode, Node
from ebk.library_db import Library
from ebk.db.models import Author


class AuthorsDirectoryNode(VirtualNode):
    """/authors/ - Virtual directory listing all authors.

    Each child is an AuthorNode representing books by that author.
    """

    def __init__(self, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize authors directory.

        Args:
            library: Library instance
            parent: Parent node (usually root)
        """
        super().__init__(name="authors", parent=parent)
        self.library = library

    def list_children(self) -> List[Node]:
        """List all authors.

        Returns:
            List of AuthorNode instances
        """
        # Query all authors from database
        # For now, we'll get unique authors from books
        authors_query = self.library.session.query(Author).all()

        author_nodes = []
        for author in authors_query:
            # Create a slug from author name
            slug = self._make_slug(author.name)
            node = AuthorNode(author, slug, self.library, parent=self)
            author_nodes.append(node)

        return author_nodes

    def get_child(self, name: str) -> Optional[Node]:
        """Get an author by slug.

        Args:
            name: Author slug (e.g., "knuth-donald")

        Returns:
            AuthorNode or None
        """
        # Try to find author by matching slug
        authors = self.library.session.query(Author).all()

        for author in authors:
            slug = self._make_slug(author.name)
            if slug == name:
                return AuthorNode(author, slug, self.library, parent=self)

        return None

    def _make_slug(self, name: str) -> str:
        """Convert author name to filesystem-safe slug.

        Args:
            name: Author name

        Returns:
            Slugified name (e.g., "Donald Knuth" -> "knuth-donald")
        """
        # Simple slugification: lowercase, replace spaces with hyphens
        # Reverse name order (Last, First -> first-last)
        parts = name.lower().split()
        if len(parts) >= 2:
            # Assume "First Last" or "Last, First"
            if "," in name:
                # "Last, First" format
                slug = "-".join(reversed([p.strip(",") for p in parts]))
            else:
                # "First Last" format - reverse to "last-first"
                slug = "-".join(reversed(parts))
        else:
            slug = "-".join(parts)

        # Remove special characters
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug

    def get_info(self) -> Dict[str, Any]:
        """Get authors directory info.

        Returns:
            Dict with directory information
        """
        total = self.library.session.query(Author).count()
        return {
            "type": "virtual",
            "name": "authors",
            "total_authors": total,
            "path": self.get_path(),
        }


class AuthorNode(VirtualNode):
    """/authors/knuth-donald/ - Books by a specific author.

    Contains symlinks to books by this author.
    """

    def __init__(
        self,
        author: Author,
        slug: str,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize author node.

        Args:
            author: Author database model
            slug: Author slug for URL
            library: Library instance
            parent: Parent node (usually AuthorsDirectoryNode)
        """
        super().__init__(name=slug, parent=parent)
        self.author = author
        self.library = library

    def list_children(self) -> List[Node]:
        """List books by this author as symlinks.

        Returns:
            List of SymlinkNode instances
        """
        symlinks = []
        for book in self.author.books:
            target_path = f"/books/{book.id}"
            name = str(book.id)

            # Include book metadata for display
            metadata = {
                "title": book.title or "Untitled",
            }
            if book.authors:
                metadata["author"] = ", ".join([a.name for a in book.authors])

            symlink = SymlinkNode(name, target_path, parent=self, metadata=metadata)
            symlinks.append(symlink)

        return symlinks

    def get_child(self, name: str) -> Optional[Node]:
        """Get a book symlink by ID.

        Args:
            name: Book ID as string

        Returns:
            SymlinkNode or None
        """
        try:
            book_id = int(name)
        except ValueError:
            return None

        # Check if this book is by this author
        for book in self.author.books:
            if book.id == book_id:
                target_path = f"/books/{book.id}"

                # Include book metadata for display
                metadata = {
                    "title": book.title or "Untitled",
                }
                if book.authors:
                    metadata["author"] = ", ".join([a.name for a in book.authors])

                return SymlinkNode(name, target_path, parent=self, metadata=metadata)

        return None

    def get_info(self) -> Dict[str, Any]:
        """Get author node info.

        Returns:
            Dict with author information
        """
        return {
            "type": "virtual",
            "name": self.name,
            "author": self.author.name,
            "book_count": len(self.author.books),
            "path": self.get_path(),
        }
