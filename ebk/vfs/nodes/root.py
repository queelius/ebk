"""Root VFS node and top-level directories."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import DirectoryNode, Node
from ebk.library_db import Library


class RootNode(DirectoryNode):
    """Root directory (/) of the VFS.

    Contains top-level directories:
    - books/      - All books
    - authors/    - Browse by author
    - subjects/   - Browse by subject
    - tags/       - Browse by user-defined hierarchical tags
    - series/     - Browse by series
    - recent/     - Recently added/modified books
    - favorites/  - Favorite books
    - unread/     - Unread books
    """

    def __init__(self, library: Library):
        """Initialize root node.

        Args:
            library: Library instance for database access
        """
        super().__init__(name="", parent=None)  # Root has empty name
        self.library = library
        self._children_cache: Optional[Dict[str, Node]] = None

    def list_children(self) -> List[Node]:
        """List top-level directories.

        Returns:
            List of top-level directory nodes
        """
        if self._children_cache is None:
            self._build_children()

        return list(self._children_cache.values())

    def get_child(self, name: str) -> Optional[Node]:
        """Get a top-level directory by name.

        Args:
            name: Directory name

        Returns:
            Directory node or None
        """
        if self._children_cache is None:
            self._build_children()

        return self._children_cache.get(name)

    def _build_children(self) -> None:
        """Build top-level directory nodes."""
        from ebk.vfs.nodes.books import BooksDirectoryNode
        from ebk.vfs.nodes.authors import AuthorsDirectoryNode
        from ebk.vfs.nodes.subjects import SubjectsDirectoryNode
        from ebk.vfs.nodes.tags import TagsDirectoryNode

        self._children_cache = {
            "books": BooksDirectoryNode(self.library, parent=self),
            "authors": AuthorsDirectoryNode(self.library, parent=self),
            "subjects": SubjectsDirectoryNode(self.library, parent=self),
            "tags": TagsDirectoryNode(self.library, parent=self),
            # TODO: Add series, recent, favorites, unread
        }

    def get_info(self) -> Dict[str, Any]:
        """Get root directory info.

        Returns:
            Dict with root directory information
        """
        from ebk.db.models import Tag

        stats = self.library.stats()
        total_tags = self.library.session.query(Tag).count()

        return {
            "type": "directory",
            "name": "/",
            "total_books": stats.get("total_books", 0),
            "total_authors": stats.get("total_authors", 0),
            "total_subjects": stats.get("total_subjects", 0),
            "total_tags": total_tags,
            "path": "/",
        }

    def get_path(self) -> str:
        """Get path (always /).

        Returns:
            Root path
        """
        return "/"
