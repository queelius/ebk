"""VFS REST API Router.

Provides REST endpoints for accessing the Virtual File System,
enabling programmatic navigation of the library structure.

Endpoints:
    GET /api/vfs/           - Root directory listing
    GET /api/vfs/{path:path} - Navigate to path, returns directory/file/symlink info

This allows API consumers to browse the library like a filesystem:
    - /books/               - List all books
    - /books/42/            - Book 42's directory
    - /books/42/title       - Read book title
    - /books/42/files/      - List book files
    - /authors/knuth/       - Books by author
"""

from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ebk.vfs import LibraryVFS, DirectoryNode, FileNode, SymlinkNode


# Pydantic models for VFS responses
class VFSChild(BaseModel):
    """Child entry in a directory listing."""
    name: str
    type: str  # "directory", "file", "symlink", "virtual"
    info: Dict[str, Any] = {}


class VFSDirectoryResponse(BaseModel):
    """Response for directory nodes."""
    type: str = "directory"
    path: str
    name: str
    info: Dict[str, Any] = {}
    children: List[VFSChild] = []
    children_count: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "type": "directory",
                "path": "/books/42",
                "name": "42",
                "info": {"title": "The Art of Computer Programming", "authors": "Donald Knuth"},
                "children": [
                    {"name": "title", "type": "file", "info": {}},
                    {"name": "authors", "type": "file", "info": {}},
                    {"name": "files", "type": "directory", "info": {}},
                    {"name": "similar", "type": "virtual", "info": {}},
                ],
                "children_count": 4,
            }
        }


class VFSFileResponse(BaseModel):
    """Response for file nodes."""
    type: str = "file"
    path: str
    name: str
    content: str
    info: Dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "type": "file",
                "path": "/books/42/title",
                "name": "title",
                "content": "The Art of Computer Programming",
                "info": {"size": 34, "writable": False},
            }
        }


class VFSSymlinkResponse(BaseModel):
    """Response for symlink nodes."""
    type: str = "symlink"
    path: str
    name: str
    target: str
    info: Dict[str, Any] = {}

    class Config:
        json_schema_extra = {
            "example": {
                "type": "symlink",
                "path": "/books/42/similar/1",
                "name": "1",
                "target": "/books/101",
                "info": {"title": "Structure and Interpretation..."},
            }
        }


VFSResponse = Union[VFSDirectoryResponse, VFSFileResponse, VFSSymlinkResponse]


# Create router
router = APIRouter(prefix="/api/vfs", tags=["vfs"])


# Module-level VFS instance (initialized when library is set)
_vfs: Optional[LibraryVFS] = None


def get_vfs() -> LibraryVFS:
    """Get the VFS instance."""
    if _vfs is None:
        raise HTTPException(status_code=500, detail="VFS not initialized")
    return _vfs


def set_vfs(vfs: LibraryVFS) -> None:
    """Set the VFS instance."""
    global _vfs
    _vfs = vfs


def init_vfs_from_library(library) -> None:
    """Initialize VFS from a library instance."""
    global _vfs
    _vfs = LibraryVFS(library)



def _build_response(node, path: str, include_content: bool = True) -> VFSResponse:
    """Build appropriate response for a node."""
    info = node.get_info()

    if isinstance(node, SymlinkNode):
        return VFSSymlinkResponse(
            path=path,
            name=node.name,
            target=node.target_path,
            info={k: v for k, v in info.items() if k not in ("type", "name", "target", "path")},
        )

    if isinstance(node, FileNode):
        content = ""
        if include_content:
            try:
                content = node.read_content()
            except Exception as e:
                content = f"Error reading content: {e}"

        return VFSFileResponse(
            path=path,
            name=node.name,
            content=content,
            info={k: v for k, v in info.items() if k not in ("type", "name", "path")},
        )

    if isinstance(node, DirectoryNode):
        children = []
        try:
            child_nodes = node.list_children()
            for child in child_nodes:
                child_info = child.get_info()
                children.append(VFSChild(
                    name=child.name,
                    type=child.node_type.value,
                    info={k: v for k, v in child_info.items() if k not in ("type", "name", "path")},
                ))
        except Exception as e:
            # Log error but continue
            pass

        return VFSDirectoryResponse(
            path=path,
            name=node.name,
            info={k: v for k, v in info.items() if k not in ("type", "name", "path", "children_count")},
            children=children,
            children_count=len(children),
        )

    # Fallback for unknown node types
    raise HTTPException(status_code=500, detail=f"Unknown node type: {type(node)}")


@router.get(
    "/",
    response_model=VFSDirectoryResponse,
    summary="VFS Root",
    description="Get the root directory of the virtual filesystem.",
    responses={
        200: {
            "description": "Root directory listing",
            "content": {
                "application/json": {
                    "example": {
                        "type": "directory",
                        "path": "/",
                        "name": "",
                        "info": {},
                        "children": [
                            {"name": "books", "type": "virtual", "info": {}},
                            {"name": "authors", "type": "virtual", "info": {}},
                            {"name": "subjects", "type": "virtual", "info": {}},
                            {"name": "tags", "type": "virtual", "info": {}},
                        ],
                        "children_count": 4,
                    }
                }
            },
        }
    },
)
async def get_vfs_root():
    """Get the VFS root directory listing.

    Returns the top-level virtual directories:
    - /books/ - Browse all books by ID
    - /authors/ - Browse books by author
    - /subjects/ - Browse books by subject
    - /tags/ - Browse books by tag hierarchy
    """
    vfs = get_vfs()
    return _build_response(vfs.root, "/")


@router.get(
    "/{path:path}",
    response_model=VFSResponse,
    summary="VFS Path",
    description="Navigate to a path in the virtual filesystem.",
    responses={
        200: {
            "description": "Node at the specified path (directory, file, or symlink)",
        },
        404: {
            "description": "Path not found",
        },
    },
)
async def get_vfs_path(
    path: str,
    follow_symlinks: bool = Query(True, description="Follow symbolic links to their targets"),
    include_content: bool = Query(True, description="Include file content in response (for files only)"),
):
    """Navigate to a path in the VFS and return its contents.

    For directories, returns the listing of children.
    For files, returns the content.
    For symlinks, returns link info (or follows if follow_symlinks=true).

    Examples:
    - /books/ - List all books
    - /books/42 - Book 42's directory
    - /books/42/title - Read book 42's title
    - /books/42/authors - Read book 42's authors
    - /books/42/files/ - List book 42's files
    - /authors/knuth-donald/ - Books by Donald Knuth
    - /tags/Work/Projects/ - Books tagged Work/Projects
    """
    vfs = get_vfs()

    # Normalize path
    if not path.startswith("/"):
        path = "/" + path

    # Handle trailing slash consistently
    clean_path = path.rstrip("/") if path != "/" else path

    # Resolve the path
    node = vfs.resolver.resolve(clean_path, vfs.root, follow_symlinks=follow_symlinks)

    if node is None:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    return _build_response(node, node.get_path(), include_content=include_content)
