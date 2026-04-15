# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**book-memex** (the directory is still `ebk/` on disk and GitHub; the Python package was renamed to `book_memex` in Phase 1). An eBook library manager evolving into the book-domain archive of the `*-memex` family. See `~/github/memex/CLAUDE.md` for ecosystem conventions and `docs/superpowers/specs/2026-04-15-book-memex-v1-design.md` for the v1 design. Phase 1 (rename + URI-addressable marginalia + soft-delete + CRUD surfaces) is complete; Phase 2 (content extraction + search + `ask_book`) and Phase 3 (browser reader) are future work.

Key capabilities as of Phase 1:
- SQLAlchemy + SQLite backend with FTS5 over metadata and extracted text.
- URI-addressable records: `book-memex://book/<unique_id>`, `book-memex://marginalia/<uuid>`, `book-memex://reading/<uuid>`.
- Soft delete across marginalia, reading sessions, and (schema-ready) all other memex-family records.
- REST (`/api/marginalia`, `/api/reading/sessions`, `/api/reading/progress`) and MCP tool surfaces over the same operations.
- arkiv export (`records.jsonl` + `schema.yaml`) including book, marginalia, reading kinds.
- Legacy `ebk` CLI alias with deprecation shim (to be removed post-v1).

## Development commands

```bash
make setup              # Create venv and install all deps
make install-dev        # Dev deps only

# Testing
pytest                                              # All tests (~1020+, 5 skipped)
pytest tests/test_server_marginalia.py -v           # Single file
pytest -k "marginalia or reading" -v                # Keyword filter
pytest --cov=book_memex --cov-report=term-missing   # Coverage

# Code quality
make lint               # flake8, mypy, pylint
make format             # black, isort

# Release
python -m build
twine upload dist/*
```

## Architecture

### Package layout

```
book_memex/
├── __init__.py
├── _ebk_alias.py            # `ebk` CLI deprecation shim (remove post-v1)
├── cli.py                    # Typer CLI (book-memex <group> <cmd>)
├── library_db.py             # Library class; fluent query API
├── server.py                 # FastAPI web server (~3800 lines)
├── search_parser.py
├── calibre_import.py
├── extract_metadata.py
├── config.py                 # ~/.config/ebk/config.json (path unchanged for backcompat)
├── core/
│   ├── uri.py                # book-memex URI builder/parser (pure Python)
│   └── soft_delete.py        # filter_active / archive / restore / hard_delete
├── db/
│   ├── models.py             # All SQLAlchemy ORM (Book, Marginalia, ReadingSession, ...)
│   ├── migrations.py         # CURRENT_SCHEMA_VERSION = 10
│   └── session.py            # init_db, FTS5 setup, run_all_migrations hook
├── mcp/
│   ├── server.py             # FastMCP stdio server; registers all tools
│   ├── tools.py              # Tool implementations (`*_impl` functions)
│   └── sql_executor.py       # Read-only SQL for execute_sql tool
├── services/
│   ├── import_service.py
│   ├── marginalia_service.py          # CRUD + scope + soft-delete
│   ├── reading_session_service.py     # Phase 1
│   ├── text_extraction.py             # Full-file extraction (Phase 2 evolves to per-segment)
│   ├── annotation_extraction.py       # Import highlights from EPUB/PDF annotations
│   ├── personal_metadata_service.py
│   ├── queue_service.py
│   ├── view_service.py
│   └── export_service.py
├── exports/
│   ├── arkiv.py              # Phase 1 - records.jsonl + schema.yaml
│   ├── echo_export.py, symlink_dag.py, multi_facet_export.py,
│   └── templates/            # Jinja HTML exports
├── plugins/                  # Plugin registry, hooks
└── similarity/               # Book similarity (unchanged in Phase 1)
```

### Key conventions

**URIs (Phase 1 addition).** Every memex-family record carries a `uri` property. Builders and parser live in `book_memex.core.uri`:
```python
from book_memex.core.uri import build_book_uri, parse_uri
parsed = parse_uri("book-memex://marginalia/abc123")  # → ParsedUri(kind="marginalia", id="abc123", ...)
```
MCP tools accept either a bare uuid or a full URI (see `_extract_uuid` in `mcp/tools.py`). REST endpoints currently take integer book ids (cross-archive URI addressing is MCP-only for now).

**Soft delete.** Add `archived_at TIMESTAMP NULL` to any new record table. Use `book_memex.core.soft_delete.filter_active(query, Model, include_archived=...)` in list queries. Service-layer `archive()` is idempotent (preserves original timestamp on re-archive). REST `DELETE ?hard=true` and MCP tools with `hard=True` opt into cascade delete.

**Marginalia scope.** `Marginalia.scope` is a Python property (not SQL-queryable) derived from book linkage + location:
- 0 books → `collection_note`
- 1 book, no location → `book_note`
- 1 book + location (page_number or position) → `highlight`
- 2+ books → `cross_book_note`

To filter by scope in list queries, the service fetches the DB-filtered rows then applies the scope predicate in Python. When `scope` is combined with `limit`, limit is applied AFTER scope-filtering (otherwise limit cuts off rows before they're classified).

**Migration pattern.** Each migration is a `migrate_X(library_path, dry_run=False) -> bool` function in `db/migrations.py`. Two-layer idempotency: `is_migration_applied(engine, name)` short-circuit plus per-column defensive checks before each `ALTER TABLE`. Migrations do NOT call `record_migration` themselves; `run_all_migrations` records them. `CURRENT_SCHEMA_VERSION` is bumped per migration. `init_db` runs `run_all_migrations` on every `Library.open()`.

**FTS5.** `books_fts` indexes book metadata (title, description, extracted_text truncated to 50k chars) via triggers. Porter + unicode61 tokenizer. Phase 2 will add a separate `book_content_fts` for per-segment content (the current per-file `ExtractedText` does not have FTS5).

### Key patterns

**Fluent Query API** (unchanged from pre-Phase 1):
```python
results = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_language("en")
    .order_by("title")
    .limit(20).all())
```

**REST / MCP parity.** Every REST endpoint has a matching MCP tool (and vice versa). REST uses integer book IDs and returns Pydantic response models. MCP uses URIs where applicable and returns plain dicts. Serialization shape is consistent: `uuid`, `uri`, ISO timestamps, nullable `archived_at`, `scope`/`book_ids`/`book_uris` where relevant.

**Progress semantics.** `POST /api/reading/progress` rejects backward percentage with 409 Conflict. `PATCH /api/reading/progress` always wins. MCP `set_reading_progress_impl(force=True)` is the `PATCH` equivalent.

## Database schema

Core tables: `books`, `authors`, `subjects`, `tags` (hierarchical), `files`, `covers`, `personal_metadata` (ratings, favorites, `reading_progress` percentage, `progress_anchor` JSON), `marginalia` (highlights + notes + cross-book observations, with `uuid`, `color`, `scope`-deriving columns), `reading_sessions` (with `uuid`, `start_anchor`, `end_anchor`), `concepts` / `book_concepts` / `concept_relations` (knowledge graph; not touched in Phase 1, flagged as federation-candidate).

All 9 memex-family tables have `archived_at` columns as of migration 9. Marginalia and reading_sessions additionally have UNIQUE `uuid` via migration 10. `books_fts` is the FTS5 mirror.

Library directory: `library.db`, `files/` (hash-prefixed), `covers/thumbnails/`.

## Test organization

Fixtures in `tests/conftest.py` and per-file: `temp_library`, `populated_library`, `fresh_library`, `lib_and_book`, `client_and_book` (FastAPI `TestClient` + `set_library(lib)`).

Key test files:
- `tests/test_uri.py`, `tests/test_soft_delete.py` (core helpers)
- `tests/test_migration_9_archived_at.py`, `tests/test_migration_10_uri_columns.py`
- `tests/test_model_new_columns.py` (ORM visibility + URI properties)
- `tests/test_marginalia_service_extended.py`, `tests/test_reading_session_service.py`
- `tests/test_server_marginalia.py`, `tests/test_server_reading.py` (REST via TestClient)
- `tests/test_mcp_marginalia_tools.py`, `tests/test_mcp_reading_tools.py` (MCP via direct impl calls)
- `tests/test_phase1_e2e.py` (REST ↔ MCP round-trip)
- `tests/test_exports.py::TestArkivExport`

Total: ~1020 passing, 5 skipped. Phase 1 modules sit at 89-100% coverage.

## Entry points

- **CLI**: `book-memex` → `book_memex.cli:app`. Legacy `ebk` → `book_memex._ebk_alias:main` (deprecation shim).
- **Python API**: `from book_memex.library_db import Library; lib = Library.open(path)`.
- **Web server**: `book-memex serve` → FastAPI on port 8000.
- **MCP server**: `book-memex-mcp-serve` (or `book-memex mcp-serve`) → stdio MCP.

## Phase 2 / 3 pending work

Phase 2 (content + search):
- Rename `TextChunk` → `BookContent` with segment_type / title / anchor / extractor_version / extraction_status.
- Drop `has_embedding` flag (per workspace "no embeddings in archives" convention).
- New `book_content_fts` virtual table + triggers.
- Content extractors for EPUB, PDF, TXT (per-chapter / per-page / whole-file).
- `GET /api/books/{id}/search` and `GET /api/search/content`; matching MCP tools.
- `ask_book(book_id, question)` MCP tool (FTS5 + LLM, no embeddings).
- `safe_fts_query()` helper for escaping user input.
- `book-memex reindex-content` CLI.

Phase 3 (browser reader):
- `/read/{book_id}` HTML shell loading EPUB.js or PDF.js.
- Highlight capture + paint-on-reload, progress sync, notes pane, in-book search UI, reading-session auto-tracking.

Phase-1 polish deferred (non-blocking, tracked):
- Book-level soft-delete propagation (archived_at exists on books/authors/etc. but is not yet filtered in `/api/books`, `Library.search`, non-arkiv exporters).
- Simplify `MarginaliaService` verb surface (legacy `delete` + new `archive`/`restore`/`hard_delete`).
- Migrate Concept graph to the federation layer (`memex`) once it exists.
