# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**book-memex** (the directory is still `ebk/` on disk and GitHub; the Python package was renamed to `book_memex` in Phase 1). An eBook library manager evolving into the book-domain archive of the `*-memex` family. See `~/github/memex/CLAUDE.md` for ecosystem conventions and `docs/superpowers/specs/2026-04-15-book-memex-v1-design.md` for the v1 design. Phases 1 (rename + URI-addressable marginalia + soft-delete + CRUD surfaces), 2 (content extraction + FTS5 per-segment search), and 3 (browser reader) are all complete.

Key capabilities as of Phase 3:
- SQLAlchemy + SQLite backend with FTS5 over metadata and per-segment `book_content`.
- URI-addressable records: `book-memex://book/<unique_id>`, `book-memex://marginalia/<uuid>`, `book-memex://reading/<uuid>`.
- Soft delete across marginalia, reading sessions, and (schema-ready) all other memex-family records.
- REST (`/api/marginalia`, `/api/reading/sessions`, `/api/reading/progress`, `/api/books/{id}/search`, `/api/search/content`) and MCP tool surfaces over the same operations.
- Browser reader at `/read/{book_id}` for EPUB and PDF with highlight capture, progress sync, three themes.
- arkiv export (`records.jsonl` + `schema.yaml`) including book, marginalia, reading kinds.
- Legacy `ebk` CLI alias with deprecation shim (to be removed post-v1).

## Development commands

```bash
make setup              # Create venv and install all deps
make install-dev        # Dev deps only

# Testing
pytest                                              # All tests (~1089)
pytest tests/test_server_marginalia.py -v           # Single file
make test-file FILE=tests/test_server_marginalia.py # Same, via Makefile
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

Top-level `book_memex/` mixes a few single-file modules with a handful of packages. Treat `cli.py` (~6k LOC) and `server.py` (~4.3k LOC) as router files that delegate to services. Don't put logic there.

- **Entrypoints.** `cli.py` (Typer, `book-memex <group> <cmd>`), `library_db.py` (the `Library` class + fluent query API), `server.py` (FastAPI app: all REST endpoints, the `/read/{book_id}` reader shell, OPDS routes).
- **Single-purpose helpers.** `ident.py` (content hashing for durable IDs), `opds.py` (OPDS 1.2 catalog, ~750 LOC), `search_parser.py`, `extract_metadata.py`, `calibre_import.py`, `config.py` (reads `~/.config/ebk/config.json`; path unchanged for backcompat), `_ebk_alias.py` (legacy `ebk` CLI shim; remove post-v1).
- **`core/`**: pure-Python building blocks with no DB dependency. `uri.py` (URI builder/parser), `soft_delete.py` (`filter_active` / `archive` / `restore` / `hard_delete`), `fts.py` (FTS5 query sanitizer: `safe_fts_query`).
- **`db/`**: `models.py` (all SQLAlchemy ORM), `session.py` (init, FTS5 trigger setup, `run_all_migrations` hook), `migrations.py` (`CURRENT_SCHEMA_VERSION = 12` plus the `MIGRATIONS` list).
- **`services/`**: one module per domain operation. `marginalia_service`, `reading_session_service`, `personal_metadata_service`, `tag_service`, `queue_service`, `view_service`, `import_service`, `export_service`, `text_extraction` (full-file), `content_extraction/{epub,pdf,txt}.py` (per-segment adapters), `content_indexer` (persists segments, maintains `book_content_fts`), `annotation_extraction` (imports EPUB/PDF annotations).
- **`mcp/`**: `server.py` registers FastMCP tools (`execute_sql`, `get_schema`, `update_books`, plus ~20 domain tools); `tools.py` holds the `*_impl` functions that REST and MCP both call; `sql_executor.py` is the read-only SQL runner.
- **`server/static/` + `server/templates/`**: reader assets only (`reader.{js,css,html}`, `reader_error.html`). Everything else the web server needs lives inline in `server.py`.
- **`exports/`**: one exporter per target. `arkiv.py` (JSONL + `schema.yaml`), `hugo.py`, `jinja_export.py`, `html_library.py` + `html_utils.py` + `templates/`, `opds_export.py`, `echo_export.py`, `multi_facet_export.py`, `symlink_dag.py`, `zip.py`; `base_exporter.py` is the shared ABC.
- **`views/`**: SICP-style composable DSL (`{select, transform, order}` over `selector` / `predicate` / `transform` / `ordering` primitives) evaluated by `dsl.py` against the library. See the `views/dsl.py` docstring for the grammar; `view_service.py` persists saved views.
- **`plugins/`, `similarity/`**: plugin registry + hooks; book-similarity utilities (unchanged pre-Phase 1).

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

**FTS5.** Two independent FTS5 indexes, both porter + unicode61, both maintained by triggers:
- `books_fts` mirrors book metadata (title, description, authors joined in, extracted_text truncated to 50k chars). Drives `Library.search()` and `/api/books?q=`.
- `book_content_fts` is an external-content FTS5 virtual table (`content='book_content'`, `content_rowid='id'`). Indexed columns: `text` (mirrors `book_content.content`) and `title`; `book_id` and `content_id` are UNINDEXED join-back columns. Segment anchoring on `book_content` uses three source columns: `segment_type` (`chapter`, `page`, etc.), `segment_index` (ordinal within the book), and `anchor` (JSON: CFI for EPUB, page+bbox for PDF, byte offset for plain text). Drives `/api/books/{id}/search`, `/api/search/content`, and the `search_book_content` / `search_library_content` / `get_segments` MCP tools. Populated on import via `services/content_indexer.py`; re-indexable via `book-memex reindex-content`.

Always route user-supplied FTS5 queries through `book_memex.core.fts.safe_fts_query` before passing to SQLite; it escapes quotes and neutralizes special syntax.

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

Core tables: `books`, `authors`, `subjects`, `tags` (hierarchical), `files`, `covers`, `personal_metadata` (ratings, favorites, `reading_progress` percentage, `progress_anchor` JSON), `marginalia` (highlights + notes + cross-book observations, with `uuid`, `color`, `scope`-deriving columns), `reading_sessions` (with `uuid`, `start_anchor`, `end_anchor`), `book_content` (per-segment text with `segment_kind` + `segment_ref` anchors; Phase 2), `views` / `view_items` (migration 7 saved views), `concepts` / `book_concepts` / `concept_relations` (knowledge graph; flagged as federation-candidate).

All memex-family record tables have `archived_at` columns (migration 9). Marginalia and reading_sessions have UNIQUE `uuid` (migration 10). `books_fts` mirrors book metadata; `book_content_fts` mirrors per-segment content (migrations 11+12).

Library directory: `library.db`, `files/` (hash-prefixed), `covers/thumbnails/`.

## Test organization

Fixtures in `tests/conftest.py` and per-file: `temp_library`, `populated_library`, `fresh_library`, `lib_and_book`, `client_and_book` (FastAPI `TestClient` + `set_library(lib)`). Phase 2 extractor tests lean on `sample_epub` (3-chapter in-memory EPUB built with `ebooklib`) and `sample_pdf` (3-page reportlab PDF), both defined in the root `conftest.py`.

Key test files:
- `tests/test_uri.py`, `tests/test_soft_delete.py` (core helpers)
- `tests/test_migration_9_archived_at.py`, `tests/test_migration_10_uri_columns.py`
- `tests/test_model_new_columns.py` (ORM visibility + URI properties)
- `tests/test_marginalia_service_extended.py`, `tests/test_reading_session_service.py`
- `tests/test_server_marginalia.py`, `tests/test_server_reading.py` (REST via TestClient)
- `tests/test_mcp_marginalia_tools.py`, `tests/test_mcp_reading_tools.py` (MCP via direct impl calls)
- `tests/test_phase1_e2e.py` (REST ↔ MCP round-trip)
- `tests/test_exports.py::TestArkivExport`

Total: 1089 tests. Phase 1-3 modules sit at 89-100% coverage. Run a single file with `make test-file FILE=tests/test_marginalia_service_extended.py` or directly via `pytest tests/<file>.py -v`.

## Entry points

- **CLI**: `book-memex` → `book_memex.cli:app`. Legacy `ebk` → `book_memex._ebk_alias:main` (deprecation shim).
- **Python API**: `from book_memex.library_db import Library; lib = Library.open(path)`.
- **Web server**: `book-memex serve` → FastAPI on port 8000.
- **MCP server**: `book-memex mcp-serve [LIBRARY_PATH]` → stdio MCP. Path falls back to `~/.config/ebk/config.json` `library.default_path` when omitted.

## Reader (Phase 3)

Browser-based EPUB/PDF reader at `/read/{book_id}` served by `book_memex.server`:

- **Endpoints.** `GET /read/{book_id}` renders the reader shell and inline-embeds book metadata in `window.BOOK`; `GET /read/{book_id}/file` streams the raw EPUB/PDF. The client pulls existing highlights and last-known progress via the Phase 1 REST surface (`/api/marginalia?book_id=...`, `/api/reading/progress?book_id=...`).
- **Static assets** at `book_memex/server/static/` (`reader.js` ~850 LOC, `reader.css`).
- **Templates** at `book_memex/server/templates/` (`reader.html`, `reader_error.html`).
- **Adapter pattern.** `reader.js` defines a `ReaderAdapter` interface with two implementations: `EpubAdapter` wraps EPUB.js 0.3.93 + JSZip 3.10.1 (from CDN), `PdfAdapter` wraps PDF.js 4.0.379 (from CDN). The shell chooses per-book based on MIME type.
- **Server-side state.** All reader state is persisted via the existing Phase 1/2 REST endpoints. Highlights go to `Marginalia` (`POST /api/marginalia`), progress to `PersonalMetadata.progress_anchor` + `reading_progress` (`PATCH /api/reading/progress`), sessions to `ReadingSession` (`POST /api/reading/sessions`). The reader does not introduce new state tables or endpoints.
- **Themes.** Three themes (light, dark, sepia). Selection is stored client-side in `localStorage.bookMemexReaderTheme`. CSS custom properties drive the shell; EPUB.js `themes.register()` + `themes.select()` propagates into the rendered EPUB iframe.
- **Limitations** (see "Known limitations" below).

## Known limitations

- **DRM-protected ebooks cannot be rendered.** EPUB.js and PDF.js do not decrypt Adobe DRM, Amazon KFX, or similar. Out of scope forever; use original vendor readers.
- **Mobile touch UX is functional but not polished.** Selection and toolbar work on touch, but highlight handles and long-press behavior are not tuned for small screens.
- **PDF highlights are not visually re-painted in v1.** PDF highlight captures are stored server-side (with CFI-like anchors) but PdfAdapter does not re-render them as overlays on PDF pages. EPUB highlights paint correctly on reload via EPUB.js annotations.
- **No offline/PWA support.** No service worker; reading requires a live connection to the `book-memex serve` instance.

## Deferred post-v1

- Book-level soft-delete propagation (archived_at exists on books/authors/etc. but is not yet filtered in `/api/books`, `Library.search`, non-arkiv exporters).
- Simplify `MarginaliaService` verb surface (legacy `delete` + new `archive`/`restore`/`hard_delete`).
- Migrate Concept graph to the federation layer (`memex`) once it exists.
- PDF highlight overlay rendering (see limitations above).
- Mobile touch polish.
- Offline reader (service worker / PWA).
