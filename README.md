# book-memex

> Renamed from `ebk` (previous name). The `ebk` CLI entrypoint is still available
> as a deprecation shim and will be removed in the release after v1.

**book-memex** is an eBook library manager and the book-domain archive of the
`*-memex` personal-data ecosystem. It stores book metadata, per-segment content,
reading marginalia (highlights and notes), and reading sessions in a SQLAlchemy +
SQLite database with FTS5 full-text search. It ships a Typer CLI, a fluent Python
API, a FastAPI web server with a browser-based EPUB/PDF reader, an MCP server for
LLM access, and exporters (arkiv JSONL, HTML, Hugo, OPDS, and more).

It is a thin domain archive by design: it stores and exposes books and reading
data. It does **not** compute embeddings or run semantic search; that belongs to
the `memex` federation layer (see `~/github/memex/CLAUDE.md`). The RAG-ready MCP
surface (per-segment FTS5 search, URI resolution, SQL) is what the federation
consumes.

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Browser Reader](#browser-reader)
- [Marginalia and Reading Sessions](#marginalia-and-reading-sessions)
- [MCP Server](#mcp-server)
- [Python API](#python-api)
- [Search Syntax](#search-syntax)
- [Architecture](#architecture)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **SQLAlchemy + SQLite backend** with a normalized schema and FTS5 full-text search.
- **Durable, URI-addressable records**: `book-memex://book/<unique_id>`,
  `book-memex://marginalia/<uuid>`, `book-memex://reading/<uuid>`.
- **Soft delete** across marginalia, reading sessions, and (schema-ready) other
  record kinds; hard delete is opt-in.
- **Text extraction and per-segment indexing**: PyMuPDF (with pypdf fallback) for
  PDFs, ebooklib for EPUBs, plus plaintext. Segments are anchored (EPUB CFI, PDF
  page+bbox, plaintext byte offset) and searchable via `book_content_fts`.
- **Hash-based deduplication**: SHA-256 file hashing. Same file is skipped; the
  same book in a different format is added as an additional format.
- **Cover extraction** and thumbnail generation.
- **FastAPI web server** with a REST API and a browser-based EPUB/PDF reader.
- **Marginalia and reading sessions**: URI-addressable highlights, notes, and
  reading-progress tracking, over both REST and MCP.
- **Exporters**: arkiv JSONL (the ecosystem interchange format), self-contained
  HTML catalog and single-file HTML app, Hugo Markdown, OPDS, CSV/JSON, and more.
- **MCP server** exposing `execute_sql`, `get_schema`, per-segment content search,
  URI resolution, and marginalia/reading tools.

---

## Installation

```bash
pip install book-memex
```

### From source

```bash
git clone https://github.com/queelius/book-memex.git
cd book-memex
pip install .
```

### Optional extras

```bash
pip install book-memex[mcp]    # MCP server (FastMCP)
pip install book-memex[docs]   # documentation tooling
pip install book-memex[dev]    # development + test dependencies
pip install book-memex[all]    # everything
```

> Requires Python 3.10+.

---

## Quick Start

```bash
# 1. Create a library
book-memex lib init ~/books

# 2. Add books (source path first, then the library path)
book-memex import add book.pdf ~/books --title "My Book" --authors "Some Author"
book-memex import folder ~/Downloads/ebooks ~/books        # bulk import a directory
book-memex import calibre ~/Calibre\ Library ~/books       # import a Calibre library

# 3. Search (query first, then the library path)
book-memex query search "title:python rating:>=4" ~/books

# 4. Browse in the web UI (and open the reader)
book-memex serve ~/books
# visit http://localhost:8000  (reader at /read/{book_id})
```

`book-memex serve` binds a loopback host by default. The REST API is
UNAUTHENTICATED and includes destructive operations, so binding a non-loopback
host requires an explicit flag and prints a warning. Do not expose it to an
untrusted network.

---

## CLI Usage

The CLI is a tree of sub-apps: `book-memex <group> <command>`.

```bash
# Library lifecycle
book-memex lib init|migrate|backup|restore|check

# Import
book-memex import add|folder|calibre|isbn|url|opds|arkiv

# Export
book-memex export json|csv|html|html-app|opds|goodreads|calibre|arkiv|echo

# Per-book operations
book-memex book info|status|progress|open|read|rate|favorite|tag|edit|delete|merge|bulk-edit|similar|export
book-memex book review add|list|show|edit|delete        # nested: structured reviews

# Notes / marginalia (also available over MCP)
book-memex note add|list|extract|export

# Tags
book-memex tag list|tree|add|remove|rename|delete|stats

# Reading queue
book-memex queue list|add|remove|move|clear|next

# Saved views (the views DSL)
book-memex view create|list|show|edit|add|remove|set|unset|export|import|delete

# Query
book-memex query search "<query>"
book-memex query stats
book-memex query sql "SELECT ..."

# Content extraction / indexing
book-memex extract
book-memex reindex-content
book-memex reindex-metadata

# Configuration (flag-based)
book-memex config --show
book-memex config --init
book-memex config --server-host 127.0.0.1 --server-port 8080 --library-path ~/books

# Servers
book-memex serve [LIBRARY]          # FastAPI web UI + reader
book-memex mcp-serve [LIBRARY_PATH] # MCP server over stdio
```

---

## Browser Reader

`book-memex serve` exposes a browser-based reader at `/read/{book_id}` for EPUB
and PDF, with highlight capture, reading-progress sync, and three themes (light,
dark, sepia). The reader libraries (EPUB.js, JSZip, PDF.js and its worker) are
vendored under `book_memex/server/static/vendor/` and served locally, so the
running instance needs no CDN or internet access. DRM-protected books cannot be
rendered.

---

## Marginalia and Reading Sessions

Marginalia are free-form, URI-addressable notes and highlights attachable to one
or more books (or to no book, as a collection note). Reading sessions track
reading events with start/end anchors, and per-book reading progress is stored on
`personal_metadata`. All of these are exposed over both the REST API
(`/api/marginalia`, `/api/reading/sessions`, `/api/reading/progress`) and MCP, and
all participate in soft delete so their URIs survive re-imports and round-trips
through other archives.

---

## MCP Server

```bash
book-memex mcp-serve ~/books
```

Configure in `.mcp.json`:

```json
{"mcpServers": {"book-memex": {"command": "book-memex", "args": ["mcp-serve", "/path/to/library"]}}}
```

The MCP surface includes the contract tools (`execute_sql`, `get_schema`) plus
domain tools for per-segment content search (`search_book_content`,
`search_library_content`, `get_segment`, `get_segments`), URI resolution, and
marginalia/reading operations. Per the ecosystem contract, the archive exposes
retrieval primitives and does not wrap LLM calls or compute embeddings.

---

## Python API

```python
from book_memex.library_db import Library

lib = Library.open("~/books")

# Fluent query API
results = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_language("en")
    .order_by("title")
    .limit(20)
    .all())

# Full-text search
hits = lib.search("title:python rating:>=4")
```

---

## Search Syntax

`book-memex query search` and `Library.search()` accept a small query language:

- **Field searches**: `title:Python`, `author:"Donald Knuth"`, `tag:programming`,
  `series:TAOCP`
- **Boolean operators**: implicit `AND`, explicit `OR`, and `NOT` / `-prefix`
  negation
- **Comparisons** (numeric fields): `rating:>=4`, `rating:3-5`
- **Exact filters**: `language:en`, `format:pdf`, `favorite:true`, `status:...`
- **Phrase searches**: `"machine learning"`
- FTS5-backed full-text search across titles, descriptions, and extracted text.

---

## Architecture

See [CLAUDE.md](CLAUDE.md) for the full package map. In brief: `cli.py` (Typer
router) and `server.py` (FastAPI) delegate to `services/`; `library_db.py` holds
the `Library` class and fluent query API; `core/` has DB-free building blocks
(URIs, soft delete, FTS5 sanitizer); `db/` holds the ORM, session setup, and
migrations; `exports/` has one exporter per target. The library directory contains
`library.db`, hash-prefixed `files/`, and `covers/thumbnails/`.

---

## Development

```bash
make setup          # create venv and install all deps
make install-dev    # dev deps only
pytest              # run the test suite
make lint           # flake8, mypy, pylint
make format         # black, isort
```

---

## Contributing

Issues and pull requests are welcome at
<https://github.com/queelius/book-memex>.

---

## License

MIT. See [LICENSE](LICENSE) and <https://github.com/queelius/book-memex>.
