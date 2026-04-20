/**
 * book-memex reader controller.
 *
 * Single IIFE, no framework, no build step. Drives EPUB.js or PDF.js through a
 * thin adapter interface and wires up highlight capture, progress sync,
 * reading sessions, in-book search, TOC, notes panel, and three-theme cycling.
 *
 * Security: all user-facing content built with createElement + textContent.
 * Server search snippets (containing <mark>) sanitised via DOMParser whitelist.
 */
(function () {
  "use strict";

  var BOOK = window.BOOK;
  if (!BOOK) return;

  var $viewer         = document.getElementById("viewer");
  var $searchBar      = document.getElementById("search-bar");
  var $searchInput    = document.getElementById("search-input");
  var $searchResults  = document.getElementById("search-results");
  var $searchClose    = document.getElementById("search-close");
  var $searchToggle   = document.getElementById("search-toggle");
  var $themeToggle    = document.getElementById("theme-toggle");
  var $navPrev        = document.getElementById("nav-prev");
  var $navNext        = document.getElementById("nav-next");
  var $tocToggle      = document.getElementById("toc-toggle");
  var $tocPanel       = document.getElementById("toc-panel");
  var $tocClose       = document.getElementById("toc-close");
  var $tocList        = document.getElementById("toc-list");
  var $sidePanel      = document.getElementById("side-panel");
  var $panelContent   = document.getElementById("panel-content");
  var $hlToolbar      = document.getElementById("highlight-toolbar");
  var $btnHighlight   = document.getElementById("btn-highlight");
  var $btnNote        = document.getElementById("btn-note");

  var adapter            = null;
  var sessionUuid        = null;
  var highlights         = new Map();
  var progressDebounce   = null;
  var searchDebounce     = null;
  var pendingSelection   = null;
  var themes             = ["light", "dark", "sepia"];
  var themeIndex         = 0;

  function escapeAttr(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#39;");
  }

  // Only text nodes and <mark> survive; everything else is stripped.
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
    }
    return frag;
  }

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

  function clearChildren(el) {
    while (el.firstChild) el.removeChild(el.firstChild);
  }

  /* ── Theme system ──────────────────────────────────────────── */

  // Per-theme palettes mirrored from reader.css, applied to the EPUB.js
  // iframe so book content respects the reader's theme.
  var READER_THEMES = {
    light:  { body: { "background": "#ffffff", "color": "#1a1a1a" } },
    dark:   { body: { "background": "#1a1a1a", "color": "#e0e0e0" } },
    sepia:  { body: { "background": "#f4ecd8", "color": "#5b4636" } },
  };

  function applyTheme(name) {
    document.documentElement.setAttribute("data-reader-theme", name);
    try { localStorage.setItem("bookMemexReaderTheme", name); } catch (_) {}
    if (adapter && adapter.applyContentTheme) adapter.applyContentTheme(name);
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

  function createEpubAdapter() {
    var book, rendition;
    return {
      async init(url, containerEl) {
        // Fetch as ArrayBuffer so EPUB.js treats it as a zipped EPUB rather
        // than resolving META-INF/container.xml relative to the URL path
        // (our /read/{id}/file URL has no .epub extension).
        var resp = await fetch(url);
        if (!resp.ok) throw new Error("Could not fetch EPUB file: " + resp.status);
        var buf = await resp.arrayBuffer();
        book = ePub(buf);
        rendition = book.renderTo(containerEl, { width: "100%", height: "100%" });
        Object.keys(READER_THEMES).forEach(function (name) {
          rendition.themes.register(name, READER_THEMES[name]);
        });
        await rendition.display();
      },

      applyContentTheme(name) {
        if (rendition && rendition.themes) {
          try { rendition.themes.select(name); } catch (_) {}
        }
      },

      display(anchor) {
        return anchor && anchor.cfi ? rendition.display(anchor.cfi) : rendition.display();
      },

      prev() { return rendition && rendition.prev && rendition.prev(); },
      next() { return rendition && rendition.next && rendition.next(); },

      getToc() {
        if (!book || !book.navigation) return [];
        var out = [];
        function walk(items, level) {
          if (!items) return;
          items.forEach(function (item) {
            out.push({
              label: (item.label || "").trim(),
              href:  item.href,
              level: level,
            });
            if (item.subitems && item.subitems.length) walk(item.subitems, level + 1);
          });
        }
        walk(book.navigation.toc, 0);
        return out;
      },

      jumpToHref(href) {
        if (rendition && href) rendition.display(href);
      },

      onKeyDown(callback) {
        if (rendition) rendition.on("keydown", function (e) { callback(e.key); });
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
          var iframeRect = sel.getRangeAt(0).getBoundingClientRect();

          // Translate iframe-local coords to main document coords.
          var iframe = containerEl.querySelector("iframe");
          var offset = iframe ? iframe.getBoundingClientRect() : { left: 0, top: 0 };
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
        return loc && loc.start ? { cfi: loc.start.cfi } : null;
      },

      jumpToFragment(fragment) {
        if (fragment && fragment.indexOf("epubcfi(") === 0) rendition.display(fragment);
      },
    };
  }

  function createPdfAdapter() {
    var pdfDoc     = null;
    var container  = null;
    var totalPages = 0;
    var currentPage = 1;
    var relocatedCb = null;
    var selectedCb  = null;
    var pageEls     = [];

    function scrollToPage(pageNum, behavior) {
      var el = pageEls[pageNum - 1];
      if (!el) return;
      el.scrollIntoView({ behavior: behavior || "smooth" });
      currentPage = pageNum;
    }

    function onScroll() {
      if (!pageEls.length) return;
      var viewMid = container.scrollTop + container.clientHeight / 2;
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

    async function renderPage(page, pageNum) {
      var scale    = 1.5;
      var viewport = page.getViewport({ scale: scale });

      var wrapper = document.createElement("div");
      wrapper.style.position = "relative";
      wrapper.style.marginBottom = "8px";
      wrapper.setAttribute("data-page", String(pageNum));

      var canvas = document.createElement("canvas");
      var ctx    = canvas.getContext("2d");
      canvas.width  = viewport.width;
      canvas.height = viewport.height;
      canvas.style.display = "block";
      canvas.style.width   = "100%";
      canvas.style.height  = "auto";
      wrapper.appendChild(canvas);

      await page.render({ canvasContext: ctx, viewport: viewport }).promise;

      var textContent = await page.getTextContent();
      var textDiv     = document.createElement("div");
      textDiv.style.position = "absolute";
      textDiv.style.left   = "0";
      textDiv.style.top    = "0";
      textDiv.style.width  = "100%";
      textDiv.style.height = "100%";
      textDiv.style.overflow = "hidden";

      textContent.items.forEach(function (item) {
        // tx = [scaleX, skewY, skewX, scaleY, translateX, translateY]
        // PDF origin is bottom-left, DOM is top-left.
        var tx = item.transform;
        var span = document.createElement("span");
        span.textContent = item.str;
        span.style.position   = "absolute";
        span.style.whiteSpace = "pre";
        span.style.fontSize   = (tx[0] * scale) + "px";
        span.style.fontFamily = "sans-serif";
        span.style.color      = "transparent";
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

        container.addEventListener("mouseup", function () {
          var sel = window.getSelection();
          if (!sel || sel.isCollapsed || !sel.toString().trim() || !selectedCb) return;

          var range = sel.getRangeAt(0);
          var rect  = range.getBoundingClientRect();

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
        if (anchor && anchor.page) scrollToPage(anchor.page, "auto");
      },

      onRelocated(cb) { relocatedCb = cb; },
      onSelected(cb)  { selectedCb  = cb; },

      prev() { if (currentPage > 1) scrollToPage(currentPage - 1); },
      next() { if (currentPage < totalPages) scrollToPage(currentPage + 1); },

      getToc() {
        var out = [];
        for (var i = 1; i <= totalPages; i++) {
          out.push({ label: "Page " + i, href: "page=" + i, level: 0 });
        }
        return out;
      },

      jumpToHref(href) {
        var m = href && href.match(/page=(\d+)/);
        if (m) scrollToPage(parseInt(m[1], 10));
      },

      onKeyDown() {},

      // Visual PDF highlight overlay deferred to post-v1. Highlights are
      // stored server-side and will be painted when the overlay lands.
      addHighlight() {},

      getCurrentAnchor() { return { page: currentPage }; },

      jumpToFragment(fragment) {
        var m = fragment && fragment.match(/page=(\d+)/);
        if (m) scrollToPage(parseInt(m[1], 10));
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

  // URL fragment mirrors the current anchor so the reader URL is
  // bookmarkable and shareable. replaceState avoids polluting history.
  //   EPUB:  /read/1#epubcfi(/6/4[chap1]!/4/2/1:0)
  //   PDF:   /read/1#page=47
  //   TXT:   /read/1#offset=0
  function anchorToFragment(anchor) {
    if (!anchor) return "";
    if (anchor.cfi) return anchor.cfi;
    if (anchor.page) return "page=" + anchor.page;
    if (anchor.offset !== undefined) return "offset=" + anchor.offset;
    return "";
  }

  function fragmentToAnchor(frag) {
    if (!frag) return null;
    frag = decodeURIComponent(frag.replace(/^#/, ""));
    if (!frag) return null;
    if (frag.indexOf("epubcfi(") === 0) return { cfi: frag };
    var m = frag.match(/^page=(\d+)$/);
    if (m) return { page: parseInt(m[1], 10) };
    m = frag.match(/^offset=(\d+)$/);
    if (m) return { offset: parseInt(m[1], 10) };
    return null;
  }

  function syncUrlFragment(anchor) {
    var frag = anchorToFragment(anchor);
    if (!frag) return;
    var newHash = "#" + frag;
    if (window.location.hash !== newHash) {
      var newUrl = window.location.pathname + window.location.search + newHash;
      try { history.replaceState(null, "", newUrl); } catch (_) {}
    }
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
    $hlToolbar.style.left = (r.left + r.width / 2 - 40) + "px";
    $hlToolbar.style.top  = (r.top + window.scrollY - 44) + "px";
    $hlToolbar.classList.add("visible");
  }

  function hideHighlightToolbar() {
    $hlToolbar.classList.remove("visible");
    pendingSelection = null;
  }

  /* ── TOC panel ─────────────────────────────────────────────── */

  function renderToc() {
    clearChildren($tocList);
    var entries = adapter && adapter.getToc ? adapter.getToc() : [];
    if (!entries.length) {
      var empty = document.createElement("div");
      empty.style.padding = "8px 16px";
      empty.style.color = "var(--text-muted)";
      empty.style.fontSize = "0.85rem";
      empty.textContent = "No table of contents available.";
      $tocList.appendChild(empty);
      return;
    }
    entries.forEach(function (entry) {
      var a = document.createElement("a");
      a.className = "toc-entry level-" + Math.min(entry.level || 0, 3);
      a.textContent = entry.label || "(untitled)";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        if (adapter && adapter.jumpToHref) adapter.jumpToHref(entry.href);
        closeToc();
      });
      $tocList.appendChild(a);
    });
  }

  function openToc() {
    renderToc();
    $tocPanel.classList.add("visible");
    $viewer.classList.add("toc-open");
  }

  function closeToc() {
    $tocPanel.classList.remove("visible");
    $viewer.classList.remove("toc-open");
  }

  /* ── Side panel (notes) ────────────────────────────────────── */

  function openSidePanel() {
    $sidePanel.classList.add("visible");
    $viewer.classList.add("panel-open");
  }

  function closeSidePanel() {
    $sidePanel.classList.remove("visible");
    $viewer.classList.remove("panel-open");
    clearChildren($panelContent);
  }

  function appendHighlightText(parent, marginalia) {
    var ht = document.createElement("div");
    ht.className = "highlight-text";
    ht.textContent = marginalia.highlighted_text || "";
    parent.appendChild(ht);
  }

  function showNotePanel(marginalia) {
    openSidePanel();
    clearChildren($panelContent);
    appendHighlightText($panelContent, marginalia);

    var label = document.createElement("label");
    label.textContent = "Note";
    label.style.display = "block";
    label.style.fontWeight = "600";
    label.style.margin = "8px 0 4px";
    $panelContent.appendChild(label);

    var ta = document.createElement("textarea");
    ta.placeholder = "Add a note...";
    ta.value = marginalia.content || "";
    $panelContent.appendChild(ta);

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

  function showHighlightDetail(marginalia) {
    openSidePanel();
    clearChildren($panelContent);
    appendHighlightText($panelContent, marginalia);

    if (marginalia.content) {
      var noteP = document.createElement("p");
      noteP.style.lineHeight = "1.5";
      noteP.style.marginBottom = "8px";
      noteP.textContent = marginalia.content;
      $panelContent.appendChild(noteP);
    }

    var editBtn = document.createElement("button");
    editBtn.className = "save-btn";
    editBtn.textContent = "Edit note";
    editBtn.addEventListener("click", function () { showNotePanel(marginalia); });
    $panelContent.appendChild(editBtn);

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
    clearChildren($searchResults);
  }

  function closeSearch() {
    $searchBar.classList.remove("visible");
    $searchInput.value = "";
    clearChildren($searchResults);
  }

  async function runSearch(query) {
    clearChildren($searchResults);
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

      var lbl = document.createElement("span");
      lbl.className = "hit-label";
      lbl.textContent = (hit.title || hit.segment_type) + ": ";
      row.appendChild(lbl);

      row.appendChild(safeSnippet(hit.snippet));

      row.addEventListener("click", function () {
        if (adapter && hit.fragment) adapter.jumpToFragment(hit.fragment);
        closeSearch();
      });

      $searchResults.appendChild(row);
    });
  }

  /* ── Event wiring ──────────────────────────────────────────── */

  function wireEvents() {
    $themeToggle.addEventListener("click", cycleTheme);

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

    if ($tocToggle) {
      $tocToggle.addEventListener("click", function () {
        if ($tocPanel.classList.contains("visible")) closeToc();
        else openToc();
      });
    }
    if ($tocClose) $tocClose.addEventListener("click", closeToc);

    $searchToggle.addEventListener("click", function () {
      if ($searchBar.classList.contains("visible")) closeSearch();
      else openSearch();
    });
    $searchClose.addEventListener("click", closeSearch);

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

    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        openSearch();
        return;
      }
      if (e.key === "Escape") {
        if ($searchBar.classList.contains("visible")) closeSearch();
        if ($sidePanel.classList.contains("visible")) closeSidePanel();
        if ($tocPanel && $tocPanel.classList.contains("visible")) closeToc();
        hideHighlightToolbar();
        return;
      }
      var tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        if (adapter && adapter.prev) { e.preventDefault(); adapter.prev(); }
      } else if (e.key === "ArrowRight" || e.key === "PageDown" || e.key === " ") {
        if (adapter && adapter.next) { e.preventDefault(); adapter.next(); }
      }
    });

    // Forward keydown from inside the EPUB iframe: EPUB.js's own key events
    // fire after the iframe has swallowed the key, so outer listeners miss
    // it when the iframe has focus.
    if (adapter && adapter.onKeyDown) {
      adapter.onKeyDown(function (key) {
        if (key === "ArrowLeft" || key === "PageUp") adapter.prev();
        else if (key === "ArrowRight" || key === "PageDown" || key === " ") adapter.next();
      });
    }

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

    document.addEventListener("mousedown", function (e) {
      if ($hlToolbar.contains(e.target)) return;
      hideHighlightToolbar();
    });

    window.addEventListener("beforeunload", endSession);
  }

  /* ── Init ──────────────────────────────────────────────────── */

  async function init() {
    initTheme();

    if (BOOK.format === "epub") {
      adapter = createEpubAdapter();
    } else if (BOOK.format === "pdf") {
      adapter = createPdfAdapter();
    } else {
      $viewer.textContent = "Unsupported format: " + BOOK.format;
      return;
    }

    try {
      await adapter.init(BOOK.file_url, $viewer);
    } catch (err) {
      console.error("Adapter init failed:", err);
      $viewer.textContent = "Could not load book. " + (err.message || "");
      return;
    }

    // Propagate the current theme into the EPUB iframe now that the
    // rendition exists (themes had to be registered during init above).
    if (adapter.applyContentTheme) adapter.applyContentTheme(themes[themeIndex]);

    // Seek to initial position. URL fragment wins over server-stored
    // progress so shared links land where pasted.
    var initialAnchor = fragmentToAnchor(window.location.hash);
    if (!initialAnchor) {
      var progress = await api("GET", "/api/reading/progress?book_id=" + BOOK.id);
      if (progress && progress.anchor) initialAnchor = progress.anchor;
    }
    if (initialAnchor) {
      try { await adapter.display(initialAnchor); } catch (_) {}
    }

    await loadHighlights();

    adapter.onRelocated(function (loc) {
      syncProgress(loc.anchor, loc.percentage);
      syncUrlFragment(loc.anchor);
    });

    // React to manual hash edits (pasted share link, browser history).
    window.addEventListener("hashchange", function () {
      var anchor = fragmentToAnchor(window.location.hash);
      if (anchor) { try { adapter.display(anchor); } catch (_) {} }
    });

    adapter.onSelected(function (sel) {
      if (sel.text.trim()) showHighlightToolbar(sel);
    });

    wireEvents();
    await startSession();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
