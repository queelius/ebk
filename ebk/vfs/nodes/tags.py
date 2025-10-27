"""Tag-related VFS nodes for hierarchical user-defined organization."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import VirtualNode, DirectoryNode, SymlinkNode, Node, FileNode
from ebk.library_db import Library
from ebk.db.models import Tag
from ebk.services.tag_service import TagService


class TagsDirectoryNode(VirtualNode):
    """/tags/ - Virtual directory with hierarchical tag structure.

    This is the entry point for browsing user-defined tags.
    Shows root-level tags as children.
    """

    def __init__(self, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize tags directory.

        Args:
            library: Library instance
            parent: Parent node (usually root)
        """
        super().__init__(name="tags", parent=parent)
        self.library = library
        self.tag_service = TagService(library.session)

    def list_children(self) -> List[Node]:
        """List root-level tags.

        Returns:
            List of TagNode instances for tags with no parent
        """
        root_tags = self.tag_service.get_root_tags()

        tag_nodes = []
        for tag in root_tags:
            node = TagNode(tag, self.library, parent=self)
            tag_nodes.append(node)

        return tag_nodes

    def get_child(self, name: str) -> Optional[Node]:
        """Get a root-level tag by name.

        Args:
            name: Tag name (e.g., "Work", "Reading-List")

        Returns:
            TagNode or None
        """
        # Try to find tag by name at root level
        tag = self.tag_service.get_tag(name)

        if tag and tag.parent_id is None:
            return TagNode(tag, self.library, parent=self)

        return None

    def get_info(self) -> Dict[str, Any]:
        """Get tags directory info.

        Returns:
            Dict with directory information
        """
        total = self.library.session.query(Tag).count()
        root_count = len(self.tag_service.get_root_tags())

        return {
            "type": "virtual",
            "name": "tags",
            "total_tags": total,
            "root_tags": root_count,
            "path": self.get_path(),
        }


class TagNode(VirtualNode):
    """/tags/Work/ or /tags/Work/Project-2024/ - A tag directory.

    Represents a tag in the hierarchy. Contains:
    - Child tags (subdirectories)
    - Books with this tag (symlinks to /books/ID)
    - Metadata files (description, color, stats)
    """

    def __init__(
        self,
        tag: Tag,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize tag node.

        Args:
            tag: Tag database model
            library: Library instance
            parent: Parent node (TagsDirectoryNode or another TagNode)
        """
        super().__init__(name=tag.name, parent=parent)
        self.tag = tag
        self.library = library
        self.tag_service = TagService(library.session)

    def list_children(self) -> List[Node]:
        """List child tags and books.

        Returns:
            List of TagNode instances (for child tags) and
            SymlinkNode instances (for books)
        """
        children = []

        # Add child tags as subdirectories
        child_tags = self.tag_service.get_children(self.tag)
        for child_tag in child_tags:
            node = TagNode(child_tag, self.library, parent=self)
            children.append(node)

        # Add books as symlinks to /books/ID
        for book in self.tag.books:
            target_path = f"/books/{book.id}"
            name = str(book.id)

            # Include book metadata for display
            metadata = {
                "title": book.title or "Untitled",
            }
            if book.authors:
                metadata["author"] = ", ".join([a.name for a in book.authors])

            symlink = SymlinkNode(name, target_path, parent=self, metadata=metadata)
            children.append(symlink)

        # Add metadata files (always show, even if empty - they're writable)
        children.append(TagDescriptionFile(self.tag, self.library, parent=self))
        children.append(TagColorFile(self.tag, self.library, parent=self))
        children.append(TagStatsFile(self.tag, self.tag_service, parent=self))

        return children

    def get_child(self, name: str) -> Optional[Node]:
        """Get a child tag or book by name.

        Args:
            name: Child tag name, book ID, or metadata file name

        Returns:
            Node or None
        """
        # Check for metadata files first
        if name == "description":
            return TagDescriptionFile(self.tag, self.library, parent=self)

        if name == "color":
            return TagColorFile(self.tag, self.library, parent=self)

        if name == "stats":
            return TagStatsFile(self.tag, self.tag_service, parent=self)

        # Try to find child tag by name
        child_tags = self.tag_service.get_children(self.tag)
        for child_tag in child_tags:
            if child_tag.name == name:
                return TagNode(child_tag, self.library, parent=self)

        # Try to find book by ID
        try:
            book_id = int(name)
        except ValueError:
            return None

        # Check if this book has this tag
        for book in self.tag.books:
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
        """Get tag node info.

        Returns:
            Dict with tag information
        """
        child_tags = self.tag_service.get_children(self.tag)

        return {
            "type": "virtual",
            "name": self.name,
            "path": self.tag.path,
            "full_path": self.get_path(),
            "depth": self.tag.depth,
            "book_count": len(self.tag.books),
            "child_tags": len(child_tags),
            "description": self.tag.description,
            "color": self.tag.color,
            "created_at": self.tag.created_at.isoformat() if self.tag.created_at else None,
        }


class TagDescriptionFile(FileNode):
    """Metadata file showing tag description."""

    def __init__(self, tag: Tag, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize tag description file.

        Args:
            tag: Tag database model
            library: Library instance for database access
            parent: Parent TagNode
        """
        super().__init__(name="description", parent=parent)
        self.tag = tag
        self.library = library

    def read_content(self) -> str:
        """Read tag description.

        Returns:
            Tag description text
        """
        return self.tag.description or ""

    def write_content(self, content: str) -> None:
        """Write tag description.

        Args:
            content: New description text
        """
        self.tag.description = content.strip()
        self.library.session.commit()


class TagColorFile(FileNode):
    """Metadata file showing tag color."""

    def __init__(self, tag: Tag, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize tag color file.

        Args:
            tag: Tag database model
            library: Library instance for database access
            parent: Parent TagNode
        """
        super().__init__(name="color", parent=parent)
        self.tag = tag
        self.library = library

    def read_content(self) -> str:
        """Read tag color.

        Returns:
            Hex color code
        """
        return self.tag.color or ""

    def write_content(self, content: str) -> None:
        """Write tag color.

        Args:
            content: Hex color code (e.g., "#FF5733" or "FF5733") or named color
        """
        import re

        color = content.strip()

        if not color:
            # Empty string clears the color
            self.tag.color = None
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

        self.tag.color = color
        self.library.session.commit()


class TagStatsFile(FileNode):
    """Metadata file showing tag statistics."""

    def __init__(
        self,
        tag: Tag,
        tag_service: TagService,
        parent: Optional[DirectoryNode] = None
    ):
        """Initialize tag stats file.

        Args:
            tag: Tag database model
            tag_service: TagService instance
            parent: Parent TagNode
        """
        super().__init__(name="stats", parent=parent)
        self.tag = tag
        self.tag_service = tag_service

    def read_content(self) -> str:
        """Read tag statistics.

        Returns:
            Formatted statistics text
        """
        stats = self.tag_service.get_tag_stats(self.tag.path)

        lines = [
            f"Tag: {self.tag.path}",
            f"Name: {self.tag.name}",
            f"Depth: {stats.get('depth', 0)}",
            f"Books: {stats.get('book_count', 0)}",
            f"Subtags: {stats.get('subtag_count', 0)}",
        ]

        if self.tag.description:
            lines.append(f"Description: {self.tag.description}")

        if self.tag.color:
            lines.append(f"Color: {self.tag.color}")

        if stats.get('created_at'):
            lines.append(f"Created: {stats['created_at']}")

        return "\n".join(lines)
