"""Virtual File System for navigating the library database.

The VFS provides a filesystem-like interface for browsing and interacting
with the ebook library. It maps database entities to a hierarchical structure
that can be navigated with familiar shell commands.

Architecture:

    ```
    /                           # Root (RootNode)
    ├── books/                  # All books (BooksDirectoryNode)
    │   ├── 1/                 # Book 1 (BookNode)
    │   │   ├── title          # Metadata file (TitleFileNode)
    │   │   ├── authors        # Metadata file (AuthorsFileNode)
    │   │   ├── description    # Metadata file
    │   │   ├── text           # Extracted text (TextFileNode)
    │   │   ├── files/         # Physical files (FilesDirectoryNode)
    │   │   │   ├── book.pdf
    │   │   │   └── book.epub
    │   │   ├── similar/       # Similar books (SimilarDirectoryNode)
    │   │   ├── annotations/   # User annotations
    │   │   └── covers/        # Cover images
    │   └── 2/
    ├── authors/               # Browse by author (AuthorsDirectoryNode)
    │   └── knuth-donald/      # Books by this author
    ├── subjects/              # Browse by subject
    └── series/                # Browse by series
    ```

Node Types:

    - Node: Base class for all VFS entries
    - DirectoryNode: Can contain children (cd into them)
    - FileNode: Leaf nodes with content (cat them)
    - VirtualNode: Dynamically computed (e.g., /books/, /similar/)
    - SymlinkNode: Links to other nodes

Path Resolution:

    The PathResolver handles navigation:
    - Absolute paths: /books/42/title
    - Relative paths: ../other, ./files
    - Special: ., .., ~ (home = /)
    - Symlink following
    - Tab completion support

Usage Example:

    ```python
    from ebk.library_db import Library
    from ebk.vfs import LibraryVFS

    # Create VFS for a library
    lib = Library.open("/path/to/library")
    vfs = LibraryVFS(lib)

    # Navigate
    root = vfs.root
    books_dir = vfs.resolver.resolve("/books", root)
    book_node = vfs.resolver.resolve("/books/42", root)

    # List children
    children = books_dir.list_children()  # All books
    for child in children:
        print(child.name, child.get_info())

    # Read file content
    title_node = vfs.resolver.resolve("/books/42/title", root)
    if isinstance(title_node, FileNode):
        content = title_node.read_content()
        print(content)
    ```
"""

from ebk.vfs.base import (
    Node,
    DirectoryNode,
    FileNode,
    VirtualNode,
    SymlinkNode,
    NodeType,
)
from ebk.vfs.resolver import PathResolver, PathError, NotADirectoryError, NotFoundError
from ebk.vfs.library_vfs import LibraryVFS

__all__ = [
    # Main entry point
    "LibraryVFS",
    # Core classes
    "Node",
    "DirectoryNode",
    "FileNode",
    "VirtualNode",
    "SymlinkNode",
    "NodeType",
    # Path resolution
    "PathResolver",
    "PathError",
    "NotADirectoryError",
    "NotFoundError",
]
