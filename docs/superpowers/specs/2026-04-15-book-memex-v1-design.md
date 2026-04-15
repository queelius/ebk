# book-memex v1: Reader, Marginalia, and Content Search

**Date**: 2026-04-15 (revised after codebase audit)
**Status**: Draft (pending review)
**Scope**: Rename `ebk` to `book-memex` and extend it with URI-addressable marginalia, a browser-based reader, content-level search, and `ask_book`.
**Context**: Part of the coordinated memex-family rename. See `~/github/memex/CLAUDE.md` for ecosystem conventions and `~/github/memex/meta-memex/docs/uri-scheme.md` for the URI spec.

**Revision note**: The first draft of this spec proposed creating new tables (`Highlight`, `Note`, `ReadingSession`, `Progress`, `BookContent`) that either already exist in ebk or have close analogues. This revision preserves ebk's existing schema where possible and extends it rather than duplicating. Findings from the codebase audit are summarized in §2.2.

## 1. Summary

`ebk` today manages eBook metadata, reading marginalia (highlights + notes + cross-book observations), reading sessions, extracted text, and a concept knowledge graph. It exposes a FastAPI web server (library manager), an MCP server, a Typer CLI, Calibre import, and OPDS export. What it does NOT have: a reader UI, URI-addressable records, soft delete, content-level FTS5, an `ask_book` tool, or compliance with the "no embeddings in archives" workspace convention.

This design:

1. Renames `ebk` to `book-memex`, aligning it with the memex-family naming and URI scheme.
2. Adds URIs to existing records (Book, Marginalia, ReadingSession) so they can participate in cross-archive trails.
3. Extends Marginalia with a `color` field (highlight variants) and the `archived_at` soft-delete column.
4. Extends ReadingSession with optional `start_anchor`/`end_anchor` for reader-driven sessions, keeping existing `pages_read`/`comprehension_score` for the academic use case.
5. Adds `progress_anchor` to PersonalMetadata so reading progress can carry a precise anchor, not just a percentage.
6. Evolves TextChunk into BookContent (rename + schema refinement) with chapter/page segmentation, extractor versioning, and extraction status. Drops `has_embedding` per workspace convention.
7. Adds FTS5 over book content (new `book_content_fts` virtual table).
8. Builds a browser-based EPUB and PDF reader served from the existing FastAPI server with native highlight capture and progress sync.
9. Adds `ask_book(book_id, question)` using FTS5 + LLM retrieval (no embeddings).
10. Adds soft delete (`archived_at`) to all record tables.
11. Leaves the Concept / BookConcept / ConceptRelation knowledge graph untouched in v1 and flags it as a candidate for migration to the federation layer (`memex`) in a future release.

## 2. Background

### 2.1 The memex family (from the workspace `CLAUDE.md`)

Each archive satisfies a 7-item contract (SQLite+FTS5, MCP server with `run_sql` + `get_schema` + domain tools, thin admin CLI, import and export pipelines, durable record IDs, marginalia, arkiv export) plus three workspace conventions:

1. Soft delete on all records (`archived_at TIMESTAMP NULL`).
2. Archives do not compute embeddings. They expose a RAG-ready MCP surface; the federation layer (`memex`, formerly `meta-memex`) owns embeddings and cross-archive vector search.
3. Positions within a record use URI fragments, not new URI kinds. Records get URI kinds.

Optionally, archives may ship `ask_<domain>` using FTS5 + LLM, no embeddings required.

### 2.2 What ebk already has (verified against the code)

**Models** (`ebk/db/models.py`):

| Model | Relevant fields | Notes |
|---|---|---|
| Book | Integer `id` PK, `unique_id` (hash string), title, metadata, timestamps | Has stable hash-based `unique_id`, Integer PK for FK relations |
| Author, Subject, Tag, Contributor, Identifier | Standard metadata | Hierarchical Tag with path-based structure |
| File | Integer `id`, book_id FK, path, format, `file_hash` (SHA256), text_extracted flag | Books have multiple Files (multi-format) |
| Cover | Integer id, book_id FK, path, is_primary | |
| ExtractedText | file_id FK (1:1), `content` TEXT, `content_hash` | Whole-file extracted text |
| TextChunk | file_id FK, chunk_index, content, start_page, end_page, `has_embedding` | Word-level chunks; has_embedding VIOLATES workspace convention |
| Concept, BookConcept, ConceptRelation | Full knowledge graph with PageRank | Out-of-scope for v1; flag for possible federation migration |
| PersonalMetadata | book_id FK (1:1), rating, `reading_status`, `reading_progress` (0-100), favorite, queue_position, dates | Progress is a percentage scalar; no anchor |
| Marginalia | `id` Integer, `content`, `highlighted_text`, `page_number`, `position` (JSON), `category`, `pinned`, timestamps, many-to-many with Book via `marginalia_books` | Scope derived from context: 0 books = collection, 1 book + location = highlight, 1 book no location = book-level note, 2+ books = cross-book. Flexible. |
| ReadingSession | `id` Integer, book_id FK, `start_time`, `end_time`, `pages_read`, `comprehension_score` | Academic-session-tracking semantics. No anchors. |
| View, ViewOverride | View DSL | Non-destructive lenses. Out of v1 scope. |

**Services** (`ebk/services/`):

- `import_service.py`: import pipeline (Calibre, filesystem, metadata extraction)
- `text_extraction.py`: full-text extraction to `ExtractedText`, chunking to `TextChunk`
- `annotation_extraction.py`: reads highlights/notes from EPUB/PDF annotations (import of existing annotations)
- `marginalia_service.py`: CRUD for Marginalia (create, get, list_for_book, update, delete)
- `personal_metadata_service.py`: CRUD for PersonalMetadata
- `queue_service.py`: reading queue management
- `tag_service.py`, `view_service.py`, `export_service.py`

**MCP tools** (`ebk/mcp/tools.py`): three tools only: `get_schema`, `execute_sql` (SQL over the Library DB), `update_books`.

**FastAPI server** (`ebk/server.py`, ~3600 lines): library manager SPA and JSON API. Endpoints cover book list/detail/update/delete, files, covers, stats, metadata search (FTS5 over `books_fts`), views, and import. No reader, no marginalia endpoints, no reading-state endpoints, no content-level search endpoints.

**FTS5** (`ebk/db/session.py`): `books_fts` with columns (book_id UNINDEXED, title, description, extracted_text truncated to 50k chars), porter+unicode61. No `book_content_fts` or `marginalia_fts`.

**Migrations** (`ebk/db/migrations.py`): at schema version 8. Migration 7 added `views`/`view_overrides`. Migration 8 converted `annotations` → `marginalia`. All structural; no `archived_at` anywhere.

**Formats supported for extraction**: EPUB (via `ebooklib` + BeautifulSoup), PDF (via `pypdf` / `fitz`), TXT/MD. Cover extraction: EPUB, PDF.

### 2.3 What changes in v1

- **Rename** (§10): package, CLI entrypoint, MCP identity, URI prefix.
- **Schema extensions** (§4): add `archived_at` everywhere; add `uuid` on Marginalia, ReadingSession, and Book URI builders; add `color` on Marginalia; add `start_anchor`/`end_anchor` on ReadingSession; add `progress_anchor` on PersonalMetadata.
- **TextChunk becomes BookContent** (§4.5): rename + refine fields (segment_type, title, anchor JSON, extractor_version, extraction_status), drop `has_embedding`.
- **Content FTS5** (§5.4): new `book_content_fts` virtual table over BookContent.
- **Reader subsystem** (§8): new, green-field.
- **Endpoint expansion** (§6): marginalia CRUD, reading state, content search, reader shell and file streaming.
- **MCP tool expansion** (§7): marginalia, reading, content search, `ask_book`.
- **Content extraction evolves** (§5): existing `text_extraction.py` extends to produce segment-level records (BookContent) alongside the whole-file ExtractedText.
- **has_embedding removal**: drops the column from TextChunk/BookContent per workspace convention.

### 2.4 What is explicitly NOT touched in v1

- **Concept knowledge graph** (`Concept`, `BookConcept`, `ConceptRelation`). Remains in place, untouched. Flagged as federation-layer candidate. The graph is too interesting to delete and arguably does not belong in a single archive; federating it later is the right call.
- **Views and ViewOverride**. Stay as-is. The view DSL is orthogonal.
- **Queue service, tag service**. Unchanged.

## 3. Scope

### 3.1 In scope

1. Rename `ebk` to `book-memex`: Python package, CLI entrypoint (`book-memex`), MCP server identity, URI prefix (`book-memex://`).
2. Schema extensions (soft delete, UUIDs for URI, color for marginalia, anchors for reading sessions, progress anchor on personal metadata).
3. TextChunk → BookContent rename and field refinement; drop `has_embedding`.
4. Segment-level content extraction for EPUB and PDF (chapter-based for EPUB, page-based for PDF).
5. `book_content_fts` virtual table + triggers.
6. Browser-based reader at `GET /read/{book_id}` using EPUB.js for EPUB and PDF.js for PDF.
7. Highlight capture, storage (as Marginalia with location scope), and re-painting on reload.
8. Reading progress sync (last-known anchor on PersonalMetadata).
9. Reading sessions started and ended by the reader UI (with anchors).
10. Marginalia CRUD via REST and MCP.
11. Reading state CRUD via REST and MCP.
12. Within-book search and cross-library content search endpoints.
13. `ask_book(book_id, question)` MCP tool using FTS5 + LLM retrieval.
14. `safe_fts_query()` helper for escaping user input.
15. Soft delete (`archived_at`) on: books, authors, subjects, tags, marginalia, reading_sessions, files, covers, personal_metadata.
16. `restore` endpoint on every soft-deletable resource.
17. arkiv export extended with Marginalia, ReadingSession, BookContent records (as RAG surface) with URIs.
18. New CLI commands: `book-memex extract <book_id>`, `book-memex reindex-content [--book <id>|--all]`, `book-memex delete --hard` flag.

### 3.2 Out of scope (deferred to future work)

- Semantic / embedding-based search. Belongs to the federation layer.
- Audiobook support. Deferred.
- OCR for scanned PDFs without a text layer. Detected and flagged, but not OCRed.
- Edition grouping (multi-format same book). Deferred.
- Multi-language search (porter stemmer is English-only).
- Highlight-aware cross-library search. Easy to add later.
- Notes-on-highlights (threaded marginalia). v2 feature.
- Migrating Concept/BookConcept/ConceptRelation to the federation layer. Flagged, not done.
- Shared / collaborative reading. Out of scope forever.
- DRM-protected ebooks. Out of scope forever.
- CSRF hardening and authentication. Web server remains localhost-scoped.
- Accessibility polish for the reader UI. Worth doing but not in v1.
- Rich reader features: dictionaries, translation, text-to-speech, annotation exports. Deferred.

## 4. Data model

### 4.1 Soft delete (retrofit)

Add `archived_at TIMESTAMP NULL` to: `books`, `authors`, `subjects`, `tags`, `files`, `covers`, `personal_metadata`, `marginalia`, `reading_sessions`, and the new `book_content` (see §4.5). Every list query and every MCP list tool filters `WHERE archived_at IS NULL` by default. `include_archived=true` exposes archived records. A `restore` endpoint / tool sets `archived_at = NULL`.

Hard delete is opt-in: `DELETE /api/.../{id}?hard=true` and `delete_*` MCP tools with `hard=True` perform the pre-existing cascade delete.

### 4.2 Marginalia (extended, existing)

Add columns:

- `uuid VARCHAR(36) UNIQUE NOT NULL` (generated at create; populated for existing rows via migration)
- `color VARCHAR(7) NULL` (hex color for highlights; null for book-level or cross-book notes)
- `archived_at TIMESTAMP NULL`

Existing fields preserved: `id`, `content`, `highlighted_text`, `page_number`, `position` (JSON), `category`, `pinned`, `created_at`, `updated_at`, M2M with Books via `marginalia_books`.

The position JSON already accepts arbitrary anchor shapes (`{char_offset, cfi, x, y, ...}`). For reader-created marginalia, position JSON will carry:

- EPUB: `{"cfi": "epubcfi(/6/4[chap01]!/4/2/1:120,/4/2/1:245)"}`
- PDF: `{"page": 47, "rects": [[x, y, w, h], ...]}`
- Text fallback (from annotation import): `{"text_before": "...", "match": "...", "text_after": "..."}`

URI: `book-memex://marginalia/<uuid>`

Scope derivation remains as today:
- 0 books in `marginalia_books`: collection-scoped note
- 1 book + location data (page_number or position): location-scoped (a "highlight")
- 1 book, no location: book-level note
- 2+ books: cross-book note

No Highlight/Note split. A client wanting just highlights queries `WHERE position IS NOT NULL OR page_number IS NOT NULL`.

### 4.3 ReadingSession (extended, existing)

Add columns:

- `uuid VARCHAR(36) UNIQUE NOT NULL` (generated at create; backfilled for existing rows)
- `start_anchor JSON NULL` (anchor where the session started)
- `end_anchor JSON NULL` (anchor where the session ended)
- `archived_at TIMESTAMP NULL`

Existing fields preserved: `id`, `book_id`, `start_time`, `end_time`, `pages_read`, `comprehension_score`. The reader UI creates sessions with anchors and leaves `pages_read`/`comprehension_score` NULL; academic-flow sessions (existing use case) can still use those fields.

URI: `book-memex://reading/<uuid>`

### 4.4 PersonalMetadata (extended, existing)

Add column:

- `progress_anchor JSON NULL` (last-known anchor for the reader to resume from)

Existing `reading_progress INTEGER` (0-100 percentage) is preserved and remains the user-visible progress scalar. `progress_anchor` carries the precise anchor for the reader's resume feature.

### 4.5 BookContent (renamed from TextChunk)

Rename `text_chunks` → `book_content`. Drop `has_embedding` column (per workspace convention). Add columns:

- `segment_type VARCHAR(20) NOT NULL` (`'chapter'` | `'page'` | `'text'`)
- `segment_index INTEGER NOT NULL` (replaces `chunk_index`; semantic rename)
- `title VARCHAR(500) NULL` (chapter title when extractable)
- `anchor JSON NOT NULL` (`{"cfi": "epubcfi(...)"}` for EPUB, `{"page": N}` for PDF, `{"offset": 0, "length": N}` for TXT)
- `extractor_version VARCHAR(50) NOT NULL` (`"epub-v1"`, `"pdf-v1"`, `"txt-v1"`)
- `extraction_status VARCHAR(20) NOT NULL DEFAULT 'ok'` (`'ok'` | `'no_text_layer'` | `'partial'`)
- `archived_at TIMESTAMP NULL`

Preserved fields: `id`, `file_id`, `content`, `start_page`, `end_page`.

Unique index: `(file_id, segment_type, segment_index)`.

Note: the deterministic-ID discussion from the original spec does not require a string PK. The existing Integer `id` is fine because segments are referenced internally. Public addressability of book positions happens through Book URI fragments (see §4.7), not segment URIs. What matters is that `(file_id, segment_type, segment_index)` is stable across re-extraction so FTS5 and the reader can resolve positions consistently.

### 4.6 FTS5 for content (new)

```sql
CREATE VIRTUAL TABLE book_content_fts USING fts5(
    text,
    title,
    book_id UNINDEXED,
    content_id UNINDEXED,
    content='book_content',
    content_rowid='id',
    tokenize='porter unicode61'
);
```

Plus `AFTER INSERT`, `AFTER UPDATE`, `AFTER DELETE` triggers on `book_content` synchronizing with `book_content_fts`. Mirrors the pattern used for `books_fts`.

The existing `books_fts` remains for metadata search. `book_content_fts` is the new index for `ask_book` and content search.

### 4.7 URI surface (after v1)

| Kind | Format | Source |
|---|---|---|
| Book | `book-memex://book/<unique_id>` | Book.unique_id (hash-based, already durable) |
| Marginalia | `book-memex://marginalia/<uuid>` | Marginalia.uuid (new column) |
| Reading session | `book-memex://reading/<uuid>` | ReadingSession.uuid (new column) |

No Highlight, Note, Progress, or BookContent URI kinds. Marginalia is the single kind for annotations. Progress is state on PersonalMetadata. BookContent is internal; positions use Book URI fragments:

```
book-memex://book/<unique_id>#epubcfi(/6/4[chap03]!/4)    (chapter start, EPUB)
book-memex://book/<unique_id>#page=47                     (PDF page)
book-memex://book/<unique_id>#cfi-range=.../to/...        (passage range, EPUB)
book-memex://book/<unique_id>#text-match=...              (fallback anchor)
```

Note: Book.unique_id is already a hash-derived string (32 characters, per the model definition). Using it directly gives durable URIs without needing to add a separate `sha256:` prefix. If it turns out unique_id is not file-hash (it might be a combined hash of title+author+etc. in practice), the URI builder may prefix it with a scheme tag; that decision is captured in the implementation task. Either way, the surface is one stable URI per Book.

### 4.8 Concept graph (out of scope, flagged)

`Concept`, `BookConcept`, `ConceptRelation` are preserved as-is. Not given URIs, not soft-deleted, not touched. Rationale: the concept graph is structurally closer to what the federation layer (`memex`) will want to own (cross-archive knowledge graph). Migrating it is its own project; for v1 we neither extend nor delete it.

A follow-up spec can move the concept graph to the federation layer or formalize it within book-memex.

## 5. Content extraction

### 5.1 Relationship to existing `text_extraction.py`

ebk's `text_extraction.py` currently extracts whole-file text to `ExtractedText.content` and creates word-level chunks in `TextChunk`. The v1 refinement:

- Keeps ExtractedText as-is (whole-file archive for backward compat and for `books_fts` indexing).
- Replaces the word-chunking logic with semantic-chunking (chapter for EPUB, page for PDF, whole-file for TXT) and writes to the renamed `book_content` table.

### 5.2 Extractor interface

```python
# book_memex/services/content_extraction.py  (new, or refactor text_extraction.py)
class Extractor(Protocol):
    version: str
    def supports(self, book_format: str) -> bool: ...
    def extract(self, file_path: Path) -> Iterator[Segment]: ...

@dataclass
class Segment:
    segment_type: str        # 'chapter' | 'page' | 'text'
    segment_index: int
    title: str | None
    anchor: dict
    text: str
    start_page: int | None
    end_page: int | None
    extraction_status: str   # 'ok' | 'no_text_layer' | 'partial'
```

Extractors are dispatched by `Book.primary_file.format`:

- `epub`: `EpubExtractor`, version `"epub-v1"`. Uses `ebooklib` to walk spine; one segment per spine item; title from HTML `<h1>` or TOC; anchor is the chapter-root CFI.
- `pdf`: `PdfExtractor`, version `"pdf-v1"`. Uses `pypdf` (already a dependency) to extract per-page text; anchor is `{"page": N}`. Detects empty text layers and sets `extraction_status = 'no_text_layer'`; does not block import.
- `txt`: `TxtExtractor`, version `"txt-v1"`. Single segment with whole file.

### 5.3 Extraction trigger

- On import via `import_service.py`: extract content synchronously after cover generation. (Currently `text_extraction.py` is called but writes whole-file text; v1 wires the new segment extraction in alongside.)
- `book-memex extract <book_id>`: manual extraction, useful for debugging.
- `book-memex reindex-content [--book <id> | --all]`: re-extract all books or one book, matching by `extractor_version`. Re-extraction clears old `book_content` rows for the file and inserts fresh ones. `book_content_fts` triggers sync automatically.

### 5.4 Quality expectations

v1 ships "useful, not comprehensive":

- EPUB: one segment per spine item (coarse chapter boundaries). Nested TOCs are not split.
- PDF: one segment per page, no header/footer stripping, no multi-column reading-order detection.
- Footnotes, endnotes, TOCs are included in segment text.
- Scanned PDFs without a text layer produce empty segments with `extraction_status = 'no_text_layer'`; surfaced in the UI and MCP schema.
- Some EPUBs will extract badly. Acceptable for v1; flag and iterate.

Extractor versioning enables selective re-extraction as quality improves.

## 6. FastAPI endpoints

Existing book/metadata endpoints are preserved. New endpoints:

### 6.1 Reader

```
GET  /read/{book_id}                       -> HTML shell (EPUB.js or PDF.js based on primary_file.format)
GET  /books/{book_id}/file                 -> streams primary file with correct Content-Type and Range
GET  /books/{book_id}/metadata.json        -> minimal metadata for the reader
```

### 6.2 Marginalia

```
GET    /api/marginalia?book_id=...&scope=...&include_archived=false
POST   /api/marginalia                     {book_ids, content?, highlighted_text?, page_number?, position?, color?, category?}  -> {uuid, uri, ...}
PATCH  /api/marginalia/{uuid}              {content?, color?, category?, pinned?}
DELETE /api/marginalia/{uuid}?hard=false
POST   /api/marginalia/{uuid}/restore
```

The `scope` query parameter filters by derived scope: `highlight` (1 book + location), `book_note` (1 book no location), `collection_note` (0 books), `cross_book_note` (2+ books). Computed at query time from the existing schema.

### 6.3 Reading state

```
GET  /api/reading/progress?book_id=...     -> {book_id, anchor, percentage, updated_at}
POST /api/reading/progress                 {book_id, anchor, percentage}   (reader auto-sync; accepts only if new anchor is at or after current)
PATCH /api/reading/progress                {book_id, anchor, percentage}   (explicit set; always wins)

POST /api/reading/sessions/start           {book_id, start_anchor?}  -> {uuid, uri, ...}
POST /api/reading/sessions/{uuid}/end      {end_anchor?}
GET  /api/reading/sessions?book_id=...&limit=50
DELETE /api/reading/sessions/{uuid}?hard=false
POST /api/reading/sessions/{uuid}/restore
```

`POST /api/reading/progress` writes to `PersonalMetadata.progress_anchor` and (optionally) updates `PersonalMetadata.reading_progress` if the percentage is supplied.

### 6.4 Content search

```
GET /api/books/{book_id}/search?q=...&limit=50
    -> [{segment_type, segment_index, title, anchor, fragment, snippet, rank}, ...]

GET /api/search/content?q=...&limit=50
    -> [{book_id, book_title, book_uri, segment_type, segment_index, anchor, fragment, snippet, rank}, ...]
```

Each result includes the raw `anchor` (JSON) and a `fragment` string ready to append to the book URI. Snippets via FTS5 `snippet()` with `<mark>` markers.

### 6.5 Query safety

`safe_fts_query()` helper escapes FTS5 operators by default. An `?advanced=true` opt-in exposes raw FTS5 syntax. Lives alongside the existing `search_parser.py`.

## 7. MCP tool additions

The existing tools (`get_schema`, `execute_sql`, `update_books`) stay. New tools:

### 7.1 Marginalia

```
list_marginalia(book_id=None, scope=None, limit=50, include_archived=False) -> list[Marginalia]
get_marginalia(uuid) -> Marginalia
add_marginalia(book_uris: list[str], content=None, highlighted_text=None, page_number=None, position=None, color=None, category=None) -> {uuid, uri, ...}
update_marginalia(uuid, content=None, color=None, category=None, pinned=None) -> Marginalia
delete_marginalia(uuid, hard=False) -> {status, ...}
restore_marginalia(uuid) -> Marginalia
```

`add_marginalia` accepts a list of book URIs (`book-memex://book/<unique_id>`), parsed into Book rows, linked via `marginalia_books`. A single entry means book-scoped; multiple means cross-book.

### 7.2 Reading state

```
get_reading_progress(book_id) -> Progress | None
set_reading_progress(book_id, anchor, percentage=None) -> Progress
start_reading_session(book_id, start_anchor=None) -> {uuid, uri, ...}
end_reading_session(session_uuid, end_anchor=None) -> ReadingSession
list_reading_sessions(book_id, limit=50, include_archived=False) -> list[ReadingSession]
delete_reading_session(uuid, hard=False) -> {status, ...}
restore_reading_session(uuid) -> ReadingSession
```

### 7.3 Content access and search

```
search_book_content(book_id, query, limit=20) -> list[{segment_type, segment_index, title, anchor, fragment, snippet, rank}]
search_library_content(query, limit=20)       -> list[{book_id, book_uri, title, anchor, fragment, snippet, rank}]
get_segment(book_id, segment_type, segment_index) -> BookContent
get_segments(book_id, limit=50, offset=0)     -> list[BookContent]   # RAG-ready pagination
```

### 7.4 `ask_book`

```
ask_book(book_id, question, k=8, model=None) -> {answer, citations, segments_used}
```

Implementation:

1. LLM extracts 3-5 keyword phrases from `question`.
2. FTS5 over `book_content_fts` filtered by `book_id`, top-k segments by BM25.
3. Build a prompt: question + each segment's text with its book-URI fragment as a citation marker.
4. Call the LLM with citation-required instructions.
5. Parse citations; return `{answer, citations: [{fragment, segment_index}], segments_used}`.

LLM provider configured via ebk config (reuses existing pattern). Failure modes: empty results return `answer=None`; no LLM configured returns a clear error; no text layer returns a flag.

## 8. Reader implementation

Green-field subsystem. No existing code.

### 8.1 Template

`GET /read/{book_id}` returns `book_memex/server/templates/reader.html` (Jinja2). It:

- Loads EPUB.js (pinned version) for EPUB or PDF.js for PDF.
- Loads `reader.js` (static asset at `book_memex/server/static/reader.js`).
- Injects `window.BOOK = {id, unique_id, format, file_url, title, author}`.
- Provides `#viewer`, `#margin` (notes pane), `#search-panel` divs.

### 8.2 Reader controller (`reader.js`)

Responsibilities:

- Initialize EPUB.js or PDF.js against `window.BOOK.file_url`.
- On load: fetch `/api/reading/progress?book_id=...`, resume at the anchor.
- On load: fetch `/api/marginalia?book_id=...&scope=highlight`, paint each.
- On text selection + "Highlight" action: `POST /api/marginalia` with book_ids=[book.unique_id], position={cfi:…} or {page:…,rects:…}, highlighted_text=selected, color=yellow.
- On `relocated` event (debounced 2s): `POST /api/reading/progress`.
- On Ctrl-F / Cmd-F: show search panel, wire to `/api/books/{id}/search`.
- On result click: jump to anchor via `rendition.display(cfi)` (EPUB) or page navigate (PDF).
- On highlight click: open notes pane, allow editing `content`, `category`, `color`.
- On start/unload: start/end reading session.

Estimated size: ~400 lines of JS.

### 8.3 Format differences

- EPUB: EPUB.js yields CFIs directly on selection; paint via `rendition.annotations.add("highlight", cfi, ..., {fill: color})`.
- PDF: PDF.js text layer + `PDFPageProxy.getViewport` for coordinate conversion; paint overlay divs on the page layer.

### 8.4 Mobile and offline

Not in v1. Functional-but-unpolished touch UX is acceptable; service workers/PWA are deferred.

## 9. Deletion semantics

Per workspace convention, all memex-family record tables get soft delete.

- `DELETE /api/...` and `delete_*` MCP tools default to setting `archived_at = NOW()`.
- `?hard=true` / `hard=True` performs hard delete (cascades via existing FK constraints).
- Default queries filter `WHERE archived_at IS NULL`. `include_archived=true` exposes archived rows.
- `POST /api/.../{id}/restore` and `restore_*` MCP tools clear `archived_at`.

Cross-archive implication: if memex (federation) holds a trail step citing `book-memex://marginalia/<uuid>` and the marginalia is soft-archived, `get_record` still returns it (with `archived_at` set). Hard delete returns NOT_FOUND. This preserves trail continuity across accidental deletion.

## 10. Rename mechanics

Order within the implementation:

1. Rename Python package directory: `ebk/ebk/` → `ebk/book_memex/`. (Repo directory name `ebk/` can also rename to `book-memex/` at the workspace level, but that is a filesystem move outside the code.)
2. Update `pyproject.toml`: `name = "book-memex"`, description, entrypoints (`book-memex`, `book-memex-mcp-serve`).
3. Update all internal imports: `from ebk.X` → `from book_memex.X`. Use `git mv` and `ruff` or `grep`-based replace.
4. Rename CLI entry: `ebk` → `book-memex`. Keep `ebk` as an alias for one release, printing a deprecation notice.
5. Rename MCP server command: `ebk mcp-serve` → `book-memex mcp-serve`.
6. Build URI builder/parser module (`book_memex/core/uri.py`) that emits `book-memex://...`.
7. Update existing docs (README.md, internal docstrings).
8. Update the repo's own CLAUDE.md (section 2.2 reality now matches after extensions land).
9. Backfill `uuid` columns for existing Marginalia and ReadingSession rows (migration).
10. Database schema: migration 9 adds `archived_at` broadly, migration 10 adds `uuid` and ReadingSession anchors and Marginalia color, migration 11 renames `text_chunks` → `book_content` and adds new columns, migration 12 creates `book_content_fts` and triggers.

The rename lands atomically with v1 features. No long-lived compatibility shim; `ebk` as CLI alias for one release only.

## 11. Testing plan

### 11.1 Unit tests

- `safe_fts_query()` with tricky inputs (`C++`, `"quantum gravity"`, `foo AND bar`, empty, unicode).
- URI builder and parser for each kind and fragment variant.
- Extractors against fixture EPUBs (happy, nested spine, missing TOC) and PDFs (text layer present, absent, multi-column).
- Soft-delete filter correctness across `list_marginalia`, `list_reading_sessions`, Library query API, book list endpoint.
- `ask_book` pipeline with mocked LLM returning deterministic keywords and answer.
- Marginalia scope derivation (0, 1+location, 1 no location, 2+ books).
- Migration 9-12 forward and (where feasible) backward correctness using copies of real-world library DBs as fixtures.

### 11.2 Integration tests

- Round-trip: import book, extract content, add marginalia (highlight-scoped), fetch via MCP, verify URI parseable, soft-delete, verify filtered out, restore, verify visible again, hard-delete, verify gone.
- Reader endpoints: `/read/{id}` returns a valid shell with correct injected `window.BOOK`; `/books/{id}/file` streams correct content with correct MIME.
- Content search against a fixture book with known text; assert snippets + anchors.
- Cross-library content search with 2+ books.
- `ask_book` end-to-end against fixture with a mocked LLM.

### 11.3 End-to-end (manual for v1)

- Launch `book-memex serve`, open a real EPUB in browser, highlight, reload, verify persistence.
- Same for a real PDF.
- Import a scanned PDF; verify `no_text_layer` surfaces in the UI and MCP `get_schema`.

### 11.4 Coverage target

- Overall: 85%+.
- New modules (extractors, URI, query safety, soft-delete helpers, `ask_book` retrieval excluding LLM): 90%+.

## 12. Migration from current ebk state

1. **Package rename** (§10). Existing users reinstall.
2. **Schema migrations (9-12)**:
   - **9**: add `archived_at` to books, authors, subjects, tags, files, covers, personal_metadata, marginalia, reading_sessions.
   - **10**: add `uuid` to marginalia and reading_sessions (backfill existing rows with `uuid4().hex`); add `color` to marginalia; add `start_anchor`, `end_anchor` to reading_sessions; add `progress_anchor` to personal_metadata.
   - **11**: rename `text_chunks` → `book_content`; rename `chunk_index` → `segment_index`; add `segment_type`, `title`, `anchor`, `extractor_version`, `extraction_status`; drop `has_embedding`. Populate new columns for existing rows with sensible defaults (`segment_type='chunk-legacy'`, `anchor='{}'`, `extractor_version='legacy'`, `extraction_status='ok'`).
   - **12**: create `book_content_fts` virtual table + triggers; backfill from existing `book_content` rows.
3. **Content backfill**: not automatic. `book-memex reindex-content --all` re-runs extraction on the new schema for existing books. First-time users import new books and extraction runs automatically.
4. **No data loss**: all existing books, authors, tags, marginalia, reading sessions, extracted text, and concept-graph data is preserved.
5. **Web server URL changes**: `/read/{book_id}`, `/api/marginalia*`, `/api/reading/*`, `/api/search/content`, `/api/books/{id}/search` are new. Existing endpoints preserved.
6. **MCP tool changes**: additive. Existing tools preserved.

## 13. Risks and open questions

### 13.1 Content extraction quality (unchanged from original spec)

See original risk. Mitigation via `extractor_version` + `reindex-content`.

### 13.2 Reader UX on mobile (unchanged)

v1 is desktop-primary. Iterate on mobile after dogfooding.

### 13.3 FTS5 semantics for non-English books (unchanged)

Porter stemmer is English-only; other languages get unicode61 but no stemming. Add per-language tokenizer later.

### 13.4 `ask_book` quality for paraphrased queries (unchanged)

FTS5 retrieval misses synonyms. Semantic RAG arrives with the federation layer.

### 13.5 Multi-window progress race (unchanged)

`POST /api/reading/progress` accepts writes only if new anchor is at or after current. `PATCH` always wins.

### 13.6 Marginalia schema backwards compatibility

Adding `uuid` to existing Marginalia rows requires backfill. `uuid4().hex` is fine (not content-derived, but stable from that point on). Trails created AFTER v1 will cite those UUIDs; there are no pre-existing trail URIs to break.

### 13.7 TextChunk → BookContent rename

Existing TextChunk rows will be migrated with legacy placeholder values. Their `segment_type='chunk-legacy'` marks them as not-yet-reindexed. The reindex command regenerates them with proper chapter/page segmentation. Until reindex, content search will hit legacy chunks (word-based); functional but less accurate than chapter/page-based. Document this and recommend running reindex soon after upgrade.

### 13.8 `has_embedding` removal

Dropping the column is safe if no embeddings were ever computed (initial audit suggests none are). If a deployment DID have embeddings stored externally in sidecar files, those files become orphaned. Migration notes should mention this; users with external embeddings opt to export or delete those files separately.

### 13.9 Concept graph decision deferred

By punting on Concept/BookConcept/ConceptRelation migration, we leave a non-memex-style structure in book-memex. This is fine for v1 but creates a migration decision later. Flag in the follow-up roadmap.

### 13.10 URI form for Book

Book.unique_id is a 32-character hash string. The URI form is decided at implementation time: `book-memex://book/<unique_id>` directly, or `book-memex://book/sha256:<unique_id>` if unique_id is provably SHA256-derived. Pick one, document, and stick with it.

## 14. Deliverables checklist

On completion of v1:

- [ ] Package renamed to `book-memex`; CLI entrypoint `book-memex`.
- [ ] Migrations 9-12 applied cleanly to representative existing libraries.
- [ ] `uuid` + `archived_at` on Marginalia and ReadingSession; `color` on Marginalia; anchors on ReadingSession; `progress_anchor` on PersonalMetadata.
- [ ] `book_content` table (renamed TextChunk) with refined schema; `has_embedding` dropped.
- [ ] Segment-level content extraction for EPUB, PDF, TXT wired into import.
- [ ] `book_content_fts` + triggers.
- [ ] FastAPI endpoints: reader shell, file stream, marginalia CRUD, reading state, content search.
- [ ] MCP tools: marginalia CRUD, reading state, content search, `get_segment(s)`, `ask_book`.
- [ ] Browser reader with highlight capture, progress sync, in-book search.
- [ ] URIs emitted on all records; URI builder/parser module.
- [ ] arkiv export extended with new record kinds and URIs.
- [ ] `safe_fts_query()` helper.
- [ ] Soft delete retrofit (9 tables) with restore endpoints and MCP tools.
- [ ] Tests per §11.
- [ ] Documentation: README updated; CLAUDE.md updated; reader user guide.

## 15. Estimated effort

Revised after the audit. The original estimate underestimated how much of the data model already existed and overestimated how much new schema would be required. It also missed the reader entirely as green-field work and miscounted extraction as small.

| Component | Python LOC | JS LOC | Tests |
|---|---|---|---|
| Migrations (9-12) + tests | 300 | 0 | 200 |
| Model extensions + ORM tweaks | 100 | 0 | 100 |
| URI builder/parser | 80 | 0 | 120 |
| Soft-delete integration (filters + restore) | 150 | 0 | 200 |
| Content extractors (EPUB, PDF, TXT) | 500 | 0 | 300 |
| Extraction wiring into import + reindex CLI | 100 | 0 | 100 |
| FastAPI endpoints (marginalia, reading, content search, reader) | 400 | 0 | 400 |
| MCP tool additions | 250 | 0 | 250 |
| `ask_book` pipeline | 120 | 0 | 150 |
| Query safety helper | 40 | 0 | 80 |
| Reader template | 50 | 0 | 0 |
| Reader controller | 0 | 400 | (manual) |
| arkiv export extension | 80 | 0 | 100 |
| Rename mechanics | (refactor) | 0 | (refactor) |
| Total (approx) | **2170** | **400** | **2000** |

Roughly 2-4 weeks of focused work. Extractor iteration is the single largest quality risk.

### 15.1 Suggested implementation phases

The spec is cohesive but large. The implementation plan splits into phases that each leave the archive in a working state:

**Phase 1: Foundation.** Rename `ebk` to `book-memex`. Add `archived_at` across existing tables. Add `uuid`, `color`, anchors, `progress_anchor` to Marginalia / ReadingSession / PersonalMetadata. Build URI builder/parser. Build soft-delete infrastructure (filters, restore endpoints + MCP tools). Add marginalia CRUD REST endpoints and MCP tools. Add reading state REST endpoints and MCP tools. Extend arkiv export.

Phase 1 makes marginalia and reading state URI-addressable via MCP and REST, compliant with workspace conventions, but no reader UI and no content-level search yet.

**Phase 2: Content and search.** Rename `text_chunks` → `book_content` with schema refinement; drop `has_embedding`. Build content extractors for EPUB, PDF, TXT. Wire extraction into import. Add `book_content_fts` + triggers. Add within-book and cross-library search (REST + MCP). Add `ask_book`. Add `safe_fts_query()`. Add `book-memex reindex-content` CLI.

Phase 2 makes content searchable and queryable via MCP. Still no reader UI.

**Phase 3: Reader.** Build the browser reader (template + `reader.js`) with highlight capture, progress sync, in-book search, notes pane, session tracking.

Phases 1 and 2 are largely independent and could ship in either order. Phase 3 depends on both.

**Phase 4 (post-v1)**: extractor quality, mobile polish, Edition grouping, audiobooks, OCR, Concept graph migration to federation layer.
