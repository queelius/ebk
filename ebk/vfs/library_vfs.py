"""Main LibraryVFS class - entry point for VFS access."""

from pathlib import Path as FilePath

from ebk.library_db import Library
from ebk.vfs.base import DirectoryNode, Node
from ebk.vfs.resolver import PathResolver
from ebk.vfs.nodes import RootNode


class LibraryVFS:
    """Virtual File System for a library.

    This is the main entry point for accessing the VFS. It creates
    the root node and provides a resolver for path navigation.

    Usage:
        >>> lib = Library.open("/path/to/library")
        >>> vfs = LibraryVFS(lib)
        >>>
        >>> # Navigate using resolver
        >>> books_dir = vfs.resolver.resolve("/books", vfs.root)
        >>> book_node = vfs.resolver.resolve("/books/42", vfs.root)
        >>>
        >>> # List children
        >>> children = books_dir.list_children()
        >>>
        >>> # Read file content
        >>> title_node = vfs.resolver.resolve("/books/42/title", vfs.root)
        >>> if isinstance(title_node, FileNode):
        >>>     print(title_node.read_content())
    """

    def __init__(self, library: Library):
        """Initialize VFS for a library.

        Args:
            library: Library instance
        """
        self.library = library
        self.root = RootNode(library)
        self.resolver = PathResolver(self.root)
        self.current = self.root  # Current working directory

    def cd(self, path: str) -> bool:
        """Change current directory.

        Args:
            path: Path to navigate to

        Returns:
            True if successful, False otherwise
        """
        new_dir = self.resolver.resolve_directory(path, self.current)
        if new_dir is None:
            return False

        self.current = new_dir
        return True

    def pwd(self) -> str:
        """Get current working directory path.

        Returns:
            Current path
        """
        return self.current.get_path()

    def ls(self, path: str = ".") -> list:
        """List children of a directory.

        Args:
            path: Path to list (default: current directory)

        Returns:
            List of nodes
        """
        node = self.resolver.resolve(path, self.current)
        if node is None or not isinstance(node, DirectoryNode):
            return []

        return node.list_children()

    def cat(self, path: str) -> str:
        """Read content of a file node.

        Args:
            path: Path to file

        Returns:
            File content or error message
        """
        from ebk.vfs.base import FileNode

        node = self.resolver.resolve(path, self.current)
        if node is None:
            return f"cat: {path}: No such file or directory"

        if not isinstance(node, FileNode):
            return f"cat: {path}: Is a directory"

        return node.read_content()

    def get_node(self, path: str) -> Node:
        """Resolve a path to a node.

        Args:
            path: Path to resolve

        Returns:
            Resolved node or None
        """
        return self.resolver.resolve(path, self.current)

    def complete(self, partial: str) -> list:
        """Get tab completion candidates.

        Args:
            partial: Partial path

        Returns:
            List of completion candidates
        """
        return self.resolver.complete_path(partial, self.current)
