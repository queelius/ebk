"""MCP server for book-memex library management."""
from pathlib import Path

from mcp.server import FastMCP

from book_memex.library_db import Library
from book_memex.mcp.tools import get_schema_impl, execute_sql_impl, update_books_impl


def create_mcp_server(library: Library) -> FastMCP:
    """Create and configure the MCP server with library tools."""
    mcp = FastMCP(
        "book-memex",
        instructions="book-memex ebook library manager. Use get_schema to understand the database, "
        "execute_sql for read queries, and update_books for modifications.",
    )

    @mcp.tool(
        name="get_schema",
        description="Get the library database schema: tables, columns, relationships, and enums. "
        "Use this to understand the data model before writing SQL queries.",
    )
    def get_schema() -> dict:
        return get_schema_impl(library.session)

    @mcp.tool(
        name="execute_sql",
        description="Execute a read-only SQL SELECT query against the library database. "
        "Use positional ? placeholders for parameters. Returns columns, rows, and row_count. "
        "Maximum 1000 rows returned (truncated flag set if more exist).",
    )
    def execute_sql(sql: str, params: list | None = None, max_rows: int = 1000) -> dict:
        return execute_sql_impl(library.db_path, sql, params=params, max_rows=max_rows)

    @mcp.tool(
        name="update_books",
        description="Update book metadata in batch. Pass a dict of book_id -> {field: value, ...}. "
        "Scalar fields: any Book or PersonalMetadata column. "
        "Collection ops: add_tags/remove_tags, add_authors/remove_authors, add_subjects/remove_subjects. "
        "Special: merge_into (mutually exclusive with other fields).",
    )
    def update_books(updates: dict) -> dict:
        return update_books_impl(library.session, updates)

    from book_memex.mcp.tools import (
        list_marginalia_impl, get_marginalia_impl, add_marginalia_impl,
        update_marginalia_impl, delete_marginalia_impl, restore_marginalia_impl,
    )

    @mcp.tool(
        name="list_marginalia",
        description=(
            "List marginalia for a book. Archived entries are excluded by "
            "default (set include_archived=True to include them). Default "
            "limit is 50; pass a smaller or larger value as needed. Optional "
            "scope filter selects one of: highlight (passage-anchored), "
            "book_note (whole-book note), collection_note (not attached to "
            "any book), cross_book_note (spans 2+ books)."
        ),
    )
    def list_marginalia(
        book_id: int, scope: str | None = None,
        include_archived: bool = False, limit: int = 50,
    ) -> list:
        return list_marginalia_impl(
            library.session, book_id=book_id, scope=scope,
            include_archived=include_archived, limit=limit,
        )

    @mcp.tool(
        name="get_marginalia",
        description=(
            "Get a marginalia record by its uuid, or by its full "
            "book-memex://marginalia/<uuid> URI. Both are accepted."
        ),
    )
    def get_marginalia(uuid: str) -> dict:
        return get_marginalia_impl(library.session, uuid=uuid)

    @mcp.tool(
        name="add_marginalia",
        description="Create marginalia linked to 0 or more books by URI. "
        "A single book + location = highlight; single book no location = book_note; "
        "no books = collection_note; multiple books = cross_book_note.",
    )
    def add_marginalia(
        book_uris: list[str],
        content: str | None = None,
        highlighted_text: str | None = None,
        page_number: int | None = None,
        position: dict | None = None,
        category: str | None = None,
        color: str | None = None,
        pinned: bool = False,
    ) -> dict:
        return add_marginalia_impl(
            library.session, book_uris=book_uris, content=content,
            highlighted_text=highlighted_text, page_number=page_number,
            position=position, category=category, color=color, pinned=pinned,
        )

    @mcp.tool(
        name="update_marginalia",
        description="Update editable fields of a marginalia by uuid.",
    )
    def update_marginalia(
        uuid: str,
        content: str | None = None,
        highlighted_text: str | None = None,
        category: str | None = None,
        color: str | None = None,
        pinned: bool | None = None,
    ) -> dict:
        return update_marginalia_impl(
            library.session, uuid=uuid, content=content,
            highlighted_text=highlighted_text, category=category,
            color=color, pinned=pinned,
        )

    @mcp.tool(
        name="delete_marginalia",
        description="Soft-delete a marginalia (archive it). Pass hard=True to irreversibly delete.",
    )
    def delete_marginalia(uuid: str, hard: bool = False) -> dict:
        return delete_marginalia_impl(library.session, uuid=uuid, hard=hard)

    @mcp.tool(
        name="restore_marginalia",
        description="Restore a soft-deleted marginalia (clear archived_at).",
    )
    def restore_marginalia(uuid: str) -> dict:
        return restore_marginalia_impl(library.session, uuid=uuid)

    from book_memex.mcp.tools import (
        start_reading_session_impl, end_reading_session_impl,
        list_reading_sessions_impl, delete_reading_session_impl,
        restore_reading_session_impl,
        get_reading_progress_impl, set_reading_progress_impl,
    )

    @mcp.tool(
        name="start_reading_session",
        description="Start a reading session for a book. Optional start_anchor (CFI or page).",
    )
    def start_reading_session(book_id: int, start_anchor: dict | None = None) -> dict:
        return start_reading_session_impl(
            library.session, book_id=book_id, start_anchor=start_anchor,
        )

    @mcp.tool(
        name="end_reading_session",
        description="End a reading session by uuid. Idempotent: ending an already-ended session returns it unchanged.",
    )
    def end_reading_session(uuid: str, end_anchor: dict | None = None) -> dict:
        return end_reading_session_impl(
            library.session, uuid=uuid, end_anchor=end_anchor,
        )

    @mcp.tool(
        name="list_reading_sessions",
        description="List reading sessions for a book.",
    )
    def list_reading_sessions(
        book_id: int, include_archived: bool = False, limit: int = 50,
    ) -> list:
        return list_reading_sessions_impl(
            library.session, book_id=book_id,
            include_archived=include_archived, limit=limit,
        )

    @mcp.tool(
        name="delete_reading_session",
        description="Soft-delete (archive) or hard-delete a reading session.",
    )
    def delete_reading_session(uuid: str, hard: bool = False) -> dict:
        return delete_reading_session_impl(library.session, uuid=uuid, hard=hard)

    @mcp.tool(
        name="restore_reading_session",
        description="Restore a soft-deleted reading session.",
    )
    def restore_reading_session(uuid: str) -> dict:
        return restore_reading_session_impl(library.session, uuid=uuid)

    @mcp.tool(
        name="get_reading_progress",
        description="Get the current reading progress (anchor + percentage) for a book.",
    )
    def get_reading_progress(book_id: int) -> dict:
        return get_reading_progress_impl(library.session, book_id=book_id)

    @mcp.tool(
        name="set_reading_progress",
        description="Set reading progress for a book. Rejects backward progress unless force=True.",
    )
    def set_reading_progress(
        book_id: int, anchor: dict,
        percentage: float | None = None, force: bool = False,
    ) -> dict:
        return set_reading_progress_impl(
            library.session, book_id=book_id, anchor=anchor,
            percentage=percentage, force=force,
        )

    return mcp


def run_server(library_path):
    """Entry point: open library and run MCP server over stdio."""
    lib = Library.open(Path(library_path))
    mcp = create_mcp_server(lib)
    try:
        mcp.run(transport="stdio")
    finally:
        lib.close()
