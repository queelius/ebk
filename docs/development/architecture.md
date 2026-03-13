# Architecture

ebk's architecture and design patterns.

## Overview

ebk is built around several key architectural principles:

1. **SQLAlchemy ORM** - Database-first design with normalized schema
2. **Service Layer** - Business logic separated from data access
3. **Fluent API** - Method chaining for intuitive queries
4. **Configuration Management** - Centralized settings with CLI overrides
5. **MCP Integration** - AI assistant access via Model Context Protocol

## Core Components

### Database Layer (`ebk/db/`)

**Models** (`models.py`):
- `Book` - Core book entity with metadata
- `Author` - Author information with sort names
- `Subject` - Tags/subjects/categories
- `Tag` - Hierarchical user-defined tags (separate from subjects)
- `File` - Physical file records with hash-based deduplication
- `ExtractedText` - Full text from ebooks
- `TextChunk` - Overlapping chunks for search
- `Cover` - Cover images with thumbnails
- `PersonalMetadata` - Ratings, favorites, reading status
- `View` - Named view definitions (Views DSL)
- `ViewOverride` - Per-book metadata overrides within views
- `BooksFTS` - FTS5 virtual table for full-text search

**Session Management** (`session.py`):
- Database initialization and schema creation
- FTS5 index setup
- Connection pooling

**Migrations** (`migrations.py`):
- Sequential schema versioning via `schema_versions` table
- Idempotent migrations (check-before-apply pattern)
- Run with `ebk migrate` or `run_all_migrations()`
- Current schema version: 7

### Views DSL (`ebk/views/`)

Composable query language for named library subsets:

- **DSL Evaluator** (`dsl.py`) - Three-stage pipeline: `evaluate(view) = order(transform(select(library)))`
- **View Service** (`service.py`) - CRUD, membership, override management
- Supports: filters, set operations (union/intersect/difference), view references, raw SQL selectors
- Security: SQL selectors use read-only connections + SQLite authorizer whitelist
- Cycle detection for recursive view references with depth limits

### Service Layer (`ebk/services/`)

**Import Service** (`import_service.py`):
- Book import with metadata extraction
- Hash-based file deduplication
- Cover extraction and thumbnail generation
- Text extraction coordination

**Text Extraction** (`text_extraction.py`):
- PDF extraction (PyMuPDF, pypdf fallback)
- EPUB extraction (ebooklib)
- Plaintext handling
- Chunking for search

### MCP Server (`ebk/mcp/`)

Model Context Protocol server for AI assistant integration (e.g., Claude Code). Launched via `ebk mcp-serve [library-path]` over stdio transport.

**Tools:**

- `get_schema` - Introspects the database via SQLAlchemy's inspection API, returning tables, columns, foreign keys, and ORM relationships.
- `execute_sql` - Read-only SQL query execution with 3-layer security:
    1. Prefix check (only `SELECT`, no multi-statement)
    2. Read-only SQLite connection (`?mode=ro`)
    3. SQLite authorizer callback (whitelist: `SELECT`, `READ`, `FUNCTION`)
- `update_books` - Batch book metadata updates: scalar fields, collection operations (tags, authors, subjects), and book merging.

**Key files:**
- `server.py` - FastMCP instance creation and stdio transport runner
- `tools.py` - Tool implementations (`get_schema_impl`, `execute_sql_impl`, `update_books_impl`)
- `sql_executor.py` - `ReadOnlySQLExecutor` with defense-in-depth

### Configuration (`ebk/config.py`)

Three configuration sections:
- `ServerConfig` - Host, port, auto-open, page size
- `CLIConfig` - Verbosity, color, page size
- `LibraryConfig` - Default library path

Stored at: `~/.config/ebk/config.json`

### Web Server (`ebk/server.py`)

FastAPI-based REST API:
- Book CRUD operations
- Search and filtering
- Cover serving
- File downloads
- Reading status management

### CLI (`ebk/cli.py`)

Typer-based command-line interface:
- `db-*` commands for library management
- `serve` for web server
- `mcp-serve` for MCP server
- `config` for configuration management

## Design Patterns

### Fluent Query API

Method chaining for intuitive queries:

```python
results = (lib.query()
    .filter_by_language("en")
    .filter_by_author("Knuth")
    .order_by("title")
    .limit(20)
    .all())
```

### Hash-Based Deduplication

Files deduplicated using SHA256:
- Same file (same hash) → skipped
- Same book, different format → added as additional format
- Hash-prefixed storage: `files/ab/abc123.pdf`

### Configuration Hierarchy

CLI options > Config file > Defaults:

```python
# Load config with defaults
config = load_config()

# Override from CLI
if cli_host:
    config.server.host = cli_host
```

## Database Schema

Library directory structure:
```
my-library/
├── library.db              # SQLite database
├── files/                  # Hash-prefixed ebook storage
│   ├── ab/
│   │   └── abc123...pdf
│   └── cd/
│       └── cde456...epub
└── covers/                 # Cover images
    ├── ab/
    │   └── abc123.jpg
    └── thumbnails/
        └── abc123_thumb.jpg
```

## Key Technologies

- **SQLAlchemy** - ORM and database toolkit
- **SQLite** with **FTS5** - Database and full-text search
- **FastAPI** - Web framework for REST API
- **Typer** + **Rich** - CLI framework with colored output
- **PyMuPDF** / **pypdf** - PDF text extraction
- **ebooklib** - EPUB parsing
- **Pillow** - Image processing for covers
- **FastMCP** - Model Context Protocol server

## Extension Points

1. **Plugins** - Use plugin registry in `ebk/plugins/`
2. **Metadata Extractors** - Add to `integrations/metadata/`
3. **Export Formats** - Add to `ebk/exports/`
4. **MCP Tools** - Add tools to `ebk/mcp/server.py`

## See Also

- [Contributing Guide](contributing.md) - How to contribute
- [API Reference](api-reference.md) - Python API documentation
- Source code on [GitHub](https://github.com/queelius/ebk)
