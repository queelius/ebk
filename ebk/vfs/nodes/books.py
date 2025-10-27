"""Book-related VFS nodes."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import VirtualNode, DirectoryNode, FileNode, Node
from ebk.library_db import Library
from ebk.db.models import Book


class BooksDirectoryNode(VirtualNode):
    """/books/ - Virtual directory listing all books.

    Children are BookNode instances (one per book in library).
    Books are accessed by ID: /books/42/
    """

    def __init__(self, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize books directory.

        Args:
            library: Library instance
            parent: Parent node (usually root)
        """
        super().__init__(name="books", parent=parent)
        self.library = library

    def list_children(self) -> List[Node]:
        """List all books in the library.

        Returns:
            List of BookNode instances
        """
        # Query all books from database
        books = self.library.query().all()

        # Create BookNode for each
        book_nodes = []
        for book in books:
            node = BookNode(book, self.library, parent=self)
            book_nodes.append(node)

        return book_nodes

    def get_child(self, name: str) -> Optional[Node]:
        """Get a book by ID.

        Args:
            name: Book ID as string

        Returns:
            BookNode or None if not found
        """
        # Parse book ID
        try:
            book_id = int(name)
        except ValueError:
            return None

        # Get book from database
        book = self.library.get_book(book_id)
        if book is None:
            return None

        return BookNode(book, self.library, parent=self)

    def get_info(self) -> Dict[str, Any]:
        """Get books directory info.

        Returns:
            Dict with directory information
        """
        total = self.library.query().count()
        return {
            "type": "virtual",
            "name": "books",
            "total_books": total,
            "path": self.get_path(),
        }


class BookNode(DirectoryNode):
    """/books/42/ - A specific book with metadata and files.

    Contains:
    - title          - Book title (file)
    - authors        - Authors list (file)
    - subjects       - Subjects/tags (file)
    - description    - Book description (file)
    - text           - Extracted full text (file)
    - year           - Publication year (file)
    - language       - Language code (file)
    - publisher      - Publisher name (file)
    - metadata       - All metadata formatted (file)
    - files/         - Physical files (directory)
    - similar/       - Similar books (virtual directory)
    - annotations/   - User annotations (directory)
    - covers/        - Cover images (directory)
    """

    def __init__(
        self,
        book: Book,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize book node.

        Args:
            book: Book database model
            library: Library instance
            parent: Parent node (usually /books/)
        """
        super().__init__(name=str(book.id), parent=parent)
        self.book = book
        self.library = library
        self._children_cache: Optional[Dict[str, Node]] = None

    def list_children(self) -> List[Node]:
        """List all files and subdirectories for this book.

        Returns:
            List of child nodes
        """
        if self._children_cache is None:
            self._build_children()

        return list(self._children_cache.values())

    def get_child(self, name: str) -> Optional[Node]:
        """Get a child by name.

        Args:
            name: Child name

        Returns:
            Child node or None
        """
        if self._children_cache is None:
            self._build_children()

        return self._children_cache.get(name)

    def _build_children(self) -> None:
        """Build child nodes."""
        from ebk.vfs.nodes.metadata import (
            TitleFileNode,
            AuthorsFileNode,
            SubjectsFileNode,
            DescriptionFileNode,
            TextFileNode,
            YearFileNode,
            LanguageFileNode,
            PublisherFileNode,
            MetadataFileNode,
            BookColorFile,
        )
        from ebk.vfs.nodes.files import FilesDirectoryNode
        from ebk.vfs.nodes.similar import SimilarDirectoryNode

        self._children_cache = {
            "title": TitleFileNode(self.book, parent=self),
            "authors": AuthorsFileNode(self.book, parent=self),
            "subjects": SubjectsFileNode(self.book, parent=self),
            "description": DescriptionFileNode(self.book, parent=self),
            "text": TextFileNode(self.book, parent=self),
            "year": YearFileNode(self.book, parent=self),
            "language": LanguageFileNode(self.book, parent=self),
            "publisher": PublisherFileNode(self.book, parent=self),
            "metadata": MetadataFileNode(self.book, parent=self),
            "color": BookColorFile(self.book, self.library, parent=self),
            "files": FilesDirectoryNode(self.book, parent=self),
            "similar": SimilarDirectoryNode(self.book, self.library, parent=self),
            "tags": BookTagsDirectoryNode(self.book, self.library, parent=self),
            # TODO: annotations/, covers/
        }

    def get_info(self) -> Dict[str, Any]:
        """Get book info.

        Returns:
            Dict with book information
        """
        authors_str = ", ".join(a.name for a in self.book.authors) if self.book.authors else ""
        info = {
            "type": "directory",
            "name": str(self.book.id),
            "title": self.book.title,
            "authors": authors_str,
            "language": self.book.language,
            "files_count": len(self.book.files),
            "path": self.get_path(),
        }

        # Include color if set
        if self.book.color:
            info["color"] = self.book.color

        return info


class BookTagsDirectoryNode(VirtualNode):
    """/books/42/tags/ - Tags associated with this book.

    Shows symlinks to tag paths where this book appears.
    Allows easy navigation to see all tags for a book.
    """

    def __init__(
        self,
        book: Book,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize book tags directory.

        Args:
            book: Book database model
            library: Library instance
            parent: Parent BookNode
        """
        super().__init__(name="tags", parent=parent)
        self.book = book
        self.library = library

    def list_children(self) -> List[Node]:
        """List all tags for this book, organized hierarchically.

        Returns:
            List of BookTagHierarchyNode (directories) and SymlinkNode instances
        """
        from ebk.vfs.base import SymlinkNode

        # Collect all tag paths for this book
        tag_paths = {tag.path for tag in self.book.tags}

        # Find root-level entries (first component of each path)
        root_entries = {}
        for tag in self.book.tags:
            parts = tag.path.split('/')
            root_name = parts[0]

            if root_name not in root_entries:
                root_entries[root_name] = []
            root_entries[root_name].append(tag.path)

        # Create nodes for root-level entries
        children = []
        for root_name, paths in root_entries.items():
            # Check if this root name is a complete tag itself
            if root_name in tag_paths:
                # It's a leaf tag - create symlink
                tag = next(t for t in self.book.tags if t.path == root_name)
                target_path = f"/tags/{tag.path}"
                metadata = {
                    "path": tag.path,
                    "depth": tag.depth,
                }
                if tag.description:
                    metadata["description"] = tag.description[:50] + "..." if len(tag.description) > 50 else tag.description

                symlink = SymlinkNode(root_name, target_path, parent=self, metadata=metadata)
                children.append(symlink)
            else:
                # It's an intermediate directory - create hierarchy node
                hierarchy_node = BookTagHierarchyNode(
                    root_name,
                    self.book,
                    self.library,
                    parent=self
                )
                children.append(hierarchy_node)

        return children

    def get_child(self, name: str) -> Optional[Node]:
        """Get a tag by root name.

        Args:
            name: Root tag name (first component of path)

        Returns:
            SymlinkNode or BookTagHierarchyNode or None
        """
        from ebk.vfs.base import SymlinkNode

        # Collect tag paths to check if name is a complete tag
        tag_paths = {tag.path for tag in self.book.tags}

        # Check if any tag starts with this name
        matching_tags = [tag for tag in self.book.tags if tag.path.split('/')[0] == name]
        if not matching_tags:
            return None

        # If name is a complete tag path, return symlink
        if name in tag_paths:
            tag = next(t for t in self.book.tags if t.path == name)
            target_path = f"/tags/{tag.path}"
            metadata = {
                "path": tag.path,
                "depth": tag.depth,
            }
            if tag.description:
                metadata["description"] = tag.description[:50] + "..." if len(tag.description) > 50 else tag.description

            return SymlinkNode(name, target_path, parent=self, metadata=metadata)
        else:
            # It's an intermediate directory
            return BookTagHierarchyNode(name, self.book, self.library, parent=self)

    def get_info(self) -> Dict[str, Any]:
        """Get tags directory info.

        Returns:
            Dict with directory information
        """
        return {
            "type": "virtual",
            "name": "tags",
            "tag_count": len(self.book.tags) if hasattr(self.book, 'tags') else 0,
            "path": self.get_path(),
        }


class BookTagHierarchyNode(VirtualNode):
    """/books/42/tags/a/ - Intermediate directory in book's tag hierarchy.

    Represents a level in the tag hierarchy for tags assigned to a book.
    For example, if book has tag 'Work/Project-2024', then:
    - /books/42/tags/Work/ is a BookTagHierarchyNode
    - /books/42/tags/Work/Project-2024 is a SymlinkNode
    """

    def __init__(
        self,
        name: str,
        book: Book,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize book tag hierarchy node.

        Args:
            name: Directory name (e.g., "Work")
            book: Book database model
            library: Library instance
            parent: Parent node
        """
        super().__init__(name=name, parent=parent)
        self.book = book
        self.library = library

    def _get_current_prefix(self) -> str:
        """Get the current path prefix for this node.

        Returns:
            Path prefix like "a" or "a/b"
        """
        # Build path from root tags directory
        parts = []
        node = self
        while node is not None and not isinstance(node, BookTagsDirectoryNode):
            parts.insert(0, node.name)
            node = node.parent

        return '/'.join(parts)

    def list_children(self) -> List[Node]:
        """List tags at this level of hierarchy.

        Returns:
            List of BookTagHierarchyNode (subdirs) and SymlinkNode (tags)
        """
        from ebk.vfs.base import SymlinkNode

        prefix = self._get_current_prefix()
        prefix_depth = len(prefix.split('/'))

        # Find all tags under this prefix
        matching_tags = [
            tag for tag in self.book.tags
            if tag.path.startswith(prefix + '/')
        ]

        # Also check if prefix itself is a tag
        tag_paths = {tag.path for tag in self.book.tags}

        # Find next-level entries
        next_level_entries = {}
        for tag in matching_tags:
            # Get the part after the prefix
            relative_path = tag.path[len(prefix) + 1:]  # Remove prefix and /
            parts = relative_path.split('/')
            next_name = parts[0]

            if next_name not in next_level_entries:
                next_level_entries[next_name] = []
            next_level_entries[next_name].append(tag.path)

        # Create nodes
        children = []
        for next_name, paths in next_level_entries.items():
            full_path = f"{prefix}/{next_name}"

            if full_path in tag_paths:
                # It's a complete tag - create symlink
                tag = next(t for t in self.book.tags if t.path == full_path)
                target_path = f"/tags/{tag.path}"
                metadata = {
                    "path": tag.path,
                    "depth": tag.depth,
                }
                if tag.description:
                    metadata["description"] = tag.description[:50] + "..." if len(tag.description) > 50 else tag.description

                symlink = SymlinkNode(next_name, target_path, parent=self, metadata=metadata)
                children.append(symlink)
            else:
                # It's an intermediate directory
                hierarchy_node = BookTagHierarchyNode(
                    next_name,
                    self.book,
                    self.library,
                    parent=self
                )
                children.append(hierarchy_node)

        return children

    def get_child(self, name: str) -> Optional[Node]:
        """Get a child tag or subdirectory.

        Args:
            name: Child name

        Returns:
            SymlinkNode or BookTagHierarchyNode or None
        """
        from ebk.vfs.base import SymlinkNode

        prefix = self._get_current_prefix()
        full_path = f"{prefix}/{name}"

        # Check if this is a complete tag
        tag_paths = {tag.path for tag in self.book.tags}

        if full_path in tag_paths:
            # It's a complete tag - return symlink
            tag = next(t for t in self.book.tags if t.path == full_path)
            target_path = f"/tags/{tag.path}"
            metadata = {
                "path": tag.path,
                "depth": tag.depth,
            }
            if tag.description:
                metadata["description"] = tag.description[:50] + "..." if len(tag.description) > 50 else tag.description

            return SymlinkNode(name, target_path, parent=self, metadata=metadata)
        else:
            # Check if it's an intermediate directory
            has_children = any(
                tag.path.startswith(full_path + '/')
                for tag in self.book.tags
            )
            if has_children:
                return BookTagHierarchyNode(name, self.book, self.library, parent=self)

        return None

    def get_info(self) -> Dict[str, Any]:
        """Get node info.

        Returns:
            Dict with node information
        """
        return {
            "type": "virtual",
            "name": self.name,
            "path": self.get_path(),
            "tag_prefix": self._get_current_prefix(),
        }
