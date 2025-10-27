"""Base classes for the Virtual File System.

The VFS maps the library database to a filesystem-like structure
that can be navigated with shell commands (cd, ls, cat, etc.).

Architecture:
    - Node: Base class for all VFS nodes
    - DirectoryNode: Nodes that can contain children (cd into them)
    - FileNode: Leaf nodes with content (cat them)
    - VirtualNode: Dynamically computed nodes (e.g., similar books)
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class NodeType(Enum):
    """Type of VFS node."""
    DIRECTORY = "directory"
    FILE = "file"
    VIRTUAL = "virtual"
    SYMLINK = "symlink"


class Node(ABC):
    """Base class for all VFS nodes.

    A Node represents an entry in the virtual filesystem. It can be
    a directory (navigable), a file (readable), or something virtual
    (dynamically computed).

    Attributes:
        name: The name of this node (e.g., "title", "books", "42")
        parent: Parent directory node (None for root)
        node_type: Type of node (directory, file, virtual, symlink)
    """

    def __init__(
        self,
        name: str,
        parent: Optional['DirectoryNode'] = None,
        node_type: NodeType = NodeType.FILE,
    ):
        """Initialize a VFS node.

        Args:
            name: Name of this node
            parent: Parent directory (None for root)
            node_type: Type of node
        """
        self.name = name
        self.parent = parent
        self.node_type = node_type
        self._metadata: Dict[str, Any] = {}

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """Get metadata about this node for display.

        Returns:
            Dict with keys like: size, modified, type, description
        """
        pass

    def get_path(self) -> str:
        """Get absolute path to this node.

        Returns:
            Path like /books/42/title
        """
        if self.parent is None:
            return "/"

        parts = []
        node = self
        while node.parent is not None:
            parts.append(node.name)
            node = node.parent

        if not parts:
            return "/"

        return "/" + "/".join(reversed(parts))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', path='{self.get_path()}')"


class DirectoryNode(Node):
    """A directory node that can contain children.

    Directory nodes can be navigated into with `cd` and their
    children can be listed with `ls`.

    Children can be:
    - Static: Fixed set of children
    - Dynamic: Children computed on-demand (e.g., book list from DB)
    """

    def __init__(self, name: str, parent: Optional['DirectoryNode'] = None):
        """Initialize a directory node.

        Args:
            name: Name of this directory
            parent: Parent directory
        """
        super().__init__(name, parent, NodeType.DIRECTORY)
        self._children: Dict[str, Node] = {}

    @abstractmethod
    def list_children(self) -> List[Node]:
        """List all children of this directory.

        This may compute children dynamically from the database.

        Returns:
            List of child nodes
        """
        pass

    @abstractmethod
    def get_child(self, name: str) -> Optional[Node]:
        """Get a child node by name.

        Args:
            name: Name of child node

        Returns:
            Child node or None if not found
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Get directory metadata.

        Returns:
            Dict with directory information
        """
        children = self.list_children()
        return {
            "type": "directory",
            "name": self.name,
            "children_count": len(children),
            "path": self.get_path(),
        }


class FileNode(Node):
    """A file node with readable content.

    File nodes represent data that can be read with `cat`.
    Examples: book title, description, full text, etc.
    """

    def __init__(
        self,
        name: str,
        parent: Optional[DirectoryNode] = None,
        size: Optional[int] = None,
    ):
        """Initialize a file node.

        Args:
            name: Name of this file
            parent: Parent directory
            size: Size in bytes (if known)
        """
        super().__init__(name, parent, NodeType.FILE)
        self._size = size
        self._content_cache: Optional[str] = None

    @abstractmethod
    def read_content(self) -> str:
        """Read the content of this file.

        Returns:
            File content as string
        """
        pass

    def write_content(self, content: str) -> None:
        """Write content to this file.

        Args:
            content: Content to write

        Raises:
            NotImplementedError: If the file is read-only
        """
        raise NotImplementedError(f"File '{self.name}' is read-only")

    def is_writable(self) -> bool:
        """Check if this file is writable.

        Returns:
            True if file supports writing, False otherwise
        """
        # By default, files are read-only unless they override write_content
        try:
            # Try calling write_content with empty string to see if it raises NotImplementedError
            # This is a bit hacky but works
            return hasattr(self.__class__, 'write_content') and \
                   self.__class__.write_content != FileNode.write_content
        except:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get file metadata.

        Returns:
            Dict with file information
        """
        return {
            "type": "file",
            "name": self.name,
            "size": self._size,
            "path": self.get_path(),
            "writable": self.is_writable(),
        }


class VirtualNode(DirectoryNode):
    """A virtual directory with dynamically computed children.

    Virtual nodes don't have a fixed set of children - they compute
    them on-demand from the database or other sources.

    Examples:
    - /books/ - Lists all books from DB
    - /books/42/similar/ - Computes similar books on-demand
    - /authors/ - Lists all authors from DB
    """

    def __init__(self, name: str, parent: Optional[DirectoryNode] = None):
        """Initialize a virtual directory node.

        Args:
            name: Name of this directory
            parent: Parent directory
        """
        super().__init__(name, parent)
        self.node_type = NodeType.VIRTUAL

    def get_info(self) -> Dict[str, Any]:
        """Get virtual directory metadata.

        Returns:
            Dict with virtual directory information
        """
        info = super().get_info()
        info["type"] = "virtual"
        return info


class SymlinkNode(Node):
    """A symbolic link pointing to another node.

    Used for creating convenient shortcuts, like similar books
    appearing as links in /books/42/similar/.

    Attributes:
        target_path: Path to the target node
        metadata: Optional metadata dict to include in get_info()
    """

    def __init__(
        self,
        name: str,
        target_path: str,
        parent: Optional[DirectoryNode] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a symlink node.

        Args:
            name: Name of this symlink
            target_path: Path to target node
            parent: Parent directory
            metadata: Optional metadata to include in get_info()
        """
        super().__init__(name, parent, NodeType.SYMLINK)
        self.target_path = target_path
        self.metadata = metadata or {}

    def get_info(self) -> Dict[str, Any]:
        """Get symlink metadata.

        Returns:
            Dict with symlink information plus any provided metadata
        """
        info = {
            "type": "symlink",
            "name": self.name,
            "target": self.target_path,
            "path": self.get_path(),
        }
        # Merge in any provided metadata
        info.update(self.metadata)
        return info
