"""Path resolution for the Virtual File System.

Handles path parsing and navigation (cd, ls semantics).
"""

from pathlib import PurePosixPath
from typing import Optional, List, Tuple

from ebk.vfs.base import Node, DirectoryNode, SymlinkNode


class PathResolver:
    """Resolves paths in the VFS and handles navigation.

    This class provides the core navigation logic for cd, ls, etc.
    It handles:
    - Absolute paths: /books/42/title
    - Relative paths: ../other, ./files
    - Special paths: ., .., ~
    - Symlink resolution
    """

    def __init__(self, root: DirectoryNode):
        """Initialize path resolver.

        Args:
            root: Root node of the VFS
        """
        self.root = root

    def resolve(
        self,
        path: str,
        current: DirectoryNode,
        follow_symlinks: bool = True,
    ) -> Optional[Node]:
        """Resolve a path to a node.

        Args:
            path: Path to resolve (absolute or relative)
            current: Current working directory
            follow_symlinks: Whether to follow symlinks

        Returns:
            Resolved node or None if path doesn't exist
        """
        # Handle empty path
        if not path or path == ".":
            return current

        # Parse path
        parts = self._parse_path(path)

        # Start from root or current directory
        if path.startswith("/"):
            node = self.root
        else:
            node = current

        # Navigate through path parts
        for part in parts:
            if part == "." or part == "":
                continue
            elif part == "..":
                # Go to parent
                if node.parent is not None:
                    node = node.parent
                # Stay at root if already at root
            else:
                # Navigate to child
                if not isinstance(node, DirectoryNode):
                    # Can't cd into a file
                    return None

                child = node.get_child(part)
                if child is None:
                    return None

                # Follow symlinks if requested
                if follow_symlinks and isinstance(child, SymlinkNode):
                    child = self.resolve(child.target_path, current, follow_symlinks=True)
                    if child is None:
                        return None

                node = child

        return node

    def resolve_directory(
        self,
        path: str,
        current: DirectoryNode,
    ) -> Optional[DirectoryNode]:
        """Resolve a path to a directory node.

        Args:
            path: Path to resolve
            current: Current working directory

        Returns:
            Directory node or None if path doesn't exist or isn't a directory
        """
        node = self.resolve(path, current)
        if node is None or not isinstance(node, DirectoryNode):
            return None
        return node

    def normalize_path(self, path: str, current: DirectoryNode) -> str:
        """Normalize a path to absolute form.

        Args:
            path: Path to normalize
            current: Current working directory

        Returns:
            Normalized absolute path
        """
        # Resolve to node first
        node = self.resolve(path, current)
        if node is None:
            # Path doesn't exist, do best effort normalization
            return self._normalize_nonexistent(path, current)

        return node.get_path()

    def complete_path(
        self,
        partial: str,
        current: DirectoryNode,
    ) -> List[str]:
        """Get completion candidates for a partial path.

        Used for tab completion.

        Args:
            partial: Partial path to complete
            current: Current working directory

        Returns:
            List of completion candidates
        """
        # Split into directory part and filename part
        if "/" in partial:
            dir_part, file_part = partial.rsplit("/", 1)
            if partial.startswith("/"):
                dir_part = "/" + dir_part if dir_part else "/"
        else:
            dir_part = ""
            file_part = partial

        # Resolve directory
        if dir_part:
            dir_node = self.resolve_directory(dir_part, current)
        else:
            dir_node = current

        if dir_node is None:
            return []

        # Get children and filter by prefix
        children = dir_node.list_children()
        candidates = []

        for child in children:
            if child.name.startswith(file_part):
                if dir_part:
                    candidates.append(f"{dir_part}/{child.name}")
                else:
                    candidates.append(child.name)

                # Add trailing slash for directories
                if isinstance(child, DirectoryNode):
                    candidates[-1] += "/"

        return candidates

    def _parse_path(self, path: str) -> List[str]:
        """Parse a path into parts.

        Args:
            path: Path to parse

        Returns:
            List of path components
        """
        # Use PurePosixPath for Unix-style path handling
        posix_path = PurePosixPath(path)

        # Get parts (excluding the root /)
        parts = posix_path.parts
        if parts and parts[0] == "/":
            parts = parts[1:]

        return list(parts)

    def _normalize_nonexistent(self, path: str, current: DirectoryNode) -> str:
        """Normalize a path that doesn't exist.

        Args:
            path: Path to normalize
            current: Current working directory

        Returns:
            Best-effort normalized path
        """
        if path.startswith("/"):
            # Already absolute
            return str(PurePosixPath(path))

        # Make relative path absolute
        current_path = current.get_path()
        combined = PurePosixPath(current_path) / path
        return str(combined)


class PathError(Exception):
    """Error resolving a path."""
    pass


class NotADirectoryError(PathError):
    """Attempted to cd into a non-directory."""
    pass


class NotFoundError(PathError):
    """Path does not exist."""
    pass
