"""MCP server for ebk library management."""
from pathlib import Path

from mcp.server import FastMCP

from ebk.library_db import Library
from ebk.mcp.tools import get_schema_impl, execute_sql_impl, update_books_impl


def create_mcp_server(library: Library) -> FastMCP:
    """Create and configure the MCP server with library tools."""
    mcp = FastMCP(
        "ebk",
        instructions="ebk ebook library manager. Use get_schema to understand the database, "
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

    return mcp


def run_server(library_path):
    """Entry point: open library and run MCP server over stdio."""
    lib = Library.open(Path(library_path))
    mcp = create_mcp_server(lib)
    try:
        mcp.run(transport="stdio")
    finally:
        lib.close()
