# book-memex Phase 3: Browser Reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a browser-based EPUB/PDF reader at `/read/{book_id}` with highlight capture, progress sync, in-book search, notes, reading-session tracking, and a three-theme system (light/dark/sepia).

**Architecture:** Server-rendered HTML shell with client-side EPUB.js/PDF.js (CDN, pinned). All state server-side via existing Phase 1+2 REST endpoints. No new Python services, models, or migrations. One HTML template, one CSS file, one JS controller with a format-adapter pattern.

**Tech Stack:** Python 3.12+ / FastAPI (endpoints), Jinja2 (template), EPUB.js 0.3.93 (CDN), PDF.js 4.0.379 (CDN), vanilla JS (~400 LOC), CSS custom properties (themes).

**Pre-flight:**
- Working directory: `/home/spinoza/github/memex/ebk/`
- Branch: create `book-memex-v1-phase-3` from master.
- Python package: `book_memex/`.
- Existing test baseline: 1082 passed, 4 skipped.
- Spec: `docs/superpowers/specs/2026-04-16-book-memex-phase-3-reader-design.md`.
- Existing endpoints the reader calls: `/api/marginalia`, `/api/reading/progress`, `/api/reading/sessions/*`, `/api/books/{id}/search`.
- `server.py` uses flat `@app.method()` decorators, `get_library()` helper, `HTTPException(status_code=..., detail=...)`.

**Security note:** The JS controller must use safe DOM methods (createElement, textContent, appendChild) for user content. Do NOT use innerHTML with untrusted data. Search result snippets from the server contain `<mark>` tags; use DOMParser or a sanitizing helper to safely render these.

---

## File structure

```
book_memex/
  server.py                              # MODIFIED: add 3 endpoints + Jinja2 setup
  server/
    templates/
      reader.html                        # NEW: Jinja2 shell
      reader_error.html                  # NEW: error page
    static/
      reader.js                          # NEW: controller with adapter pattern
      reader.css                         # NEW: three themes + layout
tests/
  test_reader_endpoints.py               # NEW: endpoint tests
```

---

## Task 1: Static file serving + Jinja2 setup + reader CSS

**Files:**
- Modify: `book_memex/server.py`
- Create: `book_memex/server/templates/` (directory)
- Create: `book_memex/server/static/reader.css`

Set up Jinja2 template directory, static file mount, and the CSS with all three themes.

- [ ] **Step 1: Create directories and CSS file**

Run:
```bash
mkdir -p book_memex/server/templates book_memex/server/static
```

Create `book_memex/server/static/reader.css` with the full three-theme CSS. The file should contain:
- CSS custom properties for light, dark, and sepia themes on `[data-reader-theme="..."]` selectors.
- Layout rules for: `#reader-toolbar` (fixed top, 48px), `#viewer` (fills remaining space, transitions for panel), `#side-panel` (fixed right, 320px, slides in/out), `#search-bar` (slides down from toolbar), `#highlight-toolbar` (absolute, hidden by default, flex when visible).
- Styles for search results (`.search-hit`, `.hit-label`), side panel content (`.highlight-text`, `textarea`, `.save-btn`), error page (`.reader-error`).

Refer to spec section 3.3 for the exact color values per theme.

- [ ] **Step 2: Add Jinja2 + static mount to server.py**

Add near the top imports of `book_memex/server.py`:

```python
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
```

After the `app = FastAPI(...)` creation, add:

```python
_SERVER_DIR = Path(__file__).parent / "server"
app.mount("/static", StaticFiles(directory=str(_SERVER_DIR / "static")), name="reader-static")
_templates = Jinja2Templates(directory=str(_SERVER_DIR / "templates"))
```

- [ ] **Step 3: Commit**

```bash
git add book_memex/server.py book_memex/server/static/reader.css book_memex/server/templates/
git commit -m "feat(reader): add static/template infrastructure + reader.css with three themes"
```

---

## Task 2: Reader HTML templates

**Files:**
- Create: `book_memex/server/templates/reader.html`
- Create: `book_memex/server/templates/reader_error.html`

- [ ] **Step 1: Create reader.html**

Create `book_memex/server/templates/reader.html`. The template must:
- Set `data-reader-theme="light"` on `<html>`.
- Load reader.css.
- Conditionally load EPUB.js (`epubjs@0.3.93`) or PDF.js (`pdfjs-dist@4.0.379`) from CDN based on `{{ format }}`.
- Inject `window.BOOK = {{ book_json | safe }}` in a script tag.
- Include DOM structure: `#reader-toolbar` (back link, title, search + theme buttons), `#search-bar` (input + results + close), `#viewer` (main content), `#side-panel` (panel-content div), `#highlight-toolbar` (highlight + note buttons).
- Load `reader.js` with defer.

Use HTML entities for button icons (search: `&#128269;`, theme: `&#9788;`, highlight: `&#9998;`, note: `&#128221;`, close: `&times;`, back: `&larr;`).

- [ ] **Step 2: Create reader_error.html**

A simple error template with: `{{ error_title }}`, `{{ error_message }}`, and a "Back to library" link. Uses `reader-error` CSS class.

- [ ] **Step 3: Commit**

```bash
git add book_memex/server/templates/
git commit -m "feat(reader): add reader.html + reader_error.html templates"
```

---

## Task 3: Three FastAPI reader endpoints + tests

**Files:**
- Modify: `book_memex/server.py`
- Create: `tests/test_reader_endpoints.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reader_endpoints.py` with ~10 tests covering:
- `GET /read/{book_id}`: returns 200 HTML for EPUB; contains `window.BOOK` and `epub.min.js` in the response.
- `GET /read/{book_id}`: contains correct book title and id in the injected JSON.
- `GET /read/99999`: returns 404.
- `GET /read/{txt_book_id}`: returns HTML error page mentioning "not supported" (for non-EPUB/PDF formats).
- `GET /books/{book_id}/file`: returns 200 with EPUB MIME type and non-empty body.
- `GET /books/{book_id}/file`: supports Range header (returns 200 or 206).
- `GET /books/99999/file`: returns 404.
- `GET /books/{book_id}/metadata.json`: returns JSON with title, format, book_uri.
- `GET /books/99999/metadata.json`: returns 404.

Use fixtures: `client_with_epub` (imports a sample EPUB via `sample_epub` conftest fixture), `client_with_txt` (imports a .txt file).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_reader_endpoints.py -q`

- [ ] **Step 3: Implement the three endpoints**

Add to `book_memex/server.py`:

**`GET /read/{book_id}`**: Takes `request: Request` (for Jinja2) and `book_id: int`. Looks up the book and primary file. If book not found: 404. If no files: render `reader_error.html` with "No readable file". If format not in (epub, pdf): render `reader_error.html` with "Format not supported". Otherwise: build `book_json` dict and render `reader.html`.

**`GET /books/{book_id}/file`**: Looks up book + primary file. Returns `FileResponse` with correct `media_type` (epub: `application/epub+zip`, pdf: `application/pdf`, txt: `text/plain`, fallback: `application/octet-stream`). FileResponse handles Range headers automatically.

**`GET /books/{book_id}/metadata.json`**: Returns `{title, author, format, book_uri}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_reader_endpoints.py -q`

- [ ] **Step 5: Run full suite**

Run: `pytest -q --tb=no 2>&1 | tail -3`

- [ ] **Step 6: Commit**

```bash
git add book_memex/server.py tests/test_reader_endpoints.py
git commit -m "feat(reader): add /read, /file, /metadata.json endpoints + tests"
```

---

## Task 4: reader.js controller

**Files:**
- Create: `book_memex/server/static/reader.js`

The full JS controller (~400 LOC). This is the largest task.

**Security requirement:** Use safe DOM methods (createElement, textContent, appendChild) for all user-facing content. For server-generated search snippets that contain `<mark>` tags, use a sanitizing approach: create a temporary element, set textContent for untrusted parts, and only allow `<mark>` tags from the server by parsing with DOMParser and whitelisting.

- [ ] **Step 1: Create reader.js**

Create `book_memex/server/static/reader.js` as a single IIFE. The file must implement:

**Core structure:**
- Format detection from `window.BOOK.format`.
- Adapter factory: `createEpubAdapter()` and `createPdfAdapter()`.
- State: `adapter`, `sessionUuid`, `highlights` Map, `progressDebounce` timer.
- `api(method, path, body)` helper wrapping fetch.
- `init()` async function that orchestrates startup.

**Adapters** (common interface):
- `init(url, containerEl)`: load and render the book.
- `display(anchor)`: seek to an anchor.
- `onRelocated(callback)`: register for position-change events.
- `onSelected(callback)`: register for text-selection events. Callback receives `{text, anchor, rect}`.
- `addHighlight(position, color)`: paint a highlight in the rendered content.
- `getCurrentAnchor()`: return current position as an anchor dict.
- `getPercentage()`: return current position as 0-100.
- `jumpToFragment(fragment)`: navigate to a URI fragment string.

**EPUB adapter specifics:**
- Uses `ePub(url)` and `book.renderTo(container, {width: "100%", height: "100%"})`.
- Selection coordinates must be translated from iframe space to main document space.
- Highlights via `rendition.annotations.add("highlight", cfi, ...)`.

**PDF adapter specifics:**
- Renders all pages as canvas elements in a scrollable container.
- Text layer via absolute-positioned spans from `page.getTextContent()`.
- Page detection via scroll position.
- `addHighlight` is a no-op in v1 (highlights stored server-side; visual overlay deferred).

**Features:**
- **Theme:** Read from localStorage on load, cycle on button click, apply via `data-reader-theme` attribute.
- **Progress:** On relocated, debounce 2s, then `PATCH /api/reading/progress`.
- **Sessions:** `POST start` on init; `sendBeacon` end on `beforeunload`.
- **Highlights:** Fetch on init and paint. On selection, show floating toolbar. Highlight button POSTs to `/api/marginalia`. Note button POSTs then opens side panel.
- **Notes panel:** Slide-in right panel. Shows highlight text + textarea for note. Save PATCHes the marginalia. Clicking existing highlight shows its detail.
- **Search:** Ctrl-F/Cmd-F override. Search bar slides down. Debounced query to `/api/books/{id}/search`. Results as clickable snippets that jump to anchor.

**DOM construction rules:** Build all dynamic content with `document.createElement`, `element.textContent`, `element.appendChild`. For search snippets containing server `<mark>` tags, use a `safeSnippet(html)` helper that creates a `<template>` element, strips all tags except `<mark>`, and returns a DocumentFragment.

- [ ] **Step 2: Verify JS syntax**

Run: `node -c book_memex/server/static/reader.js && echo "syntax ok"` (if node available).

- [ ] **Step 3: Commit**

```bash
git add book_memex/server/static/reader.js
git commit -m "feat(reader): add reader.js controller with adapter pattern"
```

---

## Task 5: Manual browser testing + fixes

**Files:** any reader file that needs bug fixes.

- [ ] **Step 1: Start dev server**

```bash
book-memex serve &
```

- [ ] **Step 2: Import a test book if needed**

```bash
book-memex import /path/to/some.epub
```

- [ ] **Step 3: Open reader and walk through checklist**

Open `http://localhost:8000/read/{book_id}`.

Checklist:
- [ ] Content renders (EPUB chapters visible).
- [ ] Select text: floating toolbar appears near selection.
- [ ] Click highlight: text highlighted, persists across reload.
- [ ] Click note: side panel opens, save note, persists.
- [ ] Click existing highlight: side panel shows detail.
- [ ] Ctrl-F: search bar opens, type query, results appear, click jumps.
- [ ] Escape closes search bar.
- [ ] Close tab, reopen: progress restored.
- [ ] Theme cycle: light, dark, sepia.
- [ ] Repeat for PDF (if available).

- [ ] **Step 4: Fix any issues, commit**

```bash
git add -A && git commit -m "fix(reader): browser testing fixes"
```

---

## Task 6: Update CLAUDE.md + final verification

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Move Phase 3 from "pending" to "complete" in the pending-work section. Add a brief reader description under architecture noting: `/read/{book_id}` serves the reader, static assets at `server/static/` and `server/templates/`, adapter pattern for EPUB/PDF, three themes via localStorage, all state server-side.

- [ ] **Step 2: Run full test suite**

```bash
pytest -q --tb=no 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md && git commit -m "docs: update CLAUDE.md for Phase 3 reader completion"
```

---

## Self-review

| Spec section | Task |
|---|---|
| §2 Endpoints (/read, /file, /metadata.json) | Task 3 |
| §3.1 reader.html | Task 2 |
| §3.2 reader.js | Task 4 |
| §3.3 reader.css | Task 1 |
| §4 Init flow | Task 4 |
| §5 Adapters | Task 4 |
| §6 Error handling | Tasks 2 + 3 + 4 |
| §7.1 Automated tests | Task 3 |
| §7.2 Manual checklist | Task 5 |

All spec sections covered. No placeholders. Adapter interface consistent across EPUB/PDF. DOM security addressed via safe construction methods.
