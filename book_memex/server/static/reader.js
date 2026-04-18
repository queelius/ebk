/**
 * book-memex reader controller
 *
 * Single IIFE, no framework, no build step.  Drives EPUB.js or PDF.js through
 * a thin adapter interface and wires up highlight capture, progress sync,
 * reading sessions, in-book search, notes panel, and three-theme cycling.
 *
 * Security: all user-facing content built with createElement + textContent.
 * Server search snippets (containing <mark>) sanitized via DOMParser whitelist.
 */
(function () {
  "use strict";

  /* ── Globals injected by the template ──────────────────────── */
  var BOOK = window.BOOK;
  if (!BOOK) return;

  /* ── DOM handles ───────────────────────────────────────────── */
  var $viewer         = document.getElementById("viewer");
  var $searchBar      = document.getElementById("search-bar");
  var $searchInput    = document.getElementById("search-input");
  var $searchResults  = document.getElementById("search-results");
  var $searchClose    = document.getElementById("search-close");
  var $searchToggle   = document.getElementById("search-toggle");
  var $themeToggle    = document.getElementById("theme-toggle");
  var $navPrev        = document.getElementById("nav-prev");
  var $navNext        = document.getElementById("nav-next");
  var $sidePanel      = document.getElementById("side-panel");
  var $panelContent   = document.getElementById("panel-content");
  var $hlToolbar      = document.getElementById("highlight-toolbar");
  var $btnHighlight   = document.getElementById("btn-highlight");
  var $btnNote        = document.getElementById("btn-note");

  /* ── State ─────────────────────────────────────────────────── */
  var adapter            = null;
  var sessionUuid        = null;
  var highlights         = new Map();   // uuid -> marginalia object
  var progressDebounce   = null;
  var searchDebounce     = null;
  var pendingSelection   = null;        // {text, anchor, rect}
  var themes             = ["light", "dark", "sepia"];
  var themeIndex         = 0;

  /* ── Helpers ───────────────────────────────────────────────── */

  /** Escape a string for use in an HTML data-attribute value. */
  function escapeAttr(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#39;");
  }

  /**
   * Sanitise a server-rendered search snippet.  Only text nodes and <mark>
   * elements survive; everything else is stripped.  Returns a DocumentFragment.
   */
  function safeSnippet(html) {
    var frag = document.createDocumentFragment();
    var doc  = new DOMParser().parseFromString(html, "text/html");
    var nodes = doc.body.childNodes;
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (node.nodeType === Node.TEXT_NODE) {
        frag.appendChild(document.createTextNode(node.textContent));
      } else if (node.nodeType === Node.ELEMENT_NODE && node.tagName === "MARK") {
        var mark = document.createElement("mark");
        mark.textContent = node.textContent;
        frag.appendChild(mark);
      }
      // Skip all other element types (sanitise).
    }
    return frag;
  }

  /** JSON-speaking fetch wrapper.  Returns parsed body or null on error. */
  async function api(method, path, body) {
    try {
      var opts = {
        method: method,
        headers: { "Content-Type": "application/json" },
      };
      if (body !== undefined) opts.body = JSON.stringify(body);
      var resp = await fetch(path, opts);
      if (!resp.ok) {
        console.warn("api", method, path, resp.status);
        return null;
      }
      var text = await resp.text();
      return text ? JSON.parse(text) : null;
    } catch (err) {
      console.error("api error", method, path, err);
      return null;
    }
  }

  /* ── Theme system ──────────────────────────────────────────── */

  // Per-theme palettes mirrored from reader.css, applied to the EPUB.js
  // iframe so the book content also respects the reader's theme.
  var READER_THEMES = {
    light:  { body: { "background": "#ffffff", "color": "#1a1a1a" } },
    dark:   { body: { "background": "#1a1a1a", "color": "#e0e0e0" } },
    sepia:  { body: { "background": "#f4ecd8", "color": "#5b4636" } },
  };

  function applyTheme(name) {
    document.documentElement.setAttribute("data-reader-theme", name);
    try { localStorage.setItem("bookMemexReaderTheme", name); } catch (_) {}
    // Propagate to the EPUB.js rendition iframe if available.
    if (adapter && typeof adapter.applyContentTheme === "function") {
      adapter.applyContentTheme(name);
    }
  }

  function initTheme() {
    var stored = null;
    try { stored = localStorage.getItem("bookMemexReaderTheme"); } catch (_) {}
    if (stored && themes.indexOf(stored) !== -1) {
      themeIndex = themes.indexOf(stored);
    }
    applyTheme(themes[themeIndex]);
  }

  function cycleTheme() {
    themeIndex = (themeIndex + 1) % themes.length;
    applyTheme(themes[themeIndex]);
  }

  /* ── Adapters ──────────────────────────────────────────────── */

  /** EPUB adapter — wraps EPUB.js (the ePub global). */
  function createEpubAdapter() {
    var book, rendition;
    return {
      async init(url, containerEl) {
        // Fetch as ArrayBuffer so EPUB.js treats it as a zipped EPUB rather
        // than resolving META-INF/container.xml relative to the URL path
        // (our /books/{id}/file URL has no .epub extension).
        const resp = await fetch(url);
        if (!resp.ok) throw new Error("Could not fetch EPUB file: " + resp.status);
        const buf = await resp.arrayBuffer();
        book = ePub(buf);
        rendition = book.renderTo(containerEl, {
          width: "100%",
          height: "100%",
        });
        // Register theme palettes so the EPUB iframe can switch colours
        // in sync with the outer reader chrome.
        for (var name in READER_THEMES) {
          if (Object.prototype.hasOwnProperty.call(READER_THEMES, name)) {
            rendition.themes.register(name, READER_THEMES[name]);
          }
        }
        await rendition.display();
      },

      applyContentTheme: function (name) {
        if (rendition && rendition.themes) {
          try { rendition.themes.select(name); } catch (_) {}
        }
      },

      async display(anchor) {
        if (anchor && anchor.cfi) return rendition.display(anchor.cfi);
        return rendition.display();
      },

      prev() { return rendition && rendition.prev && rendition.prev(); },
      next() { return rendition && rendition.next && rendition.next(); },

      /** Wire the given callback for keydown events inside the EPUB iframe. */
      onKeyDown(callback) {
        if (!rendition) return;
        rendition.on("keydown", function (e) {
          callback(e.key);
        });
      },

      onRelocated(callback) {
        rendition.on("relocated", function (location) {
          callback({
            anchor: { cfi: location.start.cfi },
            percentage: location.start.percentage * 100,
          });
        });
      },

      onSelected(callback) {
        rendition.on("selected", function (cfiRange, contents) {
          var sel  = contents.window.getSelection();
          var text = sel.toString();
          if (!text) return;
          var range     = sel.getRangeAt(0);
          var iframeRect = range.getBoundingClientRect();

          // Translate iframe-local coords to main document coords.
          var iframe = containerEl.querySelector("iframe");
          var offset = iframe
            ? iframe.getBoundingClientRect()
            : { left: 0, top: 0 };

          var rect = {
            left:   iframeRect.left   + offset.left,
            top:    iframeRect.top    + offset.top,
            right:  iframeRect.right  + offset.left,
            bottom: iframeRect.bottom + offset.top,
            width:  iframeRect.width,
            height: iframeRect.height,
          };

          callback({ text: text, anchor: { cfi: cfiRange }, rect: rect });
        });
      },

      addHighlight(position, color) {
        if (position && position.cfi) {
          rendition.annotations.add(
            "highlight", position.cfi, {}, null, "hl",
            { fill: color || "#fff176", "fill-opacity": "0.3" }
          );
        }
      },

      getCurrentAnchor() {
        var loc = rendition.currentLocation();
        if (!loc || !loc.start) return null;
        return { cfi: loc.start.cfi };
      },

      getPercentage() {
        var loc = rendition.currentLocation();
        return loc && loc.start ? loc.start.percentage * 100 : 0;
      },

      jumpToFragment(fragment) {
        if (fragment && fragment.startsWith("epubcfi(")) {
          rendition.display(fragment);
        }
      },
    };
  }

  /** PDF adapter — renders all pages as canvases with text layers. */
  function createPdfAdapter() {
    var pdfDoc     = null;
    var container  = null;
    var totalPages = 0;
    var currentPage = 1;
    var relocatedCb = null;
    var selectedCb  = null;
    var pageEls     = [];  // one wrapper div per page

    /** Detect which page is most visible and fire relocated. */
    function onScroll() {
      if (!pageEls.length) return;
      var scrollTop  = container.scrollTop;
      var viewHeight = container.clientHeight;
      var viewMid    = scrollTop + viewHeight / 2;

      var best = 1;
      for (var i = 0; i < pageEls.length; i++) {
        if (pageEls[i].offsetTop <= viewMid) best = i + 1;
      }
      if (best !== currentPage) {
        currentPage = best;
        if (relocatedCb) {
          relocatedCb({
            anchor: { page: currentPage },
            percentage: (currentPage / totalPages) * 100,
          });
        }
      }
    }

    /** Render a single page (canvas + text layer). */
    async function renderPage(page, pageNum) {
      var scale    = 1.5;
      var viewport = page.getViewport({ scale: scale });

      var wrapper = document.createElement("div");
      wrapper.style.position = "relative";
      wrapper.style.marginBottom = "8px";
      wrapper.setAttribute("data-page", String(pageNum));

      // Canvas
      var canvas  = document.createElement("canvas");
      var ctx     = canvas.getContext("2d");
      canvas.width  = viewport.width;
      canvas.height = viewport.height;
      canvas.style.display = "block";
      canvas.style.width  = "100%";
      canvas.style.height = "auto";
      wrapper.appendChild(canvas);

      await page.render({ canvasContext: ctx, viewport: viewport }).promise;

      // Text layer
      var textContent = await page.getTextContent();
      var textDiv     = document.createElement("div");
      textDiv.style.position = "absolute";
      textDiv.style.left   = "0";
      textDiv.style.top    = "0";
      textDiv.style.width  = "100%";
      textDiv.style.height = "100%";
      textDiv.style.overflow = "hidden";

      var scaleX = 1; // will be adjusted after layout

      textContent.items.forEach(function (item) {
        var tx = item.transform;
        var span = document.createElement("span");
        span.textContent = item.str;
        span.style.position  = "absolute";
        span.style.whiteSpace = "pre";
        span.style.fontSize  = (tx[0] * scale) + "px";
        span.style.fontFamily = "sans-serif";
        span.style.color     = "transparent";
        // tx = [scaleX, skewY, skewX, scaleY, translateX, translateY]
        // PDF origin is bottom-left, DOM is top-left.
        span.style.left = ((tx[4] * scale) / viewport.width * 100) + "%";
        span.style.top  = ((viewport.height - tx[5] * scale - tx[0] * scale) / viewport.height * 100) + "%";
        textDiv.appendChild(span);
      });

      wrapper.appendChild(textDiv);
      return wrapper;
    }

    return {
      async init(url, containerEl) {
        container = containerEl;
        container.style.overflow = "auto";

        var pdfjsLib = globalThis.pdfjsLib;
        if (!pdfjsLib) {
          container.textContent = "Could not load PDF.js library.";
          return;
        }
        if (window.PDFJS_WORKER_SRC) {
          pdfjsLib.GlobalWorkerOptions.workerSrc = window.PDFJS_WORKER_SRC;
        }

        pdfDoc = await pdfjsLib.getDocument(url).promise;
        totalPages = pdfDoc.numPages;

        for (var i = 1; i <= totalPages; i++) {
          var page = await pdfDoc.getPage(i);
          var el   = await renderPage(page, i);
          container.appendChild(el);
          pageEls.push(el);
        }

        container.addEventListener("scroll", onScroll, { passive: true });

        // Selection via mouseup on the text layers.
        container.addEventListener("mouseup", function () {
          var sel = window.getSelection();
          if (!sel || sel.isCollapsed || !sel.toString().trim()) return;
          if (!selectedCb) return;

          var range = sel.getRangeAt(0);
          var rect  = range.getBoundingClientRect();

          // Determine page from selection anchor node.
          var node = range.startContainer;
          var pageNum = currentPage;
          while (node && node !== container) {
            if (node.getAttribute && node.getAttribute("data-page")) {
              pageNum = parseInt(node.getAttribute("data-page"), 10);
              break;
            }
            node = node.parentNode;
          }

          selectedCb({
            text: sel.toString(),
            anchor: { page: pageNum },
            rect: {
              left: rect.left, top: rect.top,
              right: rect.right, bottom: rect.bottom,
              width: rect.width, height: rect.height,
            },
          });
        });
      },

      async display(anchor) {
        if (anchor && anchor.page && pageEls[anchor.page - 1]) {
          pageEls[anchor.page - 1].scrollIntoView({ behavior: "auto" });
          currentPage = anchor.page;
        }
      },

      onRelocated(callback)  { relocatedCb = callback; },
      onSelected(callback)   { selectedCb  = callback; },

      prev() {
        if (currentPage > 1 && pageEls[currentPage - 2]) {
          pageEls[currentPage - 2].scrollIntoView({ behavior: "smooth" });
        }
      },
      next() {
        if (currentPage < totalPages && pageEls[currentPage]) {
          pageEls[currentPage].scrollIntoView({ behavior: "smooth" });
        }
      },

      /** Visual PDF highlight overlay deferred to post-v1. */
      addHighlight(/* position, color */) {
        // No-op in v1.  Highlights are stored server-side and painted
        // on reload when the overlay layer is implemented.
      },

      getCurrentAnchor() { return { page: currentPage }; },
      getPercentage()    { return totalPages ? (currentPage / totalPages) * 100 : 0; },

      jumpToFragment(fragment) {
        if (!fragment) return;
        var m = fragment.match(/page=(\d+)/);
        if (m) {
          var p = parseInt(m[1], 10);
          if (pageEls[p - 1]) {
            pageEls[p - 1].scrollIntoView({ behavior: "smooth" });
            currentPage = p;
          }
        }
      },
    };
  }

  /* ── Progress sync ─────────────────────────────────────────── */

  function syncProgress(anchor, percentage) {
    clearTimeout(progressDebounce);
    progressDebounce = setTimeout(function () {
      api("PATCH", "/api/reading/progress", {
        book_id: BOOK.id,
        anchor: anchor,
        percentage: percentage,
      });
    }, 2000);
  }

  /* ── Reading sessions ──────────────────────────────────────── */

  async function startSession() {
    var anchor = adapter ? adapter.getCurrentAnchor() : null;
    var data = await api("POST", "/api/reading/sessions/start", {
      book_id: BOOK.id,
      start_anchor: anchor,
    });
    if (data && data.uuid) sessionUuid = data.uuid;
  }

  function endSession() {
    if (!sessionUuid) return;
    var anchor = adapter ? adapter.getCurrentAnchor() : null;
    var body = JSON.stringify({ end_anchor: anchor });
    navigator.sendBeacon(
      "/api/reading/sessions/" + encodeURIComponent(sessionUuid) + "/end",
      new Blob([body], { type: "application/json" })
    );
  }

  /* ── Highlights ────────────────────────────────────────────── */

  async function loadHighlights() {
    var data = await api("GET",
      "/api/marginalia?book_id=" + BOOK.id + "&scope=highlight");
    if (!Array.isArray(data)) return;
    data.forEach(function (m) {
      highlights.set(m.uuid, m);
      if (adapter) adapter.addHighlight(m.position, m.color);
    });
  }

  async function createHighlight(text, anchor, openNote) {
    var data = await api("POST", "/api/marginalia", {
      book_ids: [BOOK.id],
      highlighted_text: text,
      position: anchor,
      color: "#fff176",
    });
    if (!data) return;
    highlights.set(data.uuid, data);
    if (adapter) adapter.addHighlight(data.position, data.color);
    if (openNote) showNotePanel(data);
  }

  /* ── Floating highlight toolbar ────────────────────────────── */

  function showHighlightToolbar(sel) {
    pendingSelection = sel;
    var r = sel.rect;
    // Position above the selection, centred horizontally.
    $hlToolbar.style.left = (r.left + r.width / 2 - 40) + "px";
    $hlToolbar.style.top  = (r.top + window.scrollY - 44) + "px";
    $hlToolbar.classList.add("visible");
  }

  function hideHighlightToolbar() {
    $hlToolbar.classList.remove("visible");
    pendingSelection = null;
  }

  /* ── Side panel (notes) ────────────────────────────────────── */

  function openSidePanel() {
    $sidePanel.classList.add("visible");
    $viewer.classList.add("panel-open");
  }

  function closeSidePanel() {
    $sidePanel.classList.remove("visible");
    $viewer.classList.remove("panel-open");
    // Clear content.
    while ($panelContent.firstChild) $panelContent.removeChild($panelContent.firstChild);
  }

  /** Build the "new note" editor for a just-created highlight. */
  function showNotePanel(marginalia) {
    openSidePanel();
    while ($panelContent.firstChild) $panelContent.removeChild($panelContent.firstChild);

    // Quoted highlight text.
    var ht = document.createElement("div");
    ht.className = "highlight-text";
    ht.textContent = marginalia.highlighted_text || "";
    $panelContent.appendChild(ht);

    // Label
    var label = document.createElement("label");
    label.textContent = "Note";
    label.style.display = "block";
    label.style.fontWeight = "600";
    label.style.margin = "8px 0 4px";
    $panelContent.appendChild(label);

    // Textarea
    var ta = document.createElement("textarea");
    ta.placeholder = "Add a note...";
    ta.value = marginalia.content || "";
    $panelContent.appendChild(ta);

    // Save button
    var btn = document.createElement("button");
    btn.className = "save-btn";
    btn.textContent = "Save";
    btn.addEventListener("click", async function () {
      var res = await api("PATCH",
        "/api/marginalia/" + encodeURIComponent(marginalia.uuid),
        { content: ta.value });
      if (res) {
        highlights.set(res.uuid, res);
        showHighlightDetail(res);
      }
    });
    $panelContent.appendChild(btn);
  }

  /** Show an existing highlight's detail (text + note + edit). */
  function showHighlightDetail(marginalia) {
    openSidePanel();
    while ($panelContent.firstChild) $panelContent.removeChild($panelContent.firstChild);

    // Quoted highlight text.
    var ht = document.createElement("div");
    ht.className = "highlight-text";
    ht.textContent = marginalia.highlighted_text || "";
    $panelContent.appendChild(ht);

    // Note display.
    if (marginalia.content) {
      var noteP = document.createElement("p");
      noteP.style.lineHeight = "1.5";
      noteP.style.marginBottom = "8px";
      noteP.textContent = marginalia.content;
      $panelContent.appendChild(noteP);
    }

    // Edit button — switches to editor view.
    var editBtn = document.createElement("button");
    editBtn.className = "save-btn";
    editBtn.textContent = "Edit note";
    editBtn.addEventListener("click", function () {
      showNotePanel(marginalia);
    });
    $panelContent.appendChild(editBtn);

    // Close button
    var closeBtn = document.createElement("button");
    closeBtn.className = "save-btn";
    closeBtn.style.marginLeft = "8px";
    closeBtn.style.background = "var(--border)";
    closeBtn.style.color = "var(--text)";
    closeBtn.textContent = "Close";
    closeBtn.addEventListener("click", closeSidePanel);
    $panelContent.appendChild(closeBtn);
  }

  /* ── Search ────────────────────────────────────────────────── */

  function openSearch() {
    $searchBar.classList.add("visible");
    $searchInput.value = "";
    $searchInput.focus();
    clearSearchResults();
  }

  function closeSearch() {
    $searchBar.classList.remove("visible");
    $searchInput.value = "";
    clearSearchResults();
  }

  function clearSearchResults() {
    while ($searchResults.firstChild) $searchResults.removeChild($searchResults.firstChild);
  }

  async function runSearch(query) {
    clearSearchResults();
    if (!query || !query.trim()) return;

    var data = await api("GET",
      "/api/books/" + BOOK.id + "/search?q=" + encodeURIComponent(query) + "&limit=20");
    if (!data || !data.length) {
      var empty = document.createElement("div");
      empty.className = "search-hit";
      empty.textContent = "No results found.";
      $searchResults.appendChild(empty);
      return;
    }

    data.forEach(function (hit) {
      var row = document.createElement("div");
      row.className = "search-hit";
      row.setAttribute("data-fragment", escapeAttr(hit.fragment));

      // Label: segment type + index
      var lbl = document.createElement("span");
      lbl.className = "hit-label";
      lbl.textContent = (hit.title || hit.segment_type) + ": ";
      row.appendChild(lbl);

      // Snippet (sanitised).
      row.appendChild(safeSnippet(hit.snippet));

      // Click to jump.
      row.addEventListener("click", function () {
        if (adapter && hit.fragment) adapter.jumpToFragment(hit.fragment);
        closeSearch();
      });

      $searchResults.appendChild(row);
    });
  }

  /* ── Event wiring ──────────────────────────────────────────── */

  function wireEvents() {
    // Theme toggle
    $themeToggle.addEventListener("click", cycleTheme);

    // Page navigation buttons
    if ($navPrev) {
      $navPrev.addEventListener("click", function () {
        if (adapter && adapter.prev) adapter.prev();
      });
    }
    if ($navNext) {
      $navNext.addEventListener("click", function () {
        if (adapter && adapter.next) adapter.next();
      });
    }

    // Search toggle button
    $searchToggle.addEventListener("click", function () {
      if ($searchBar.classList.contains("visible")) closeSearch();
      else openSearch();
    });
    $searchClose.addEventListener("click", closeSearch);

    // Search input — debounced on keyup, immediate on Enter.
    $searchInput.addEventListener("keyup", function (e) {
      if (e.key === "Enter") {
        clearTimeout(searchDebounce);
        runSearch($searchInput.value);
        return;
      }
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(function () {
        runSearch($searchInput.value);
      }, 500);
    });

    // Ctrl-F / Cmd-F override, Escape, and arrow-key page navigation.
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        openSearch();
        return;
      }
      if (e.key === "Escape") {
        if ($searchBar.classList.contains("visible")) closeSearch();
        if ($sidePanel.classList.contains("visible")) closeSidePanel();
        hideHighlightToolbar();
        return;
      }
      // Page navigation. Skip when focus is in an input/textarea.
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        if (adapter && adapter.prev) { e.preventDefault(); adapter.prev(); }
      } else if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        if (adapter && adapter.next) { e.preventDefault(); adapter.next(); }
      }
    });

    // Also forward keydown from inside the EPUB iframe. EPUB.js installs
    // its own "keyreleased" events but they fire after the iframe document
    // has received the key; if the iframe has focus, outer listeners miss it.
    if (adapter && typeof adapter.onKeyDown === "function") {
      adapter.onKeyDown(function (key) {
        if (key === "ArrowLeft" || key === "PageUp") { adapter.prev(); }
        else if (key === "ArrowRight" || key === "PageDown" || key === " ") { adapter.next(); }
      });
    }

    // Highlight toolbar buttons.
    $btnHighlight.addEventListener("click", function () {
      if (!pendingSelection) return;
      createHighlight(pendingSelection.text, pendingSelection.anchor, false);
      hideHighlightToolbar();
    });
    $btnNote.addEventListener("click", function () {
      if (!pendingSelection) return;
      createHighlight(pendingSelection.text, pendingSelection.anchor, true);
      hideHighlightToolbar();
    });

    // Dismiss highlight toolbar on click outside.
    document.addEventListener("mousedown", function (e) {
      if ($hlToolbar.contains(e.target)) return;
      hideHighlightToolbar();
    });

    // End session on unload.
    window.addEventListener("beforeunload", endSession);
  }

  /* ── Init ──────────────────────────────────────────────────── */

  async function init() {
    initTheme();

    // Create format adapter.
    if (BOOK.format === "epub") {
      adapter = createEpubAdapter();
    } else if (BOOK.format === "pdf") {
      adapter = createPdfAdapter();
    } else {
      $viewer.textContent = "Unsupported format: " + BOOK.format;
      return;
    }

    // Initialise renderer.
    try {
      await adapter.init(BOOK.file_url, $viewer);
    } catch (err) {
      console.error("Adapter init failed:", err);
      $viewer.textContent = "Could not load book. " + (err.message || "");
      return;
    }

    // Propagate the current theme into the EPUB iframe now that the
    // rendition exists (themes had to be registered during init above).
    if (adapter && typeof adapter.applyContentTheme === "function") {
      adapter.applyContentTheme(themes[themeIndex]);
    }

    // Restore progress.
    var progress = await api("GET", "/api/reading/progress?book_id=" + BOOK.id);
    if (progress && progress.anchor) {
      try { await adapter.display(progress.anchor); } catch (_) {}
    }

    // Load and paint existing highlights.
    await loadHighlights();

    // Wire adapter events.
    adapter.onRelocated(function (loc) {
      syncProgress(loc.anchor, loc.percentage);
    });

    adapter.onSelected(function (sel) {
      if (sel.text.trim()) showHighlightToolbar(sel);
    });

    // Wire DOM events.
    wireEvents();

    // Start reading session.
    await startSession();
  }

  /* ── Bootstrap ─────────────────────────────────────────────── */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
