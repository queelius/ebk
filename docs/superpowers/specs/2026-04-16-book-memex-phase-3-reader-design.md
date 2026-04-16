# book-memex Phase 3: Browser Reader

**Date**: 2026-04-16
**Status**: Draft (pending review)
**Scope**: Browser-based EPUB/PDF reader with highlight capture, progress sync, in-book search, notes, session tracking, and a three-theme system.
**Context**: Phase 3 of the book-memex v1 rollout. Phases 1 (foundation) and 2 (content extraction + search) are merged to master. The reader reuses all existing REST endpoints; no new Python services, models, or migrations are needed.

## 1. Summary

Add a browser-based ebook reader served from the existing FastAPI server. The reader renders EPUBs via EPUB.js and PDFs via PDF.js, both loaded from CDN (pinned versions, no npm/bundler). All state lives server-side: highlights as Marginalia rows, progress as PersonalMetadata.progress_anchor, reading sessions as ReadingSession rows. The browser is a disposable view.

The reader is desktop-first (keyboard shortcuts, mouse selection) but functional on tablets. It is not competing with Kindle's reading UX; its value is that highlights are URI-addressable, searchable via FTS5, and participate in the memex ecosystem.

## 2. New endpoints

Three new FastAPI routes. No new Pydantic models needed (existing ones suffice for the REST calls the reader makes via fetch).

### 2.1 `GET /read/{book_id}`

Returns `reader.html` (Jinja2 template). Selects EPUB.js or PDF.js based on `book.primary_file.format`. Injects `window.BOOK = {id, unique_id, format, file_url, title, author}` for the JS controller. Returns a friendly HTML error page if:
- Book not found (404).
- Book has no files ("No readable file found").
- File format is not EPUB or PDF ("Format X is not supported in the reader").

### 2.2 `GET /books/{book_id}/file`

Streams the book's primary file with correct `Content-Type` (`application/epub+zip` for EPUB, `application/pdf` for PDF) and `Range` header support (important for PDF.js which fetches byte ranges). Uses `FileResponse` or equivalent streaming from FastAPI/Starlette.

### 2.3 `GET /books/{book_id}/metadata.json`

Returns `{title, author, format, book_uri}` as JSON. Used by the reader header. Lightweight; avoids sending the full Book row.

## 3. Static assets

### 3.1 `book_memex/server/templates/reader.html` (~120 LOC)

Jinja2 template. Structure:

```html
<!DOCTYPE html>
<html data-reader-theme="light">
<head>
  <title>{{ title }} - book-memex reader</title>
  <link rel="stylesheet" href="/static/reader.css">
  <!-- EPUB.js or PDF.js loaded conditionally -->
  {% if format == "epub" %}
  <script src="https://cdn.jsdelivr.net/npm/epubjs@0.3.93/dist/epub.min.js"></script>
  {% elif format == "pdf" %}
  <script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.379/build/pdf.min.mjs" type="module"></script>
  {% endif %}
  <script>
    window.BOOK = {{ book_json | safe }};
  </script>
</head>
<body>
  <header id="reader-toolbar">
    <span id="book-title">{{ title }}</span>
    <div id="toolbar-actions">
      <button id="search-toggle" title="Search (Ctrl+F)">search icon</button>
      <button id="theme-toggle" title="Cycle theme">theme icon</button>
    </div>
  </header>
  <div id="search-bar" class="hidden">
    <input id="search-input" placeholder="Search in book..." />
    <div id="search-results"></div>
    <button id="search-close">X</button>
  </div>
  <main id="viewer"></main>
  <aside id="side-panel" class="hidden">
    <div id="panel-content"></div>
  </aside>
  <div id="highlight-toolbar" class="hidden">
    <button id="btn-highlight" title="Highlight">highlight icon</button>
    <button id="btn-note" title="Highlight + Note">note icon</button>
  </div>
  <script src="/static/reader.js" defer></script>
</body>
</html>
```

### 3.2 `book_memex/server/static/reader.js` (~400 LOC)

Single-file controller. No framework, no build step. Organized as an IIFE or a simple module. Responsibilities:

**Initialization:**
1. Detect format from `window.BOOK.format`.
2. Load renderer: EPUB.js `ePub(BOOK.file_url)` or PDF.js `getDocument(BOOK.file_url)`.
3. Fetch progress anchor and seek.
4. Fetch and paint existing highlights.
5. Start a reading session.

**Highlight capture:**
1. Listen for text selection events.
2. On non-empty selection, position the floating toolbar near the selection.
3. "Highlight" button: POST marginalia, paint in DOM, dismiss toolbar.
4. "Note" button: POST marginalia, open side panel with textarea, PATCH on save.
5. Clicking an existing highlight: open side panel showing highlight text + note.

**Progress sync:**
1. On relocated/scroll events, debounce 2 seconds.
2. `PATCH /api/reading/progress` (always wins, no backward rejection). The reader is the authoritative source.

**Reading sessions:**
1. `POST /api/reading/sessions/start` on load.
2. `POST /api/reading/sessions/{uuid}/end` on `beforeunload` via `navigator.sendBeacon`.

**In-book search:**
1. Intercept Ctrl-F / Cmd-F.
2. Show search bar (slides down from toolbar).
3. On Enter or 500ms debounce: `GET /api/books/{book_id}/search?q=...`.
4. Render results as snippet list.
5. Click result: jump to anchor.
6. Escape closes search bar.

**Theme switcher:**
1. Cycle button: light -> dark -> sepia -> light.
2. Store in `localStorage.bookMemexReaderTheme`.
3. Apply `data-reader-theme` attribute on `<html>`.

**Format abstraction:**
The controller uses a thin adapter pattern so the main logic doesn't branch on format everywhere:

```javascript
const adapter = BOOK.format === "epub" ? createEpubAdapter() : createPdfAdapter();
// adapter.display(anchor), adapter.onRelocated(cb), adapter.getSelection(),
// adapter.addHighlight(anchor, color), adapter.getCurrentAnchor(), adapter.getPercentage()
```

Each adapter wraps the library-specific calls. The main controller calls adapter methods.

### 3.3 `book_memex/server/static/reader.css` (~150 LOC)

Three themes via CSS custom properties:

```css
[data-reader-theme="light"] {
  --bg: #ffffff; --text: #1a1a1a; --highlight: #fff176;
  --panel-bg: #f5f5f5; --toolbar-bg: #ffffff; --border: #e0e0e0;
}
[data-reader-theme="dark"] {
  --bg: #1a1a1a; --text: #e0e0e0; --highlight: #665500;
  --panel-bg: #2a2a2a; --toolbar-bg: #1a1a1a; --border: #444;
}
[data-reader-theme="sepia"] {
  --bg: #f4ecd8; --text: #5b4636; --highlight: #e6d4a0;
  --panel-bg: #ede3ce; --toolbar-bg: #f4ecd8; --border: #d4c4a8;
}
```

Layout: full-width viewer, fixed top toolbar, slide-in right panel (300px), absolutely-positioned floating highlight toolbar, slide-down search bar.

## 4. Initialization flow (detailed)

```
Page load
  -> reader.js runs
  -> detect format
  -> create adapter (epub or pdf)
  -> adapter.init(BOOK.file_url, "#viewer")
  -> fetch GET /api/reading/progress?book_id=BOOK.id
     -> if anchor exists: adapter.display(anchor)
     -> else: adapter.display(null)  // start of book
  -> fetch GET /api/marginalia?book_id=BOOK.id&scope=highlight
     -> for each: adapter.addHighlight(m.position, m.color)
     -> store highlights in a Map(uuid -> marginalia)
  -> POST /api/reading/sessions/start {book_id: BOOK.id, start_anchor: currentAnchor}
     -> store session uuid for later end call
  -> register event listeners (selection, relocated, keydown, beforeunload)
```

## 5. Format-specific adapter contracts

### 5.1 EPUB adapter

```javascript
function createEpubAdapter() {
  let book, rendition;
  return {
    init(url, container) {
      book = ePub(url);
      rendition = book.renderTo(container, {width: "100%", height: "100%"});
      return rendition.display();
    },
    display(anchor) {
      if (anchor && anchor.cfi) return rendition.display(anchor.cfi);
      return rendition.display();
    },
    onRelocated(callback) {
      rendition.on("relocated", (location) => {
        callback({
          anchor: {cfi: location.start.cfi},
          percentage: location.start.percentage * 100,
        });
      });
    },
    onSelected(callback) {
      rendition.on("selected", (cfiRange, contents) => {
        const text = contents.window.getSelection().toString();
        const rect = contents.window.getSelection().getRangeAt(0).getBoundingClientRect();
        callback({
          text,
          anchor: {cfi: cfiRange},
          rect,  // for positioning the floating toolbar
        });
      });
    },
    addHighlight(position, color) {
      if (position && position.cfi) {
        rendition.annotations.add("highlight", position.cfi, {}, null, "hl",
          {"fill": color || "#fff176", "fill-opacity": "0.3"});
      }
    },
    getCurrentAnchor() {
      const loc = rendition.currentLocation();
      if (!loc || !loc.start) return null;
      return {cfi: loc.start.cfi};
    },
    getPercentage() {
      const loc = rendition.currentLocation();
      return loc && loc.start ? loc.start.percentage * 100 : 0;
    },
    jumpToFragment(fragment) {
      // fragment is a CFI string like "epubcfi(...)"
      if (fragment.startsWith("epubcfi(")) rendition.display(fragment);
    },
  };
}
```

### 5.2 PDF adapter

```javascript
function createPdfAdapter() {
  let pdfDoc, container, currentPage = 1, totalPages = 0;
  // ... PDF.js rendering setup, canvas per page or virtual scroll
  return {
    init(url, containerEl) { /* load doc, render first page */ },
    display(anchor) { /* scroll to anchor.page */ },
    onRelocated(callback) { /* scroll/page-change listener */ },
    onSelected(callback) { /* text layer selection listener */ },
    addHighlight(position, color) { /* overlay div on page canvas */ },
    getCurrentAnchor() { return {page: currentPage}; },
    getPercentage() { return (currentPage / totalPages) * 100; },
    jumpToFragment(fragment) { /* parse "page=N" and scroll */ },
  };
}
```

The PDF adapter is more complex (canvas rendering, text layer overlays, multi-page scroll). The EPUB adapter benefits from EPUB.js doing most of the work. Both expose the same interface to the controller.

## 6. Error handling

| Scenario | Behavior |
|---|---|
| Book not found | `/read/{id}` returns HTML error page (404) |
| No files on book | HTML error page: "No readable file found" |
| Unsupported format | HTML error page: "Format X not supported in reader" |
| Progress fetch fails | Start at beginning of book; log to console |
| Highlight save fails | Floating toolbar flashes red briefly; highlight not painted; user can retry |
| Progress sync fails | Log to console; retry on next relocated event |
| Session end fails (beforeunload) | sendBeacon is fire-and-forget; session stays open (server can detect orphaned sessions later) |
| Search returns no results | "No results found" message in search bar |
| CDN unreachable | Reader shell loads but renderer fails; show "Could not load reader library" message in viewer area |

## 7. Testing

### 7.1 Automated (pytest)

- `GET /read/{book_id}` returns 200, Content-Type text/html.
- Response HTML contains `window.BOOK` with correct id, format, title.
- EPUB book loads EPUB.js script tag; PDF book loads PDF.js script tag.
- `GET /read/99999` returns 404.
- `GET /books/{book_id}/file` returns correct MIME type.
- `GET /books/{book_id}/file` supports Range header (returns 206 Partial Content).
- `GET /books/{book_id}/metadata.json` returns correct shape.
- Book with no files: `/read/{id}` returns friendly error page.

### 7.2 Manual checklist (documented, not automated)

- [ ] Open EPUB in reader; content renders.
- [ ] Select text; floating toolbar appears near selection.
- [ ] Click highlight; text turns yellow; persists across reload.
- [ ] Click note; side panel opens with textarea; save note; persists.
- [ ] Click existing highlight; side panel shows highlight text + note.
- [ ] Ctrl-F opens search bar; type query; results appear; click jumps.
- [ ] Escape closes search bar.
- [ ] Close tab, reopen; progress restored to last position.
- [ ] Cycle theme: light, dark, sepia; each applies visually.
- [ ] Repeat all above for a PDF.

## 8. Scope exclusions (not in Phase 3)

- Offline / PWA (service workers).
- Mobile touch polish (functional but not optimized).
- Multi-color highlights (yellow only).
- Table of contents sidebar.
- Font size / family controls.
- Text-to-speech.
- Annotation export from reader UI.
- Automated browser testing (Playwright/Selenium).

## 9. Estimated effort

| Component | LOC | Notes |
|---|---|---|
| FastAPI endpoints (3) | ~80 Python | /read, /file, /metadata.json |
| reader.html template | ~120 HTML | Jinja2, conditional EPUB/PDF script |
| reader.css | ~150 CSS | Three themes, layout, floating toolbar, panels |
| reader.js | ~400 JS | Controller, adapters, highlight/search/progress/session |
| Tests (automated) | ~100 Python | 8-10 endpoint tests |
| Total | ~850 | Plus manual browser testing |
