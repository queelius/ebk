# MCP Server

ebk includes a built-in [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) server that lets AI assistants like Claude interact with your ebook library directly. The server exposes three tools for schema introspection, read-only SQL queries, and book metadata updates.

## Quick Start

Launch the MCP server with:

```bash
ebk mcp-serve /path/to/library
```

The server uses **stdio transport**, which makes it compatible with Claude Code and other MCP-aware clients.

## Claude Code Integration

Add the following to your Claude Code MCP configuration (typically `~/.claude.json` or project-level `.mcp.json`):

```json
{
  "mcpServers": {
    "ebk": {
      "command": "ebk",
      "args": ["mcp-serve", "/path/to/library"]
    }
  }
}
```

Once configured, Claude Code can query your library, inspect the schema, and update book metadata through natural language.

## Tools

### `get_schema`

Returns the complete database schema: tables, columns (with types, nullability, primary key status), foreign keys, and ORM relationships.

Use this tool first to understand the data model before writing SQL queries.

**Parameters:** None.

**Returns:** `{"tables": {table_name: {columns, foreign_keys, relationships}, ...}}`

### `execute_sql`

Executes a read-only SQL `SELECT` query against the library database.

The executor enforces read-only access through three layers of security:

1. **Prefix check** -- only queries beginning with `SELECT` are accepted; multi-statement queries are rejected.
2. **Read-only connection** -- the SQLite connection is opened in `?mode=ro`, preventing any writes at the database level.
3. **SQLite authorizer** -- a callback whitelist allows only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION` operations.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `sql` | `str` | required | SQL SELECT query. Use `?` for positional placeholders. |
| `params` | `list` | `None` | Positional parameters for `?` placeholders. |
| `max_rows` | `int` | `1000` | Maximum rows to return. |

**Returns:** `{"columns": [...], "rows": [[...], ...], "row_count": N}` (with `"truncated": true` if results exceed `max_rows`), or `{"error": "..."}` on failure.

### `update_books`

Updates book metadata in batch. Pass a dict mapping book IDs to field updates.

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `updates` | `dict` | `{book_id: {field: value, ...}, ...}` |

**Supported operations:**

- **Scalar fields** -- any column on the `Book` or `PersonalMetadata` model (e.g., `title`, `language`, `rating`, `reading_status`).
- **Collection operations** -- `add_tags` / `remove_tags`, `add_authors` / `remove_authors`, `add_subjects` / `remove_subjects`. Values are lists of strings.
- **Merge** -- `{"merge_into": target_id}` merges the source book into the target, moving all files, covers, and collections. This is mutually exclusive with other fields.

**Returns:** `{"updated": [book_id, ...], "errors": {book_id: "message", ...}}`

**Example:**

```json
{
  "42": {"rating": 5.0, "add_tags": ["favorites", "technical/python"]},
  "99": {"merge_into": 42}
}
```

## Architecture

The MCP server lives in `ebk/mcp/` with three modules:

- `server.py` -- creates the FastMCP instance, registers tools, and runs the stdio transport loop.
- `tools.py` -- tool implementations (`get_schema_impl`, `execute_sql_impl`, `update_books_impl`).
- `sql_executor.py` -- `ReadOnlySQLExecutor` with 3-layer security defense.

## See Also

- [Architecture](../development/architecture.md) -- overall system design
- [CLI Reference](../user-guide/cli.md) -- command documentation
- [Python API](../user-guide/api.md) -- programmatic library access
