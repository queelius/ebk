"""
Export library to a self-contained HTML5 file with embedded CSS and JavaScript.

Creates an interactive, searchable, filterable library catalog that works offline.
All metadata, including contributors, series, keywords, etc., is preserved.
"""

from pathlib import Path
from typing import List, Optional
import json
from datetime import datetime


def export_to_html(books: List, output_path: Path, include_stats: bool = True, base_url: str = ""):
    """
    Export library to a single self-contained HTML file.

    Args:
        books: List of Book ORM objects
        output_path: Path to write HTML file
        include_stats: Include library statistics
        base_url: Base URL for file links (e.g., '/library' or 'https://example.com/books')
                  If empty, uses relative paths from HTML file location
    """

    # Serialize books to JSON-compatible format
    books_data = []
    for book in books:
        # Get primary cover if available
        cover_path = None
        if book.covers:
            primary_cover = next((c for c in book.covers if c.is_primary), book.covers[0])
            cover_path = primary_cover.path

        book_data = {
            'id': book.id,
            'title': book.title,
            'subtitle': book.subtitle,
            'authors': [{'name': a.name, 'sort_name': a.sort_name} for a in book.authors],
            'contributors': [
                {'name': c.name, 'role': c.role, 'file_as': c.file_as}
                for c in book.contributors
            ] if hasattr(book, 'contributors') else [],
            'subjects': [s.name for s in book.subjects],
            'language': book.language,
            'publisher': book.publisher,
            'publication_date': book.publication_date,
            'series': book.series,
            'series_index': book.series_index,
            'edition': book.edition,
            'description': book.description,
            'page_count': book.page_count,
            'word_count': book.word_count,
            'keywords': book.keywords or [],
            'rights': book.rights,
            'identifiers': [
                {'scheme': i.scheme, 'value': i.value}
                for i in book.identifiers
            ],
            'files': [
                {
                    'format': f.format,
                    'size_bytes': f.size_bytes,
                    'mime_type': f.mime_type,
                    'creator_application': f.creator_application,
                    'created_date': f.created_date.isoformat() if f.created_date else None,
                    'modified_date': f.modified_date.isoformat() if f.modified_date else None,
                    'path': f.path,  # Store relative path from library root
                }
                for f in book.files
            ],
            'cover_path': cover_path,
            'personal': {
                'rating': book.personal.rating if book.personal else None,
                'favorite': book.personal.favorite if book.personal else False,
                'reading_status': book.personal.reading_status if book.personal else 'unread',
                'tags': book.personal.personal_tags or [] if book.personal else [],
            },
            'created_at': book.created_at.isoformat(),
        }
        books_data.append(book_data)

    # Generate statistics
    stats = {}
    if include_stats:
        all_authors = set()
        all_subjects = set()
        all_languages = set()
        all_formats = set()
        series_count = 0

        for book in books:
            for author in book.authors:
                all_authors.add(author.name)
            for subject in book.subjects:
                all_subjects.add(subject.name)
            if book.language:
                all_languages.add(book.language)
            for file in book.files:
                all_formats.add(file.format)
            if book.series:
                series_count += 1

        stats = {
            'total_books': len(books),
            'total_authors': len(all_authors),
            'total_subjects': len(all_subjects),
            'languages': list(all_languages),
            'formats': list(all_formats),
            'books_in_series': series_count,
        }

    # Create HTML content
    html_content = _generate_html_template(books_data, stats, base_url)

    # Write to file
    output_path.write_text(html_content, encoding='utf-8')


def _generate_html_template(books_data: List[dict], stats: dict, base_url: str = "") -> str:
    """Generate the complete HTML template with embedded CSS and JavaScript."""

    books_json = json.dumps(books_data, indent=2, ensure_ascii=False)
    stats_json = json.dumps(stats, indent=2, ensure_ascii=False)
    base_url_json = json.dumps(base_url, ensure_ascii=False)
    export_date = datetime.now().isoformat()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>eBook Library Catalog</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: #2563eb;
            --primary-dark: #1e40af;
            --secondary: #64748b;
            --background: #f8fafc;
            --surface: #ffffff;
            --text: #1e293b;
            --text-light: #64748b;
            --border: #e2e8f0;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--background);
            color: var(--text);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        header {{
            background: var(--surface);
            border-bottom: 2px solid var(--border);
            padding: 20px 0;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        h1 {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 10px;
        }}

        .stats {{
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 15px;
            color: var(--text-light);
            font-size: 0.9rem;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .stat-value {{
            font-weight: 600;
            color: var(--text);
        }}

        .controls {{
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .search-bar {{
            width: 100%;
            padding: 12px 16px;
            font-size: 1rem;
            border: 2px solid var(--border);
            border-radius: 6px;
            margin-bottom: 15px;
            transition: border-color 0.2s;
        }}

        .search-bar:focus {{
            outline: none;
            border-color: var(--primary);
        }}

        .filters {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }}

        .filter-group {{
            flex: 1;
            min-width: 200px;
        }}

        .filter-group label {{
            display: block;
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 5px;
            color: var(--text-light);
        }}

        .filter-group select {{
            width: 100%;
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.9rem;
            background: white;
            cursor: pointer;
        }}

        .book-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}

        .book-card {{
            background: var(--surface);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }}

        .book-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.15);
        }}

        .book-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 12px;
        }}

        .book-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text);
            line-height: 1.3;
            flex: 1;
        }}

        .favorite-badge {{
            color: var(--warning);
            font-size: 1.2rem;
            margin-left: 8px;
        }}

        .book-subtitle {{
            font-size: 0.9rem;
            color: var(--text-light);
            margin-bottom: 8px;
        }}

        .book-authors {{
            font-size: 0.95rem;
            color: var(--text-light);
            margin-bottom: 8px;
        }}

        .book-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }}

        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-series {{
            background: #dbeafe;
            color: var(--primary);
        }}

        .badge-format {{
            background: #f3f4f6;
            color: var(--secondary);
        }}

        .badge-language {{
            background: #fef3c7;
            color: #92400e;
        }}

        .rating {{
            color: var(--warning);
            font-size: 0.9rem;
        }}

        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            padding: 20px;
            overflow-y: auto;
        }}

        .modal.active {{
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .modal-content {{
            background: var(--surface);
            border-radius: 12px;
            max-width: 800px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
        }}

        .modal-header {{
            padding: 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
        }}

        .modal-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text);
            flex: 1;
        }}

        .close-btn {{
            background: none;
            border: none;
            font-size: 2rem;
            color: var(--text-light);
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            line-height: 1;
        }}

        .close-btn:hover {{
            color: var(--text);
        }}

        .modal-body {{
            padding: 24px;
        }}

        .detail-section {{
            margin-bottom: 24px;
        }}

        .detail-label {{
            font-weight: 600;
            color: var(--text-light);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 8px;
        }}

        .detail-value {{
            color: var(--text);
            margin-bottom: 8px;
        }}

        .contributors-list, .identifiers-list {{
            list-style: none;
            padding: 0;
        }}

        .contributors-list li, .identifiers-list li {{
            padding: 4px 0;
            color: var(--text);
        }}

        .contributor-role {{
            color: var(--text-light);
            font-size: 0.875rem;
            margin-left: 8px;
        }}

        .file-link {{
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }}

        .file-link:hover {{
            color: var(--primary-dark);
            text-decoration: underline;
        }}

        .tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}

        .tag {{
            background: #e0e7ff;
            color: var(--primary);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.8rem;
        }}

        .no-results {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-light);
        }}

        .no-results-icon {{
            font-size: 4rem;
            margin-bottom: 16px;
        }}

        @media (max-width: 768px) {{
            .book-grid {{
                grid-template-columns: 1fr;
            }}

            .filters {{
                flex-direction: column;
            }}

            .stats {{
                flex-direction: column;
                gap: 8px;
            }}
        }}

        code {{
            background: rgba(37, 99, 235, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            color: var(--primary);
        }}

        #search-help ul {{
            list-style-type: none;
        }}

        #search-help li {{
            padding: 3px 0;
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>📚 eBook Library</h1>
            <div class="stats">
                <div class="stat-item">
                    <span>Total Books:</span>
                    <span class="stat-value" id="total-books">0</span>
                </div>
                <div class="stat-item">
                    <span>Authors:</span>
                    <span class="stat-value" id="total-authors">0</span>
                </div>
                <div class="stat-item">
                    <span>Subjects:</span>
                    <span class="stat-value" id="total-subjects">0</span>
                </div>
                <div class="stat-item">
                    <span>Exported:</span>
                    <span class="stat-value">{export_date[:10]}</span>
                </div>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="controls">
            <div style="position: relative; display: flex; align-items: center; gap: 8px;">
                <input
                    type="text"
                    class="search-bar"
                    id="search-input"
                    placeholder="Search books... (try: title:Python rating:>=4)"
                    style="flex: 1;"
                >
                <button
                    onclick="toggleSearchHelp()"
                    style="background: var(--secondary); color: white; border: none; border-radius: 6px; width: 36px; height: 36px; cursor: pointer; font-size: 1.2rem; display: flex; align-items: center; justify-content: center;"
                    title="Search Help"
                >
                    ?
                </button>
            </div>

            <div id="search-help" style="display: none; margin-top: 10px; padding: 15px; background: var(--card-bg); border-radius: 8px; border: 2px solid var(--primary); font-size: 0.875rem;">
                <h4 style="margin-top: 0; color: var(--primary);">Advanced Search Syntax</h4>

                <p style="margin: 5px 0;"><strong>Field Searches:</strong></p>
                <ul style="margin: 5px 0 10px 20px; padding: 0;">
                    <li><code>title:Python</code> - Search in title only</li>
                    <li><code>author:Knuth</code> - Search author name</li>
                    <li><code>tag:programming</code> - Search subjects/tags</li>
                    <li><code>description:algorithms</code> - Search description</li>
                    <li><code>series:TAOCP</code> - Search series name</li>
                </ul>

                <p style="margin: 5px 0;"><strong>Filters:</strong></p>
                <ul style="margin: 5px 0 10px 20px; padding: 0;">
                    <li><code>language:en</code> - Language code</li>
                    <li><code>format:pdf</code> - File format</li>
                    <li><code>rating:5</code> or <code>rating:>=4</code> - Rating filter</li>
                    <li><code>favorite:true</code> - Favorites only</li>
                    <li><code>status:reading</code> - Reading status</li>
                </ul>

                <p style="margin: 5px 0;"><strong>Boolean Logic:</strong></p>
                <ul style="margin: 5px 0 10px 20px; padding: 0;">
                    <li><code>python java</code> - Both terms (implicit AND)</li>
                    <li><code>python OR java</code> - Either term</li>
                    <li><code>NOT java</code> or <code>-java</code> - Exclude term</li>
                </ul>

                <p style="margin: 5px 0;"><strong>Quotes:</strong></p>
                <ul style="margin: 5px 0 10px 20px; padding: 0;">
                    <li><code>"machine learning"</code> - Exact phrase</li>
                    <li><code>author:"Donald Knuth"</code> - Field with phrase</li>
                </ul>

                <p style="margin: 5px 0;"><strong>Examples:</strong></p>
                <ul style="margin: 5px 0 0 20px; padding: 0;">
                    <li><code>title:Python rating:>=4 format:pdf</code></li>
                    <li><code>author:"Donald Knuth" series:TAOCP</code></li>
                    <li><code>tag:programming favorite:true NOT java</code></li>
                </ul>
            </div>

            <div class="filters">
                <div class="filter-group">
                    <label for="sort-field">Sort By</label>
                    <select id="sort-field">
                        <option value="title">Title</option>
                        <option value="created_at">Date Added</option>
                        <option value="publication_date">Publication Date</option>
                        <option value="rating">Rating</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="sort-order">Order</label>
                    <select id="sort-order">
                        <option value="asc">Ascending</option>
                        <option value="desc">Descending</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="language-filter">Language</label>
                    <select id="language-filter">
                        <option value="">All Languages</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="format-filter">Format</label>
                    <select id="format-filter">
                        <option value="">All Formats</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="series-filter">Series</label>
                    <select id="series-filter">
                        <option value="">All Books</option>
                        <option value="has-series">In Series</option>
                        <option value="no-series">Not in Series</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="favorite-filter">Favorites</label>
                    <select id="favorite-filter">
                        <option value="">All Books</option>
                        <option value="true">Favorites Only</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="rating-filter">Min Rating</label>
                    <select id="rating-filter">
                        <option value="">Any Rating</option>
                        <option value="1">1+ Stars</option>
                        <option value="2">2+ Stars</option>
                        <option value="3">3+ Stars</option>
                        <option value="4">4+ Stars</option>
                        <option value="5">5 Stars</option>
                    </select>
                </div>
            </div>
            <button onclick="clearFilters()" style="margin-top: 10px; padding: 8px 16px; background: var(--secondary); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem;">Clear Filters</button>
        </div>

        <div id="results-info" style="margin-bottom: 15px; color: var(--text-light); font-size: 0.9rem;"></div>

        <div class="book-grid" id="book-grid"></div>

        <div class="no-results" id="no-results" style="display: none;">
            <div class="no-results-icon">🔍</div>
            <h2>No books found</h2>
            <p>Try adjusting your search or filters</p>
        </div>

        <div id="pagination" style="display: flex; justify-content: center; align-items: center; gap: 10px; margin-top: 30px; flex-wrap: wrap;"></div>
    </div>

    <div class="modal" id="book-modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="modal-title"></h2>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <button class="btn-primary" onclick="toggleEditMode()" id="edit-mode-btn" style="padding: 6px 12px; font-size: 0.875rem;">Edit Metadata</button>
                    <button class="close-btn" onclick="closeModal()">&times;</button>
                </div>
            </div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>

    <script>
        // Embedded data
        const BOOKS = {books_json};
        const STATS = {stats_json};
        const BASE_URL = {base_url_json};

        // State
        let filteredBooks = [...BOOKS];
        let editMode = false;
        let currentBookId = null;
        let currentPage = 1;
        const booksPerPage = 50;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            populateStats();
            populateFilters();
            restoreStateFromURL();
            applyFilters();
            setupEventListeners();

            // Handle browser back/forward
            window.addEventListener('popstate', () => {{
                restoreStateFromURL();
                applyFilters();
            }});
        }});

        function populateStats() {{
            document.getElementById('total-books').textContent = STATS.total_books;
            document.getElementById('total-authors').textContent = STATS.total_authors;
            document.getElementById('total-subjects').textContent = STATS.total_subjects;
        }}

        function populateFilters() {{
            // Languages
            const languageSelect = document.getElementById('language-filter');
            STATS.languages.forEach(lang => {{
                const option = document.createElement('option');
                option.value = lang;
                option.textContent = lang.toUpperCase();
                languageSelect.appendChild(option);
            }});

            // Formats
            const formatSelect = document.getElementById('format-filter');
            STATS.formats.forEach(fmt => {{
                const option = document.createElement('option');
                option.value = fmt;
                option.textContent = fmt.toUpperCase();
                formatSelect.appendChild(option);
            }});
        }}

        // localStorage helpers
        function loadMetadataOverrides() {{
            const overrides = localStorage.getItem('ebk_metadata_overrides');
            return overrides ? JSON.parse(overrides) : {{}};
        }}

        function saveMetadataOverride(bookId, field, value) {{
            const overrides = loadMetadataOverrides();
            if (!overrides[bookId]) overrides[bookId] = {{}};
            overrides[bookId][field] = value;
            localStorage.setItem('ebk_metadata_overrides', JSON.stringify(overrides));
        }}

        function applyMetadataOverrides(book) {{
            const overrides = loadMetadataOverrides();
            if (overrides[book.id]) {{
                return {{ ...book, ...overrides[book.id] }};
            }}
            return book;
        }}

        // URL State Management
        function updateURL() {{
            const params = new URLSearchParams();

            if (currentPage > 1) params.set('page', currentPage);

            const searchQuery = document.getElementById('search-input').value;
            if (searchQuery) params.set('q', searchQuery);

            const language = document.getElementById('language-filter').value;
            if (language) params.set('language', language);

            const format = document.getElementById('format-filter').value;
            if (format) params.set('format', format);

            const series = document.getElementById('series-filter').value;
            if (series) params.set('series', series);

            const favorite = document.getElementById('favorite-filter').value;
            if (favorite) params.set('favorite', favorite);

            const rating = document.getElementById('rating-filter').value;
            if (rating) params.set('rating', rating);

            const sortField = document.getElementById('sort-field').value;
            if (sortField !== 'title') params.set('sort', sortField);

            const sortOrder = document.getElementById('sort-order').value;
            if (sortOrder !== 'asc') params.set('order', sortOrder);

            const newURL = params.toString() ? `?${{params.toString()}}` : window.location.pathname;
            window.history.pushState({{}}, '', newURL);
        }}

        function restoreStateFromURL() {{
            const params = new URLSearchParams(window.location.search);

            currentPage = parseInt(params.get('page')) || 1;

            document.getElementById('search-input').value = params.get('q') || '';
            document.getElementById('language-filter').value = params.get('language') || '';
            document.getElementById('format-filter').value = params.get('format') || '';
            document.getElementById('series-filter').value = params.get('series') || '';
            document.getElementById('favorite-filter').value = params.get('favorite') || '';
            document.getElementById('rating-filter').value = params.get('rating') || '';
            document.getElementById('sort-field').value = params.get('sort') || 'title';
            document.getElementById('sort-order').value = params.get('order') || 'asc';
        }}

        function applyFilters() {{
            filterBooks();
            updateURL();
        }}

        function setupEventListeners() {{
            document.getElementById('search-input').addEventListener('input', () => {{
                currentPage = 1;  // Reset to page 1 on new search
                applyFilters();
            }});
            document.getElementById('language-filter').addEventListener('change', () => {{
                currentPage = 1;
                applyFilters();
            }});
            document.getElementById('format-filter').addEventListener('change', () => {{
                currentPage = 1;
                applyFilters();
            }});
            document.getElementById('series-filter').addEventListener('change', () => {{
                currentPage = 1;
                applyFilters();
            }});
            document.getElementById('favorite-filter').addEventListener('change', () => {{
                currentPage = 1;
                applyFilters();
            }});
            document.getElementById('rating-filter').addEventListener('change', () => {{
                currentPage = 1;
                applyFilters();
            }});
            document.getElementById('sort-field').addEventListener('change', applyFilters);
            document.getElementById('sort-order').addEventListener('change', applyFilters);

            // Close modal on outside click
            document.getElementById('book-modal').addEventListener('click', (e) => {{
                if (e.target.id === 'book-modal') {{
                    closeModal();
                }}
            }});
        }}

        function filterBooks() {{
            const searchTerm = document.getElementById('search-input').value.toLowerCase();
            const languageFilter = document.getElementById('language-filter').value;
            const formatFilter = document.getElementById('format-filter').value;
            const seriesFilter = document.getElementById('series-filter').value;
            const favoriteFilter = document.getElementById('favorite-filter').value;
            const ratingFilter = document.getElementById('rating-filter').value;
            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;

            // Apply metadata overrides and filter
            filteredBooks = BOOKS.map(applyMetadataOverrides).filter(book => {{
                // Search
                if (searchTerm) {{
                    const searchable = [
                        book.title,
                        book.subtitle,
                        ...book.authors.map(a => a.name),
                        ...book.subjects,
                        ...book.keywords,
                        book.description
                    ].filter(x => x).join(' ').toLowerCase();

                    if (!searchable.includes(searchTerm)) return false;
                }}

                // Language
                if (languageFilter && book.language !== languageFilter) return false;

                // Format
                if (formatFilter && !book.files.some(f => f.format === formatFilter)) return false;

                // Series
                if (seriesFilter === 'has-series' && !book.series) return false;
                if (seriesFilter === 'no-series' && book.series) return false;

                // Favorite
                if (favoriteFilter === 'true' && !book.personal.favorite) return false;

                // Rating
                if (ratingFilter && (!book.personal.rating || book.personal.rating < parseFloat(ratingFilter))) return false;

                return true;
            }});

            // Sort
            filteredBooks.sort((a, b) => {{
                let aVal, bVal;

                switch(sortField) {{
                    case 'title':
                        aVal = (a.title || '').toLowerCase();
                        bVal = (b.title || '').toLowerCase();
                        break;
                    case 'created_at':
                        aVal = new Date(a.created_at || 0);
                        bVal = new Date(b.created_at || 0);
                        break;
                    case 'publication_date':
                        aVal = new Date(a.publication_date || 0);
                        bVal = new Date(b.publication_date || 0);
                        break;
                    case 'rating':
                        aVal = a.personal?.rating || 0;
                        bVal = b.personal?.rating || 0;
                        break;
                    default:
                        return 0;
                }}

                if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
                return 0;
            }});

            renderBooks();
        }}

        function clearFilters() {{
            document.getElementById('search-input').value = '';
            document.getElementById('language-filter').value = '';
            document.getElementById('format-filter').value = '';
            document.getElementById('series-filter').value = '';
            document.getElementById('favorite-filter').value = '';
            document.getElementById('rating-filter').value = '';
            document.getElementById('sort-field').value = 'title';
            document.getElementById('sort-order').value = 'asc';
            filterBooks();
        }}

        function renderBooks() {{
            const grid = document.getElementById('book-grid');
            const noResults = document.getElementById('no-results');
            const resultsInfo = document.getElementById('results-info');
            const pagination = document.getElementById('pagination');

            if (filteredBooks.length === 0) {{
                grid.style.display = 'none';
                noResults.style.display = 'block';
                resultsInfo.style.display = 'none';
                pagination.style.display = 'none';
                return;
            }}

            grid.style.display = 'grid';
            noResults.style.display = 'none';
            resultsInfo.style.display = 'block';

            // Pagination
            const totalPages = Math.ceil(filteredBooks.length / booksPerPage);
            const startIdx = (currentPage - 1) * booksPerPage;
            const endIdx = Math.min(startIdx + booksPerPage, filteredBooks.length);
            const booksToShow = filteredBooks.slice(startIdx, endIdx);

            // Update results info
            resultsInfo.textContent = `Showing ${{startIdx + 1}}-${{endIdx}} of ${{filteredBooks.length}} books`;

            grid.innerHTML = booksToShow.map(book => `
                <div class="book-card" onclick="showBookDetails(${{book.id}})">
                    ${{book.cover_path ? `
                        <div style="text-align: center; margin-bottom: 12px;">
                            <img src="${{BASE_URL ? BASE_URL + '/' + book.cover_path : book.cover_path}}"
                                 alt="Cover"
                                 style="max-width: 100%; max-height: 220px; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.15);"
                                 onerror="this.style.display='none'">
                        </div>
                    ` : ''}}
                    <div class="book-header">
                        <div class="book-title">
                            ${{escapeHtml(book.title)}}
                            ${{book.personal.favorite ? '<span class="favorite-badge">⭐</span>' : ''}}
                        </div>
                    </div>
                    ${{book.subtitle ? `<div class="book-subtitle">${{escapeHtml(book.subtitle)}}</div>` : ''}}
                    <div class="book-authors">
                        ${{book.authors.map(a => a.name).join(', ') || 'Unknown Author'}}
                    </div>
                    ${{book.publication_date ? `<div style="color: #6b7280; font-size: 0.875rem; margin-top: 4px;">📅 ${{book.publication_date}}</div>` : ''}}
                    ${{book.personal.rating ? `<div class="rating">${{'★'.repeat(Math.round(book.personal.rating))}} ${{book.personal.rating}}</div>` : ''}}
                    <div class="book-meta">
                        ${{book.series ? `<span class="badge badge-series">${{escapeHtml(book.series)}} #${{book.series_index}}</span>` : ''}}
                        ${{book.files.map(f => `<span class="badge badge-format">${{f.format.toUpperCase()}}</span>`).join('')}}
                        ${{book.language ? `<span class="badge badge-language">${{book.language.toUpperCase()}}</span>` : ''}}
                    </div>
                </div>
            `).join('');

            // Render pagination controls
            renderPagination(totalPages);
        }}

        function renderPagination(totalPages) {{
            const pagination = document.getElementById('pagination');

            if (totalPages <= 1) {{
                pagination.style.display = 'none';
                return;
            }}

            pagination.style.display = 'flex';

            let html = '';

            // Previous button
            html += `<button onclick="goToPage(${{currentPage - 1}})" ${{currentPage === 1 ? 'disabled' : ''}}
                style="padding: 8px 16px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; ${{currentPage === 1 ? 'opacity: 0.5; cursor: not-allowed;' : ''}}">
                ← Previous
            </button>`;

            // Page numbers
            const maxButtons = 7;
            let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
            let endPage = Math.min(totalPages, startPage + maxButtons - 1);

            if (endPage - startPage < maxButtons - 1) {{
                startPage = Math.max(1, endPage - maxButtons + 1);
            }}

            if (startPage > 1) {{
                html += `<button onclick="goToPage(1)" style="padding: 8px 12px; background: white; color: var(--text); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 0.875rem;">1</button>`;
                if (startPage > 2) {{
                    html += `<span style="padding: 8px;">...</span>`;
                }}
            }}

            for (let i = startPage; i <= endPage; i++) {{
                const isActive = i === currentPage;
                html += `<button onclick="goToPage(${{i}})"
                    style="padding: 8px 12px; background: ${{isActive ? 'var(--primary)' : 'white'}}; color: ${{isActive ? 'white' : 'var(--text)'}}; border: 1px solid ${{isActive ? 'var(--primary)' : 'var(--border)'}}; border-radius: 6px; cursor: pointer; font-size: 0.875rem; font-weight: ${{isActive ? '600' : '400'}};">
                    ${{i}}
                </button>`;
            }}

            if (endPage < totalPages) {{
                if (endPage < totalPages - 1) {{
                    html += `<span style="padding: 8px;">...</span>`;
                }}
                html += `<button onclick="goToPage(${{totalPages}})" style="padding: 8px 12px; background: white; color: var(--text); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 0.875rem;">${{totalPages}}</button>`;
            }}

            // Next button
            html += `<button onclick="goToPage(${{currentPage + 1}})" ${{currentPage === totalPages ? 'disabled' : ''}}
                style="padding: 8px 16px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.875rem; ${{currentPage === totalPages ? 'opacity: 0.5; cursor: not-allowed;' : ''}}">
                Next →
            </button>`;

            pagination.innerHTML = html;
        }}

        function goToPage(page) {{
            const totalPages = Math.ceil(filteredBooks.length / booksPerPage);
            if (page < 1 || page > totalPages) return;
            currentPage = page;
            renderBooks();
            updateURL();
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        function showBookDetails(bookId) {{
            currentBookId = bookId;
            editMode = false;
            document.getElementById('edit-mode-btn').textContent = 'Edit Metadata';

            const book = BOOKS.find(b => b.id === bookId);
            if (!book) return;

            const modal = document.getElementById('book-modal');
            const modalTitle = document.getElementById('modal-title');
            const modalBody = document.getElementById('modal-body');

            modalTitle.textContent = book.title;

            let html = '';

            // Cover image
            if (book.cover_path) {{
                html += `
                    <div style="text-align: center; margin-bottom: 20px;">
                        <img src="${{BASE_URL ? BASE_URL + '/' + book.cover_path : book.cover_path}}"
                             alt="Cover"
                             style="max-width: 300px; max-height: 400px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);"
                             onerror="this.style.display='none'">
                    </div>
                `;
            }}

            // Authors
            if (book.authors.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Authors</div>
                        <div class="detail-value">${{book.authors.map(a => a.name).join(', ')}}</div>
                    </div>
                `;
            }}

            // Contributors
            if (book.contributors && book.contributors.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Contributors</div>
                        <ul class="contributors-list">
                            ${{book.contributors.map(c => `<li>${{c.name}} <span class="contributor-role">(${{c.role}})</span></li>`).join('')}}
                        </ul>
                    </div>
                `;
            }}

            // Series
            if (book.series) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Series</div>
                        <div class="detail-value">${{book.series}} #${{book.series_index}}</div>
                    </div>
                `;
            }}

            // Description (rendered as HTML)
            if (book.description) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Description</div>
                        <div class="detail-value">${{book.description}}</div>
                    </div>
                `;
            }}

            // Metadata
            const metadata = [];
            if (book.publisher) metadata.push(`Publisher: ${{book.publisher}}`);
            if (book.publication_date) metadata.push(`Published: ${{book.publication_date}}`);
            if (book.edition) metadata.push(`Edition: ${{book.edition}}`);
            if (book.language) metadata.push(`Language: ${{book.language.toUpperCase()}}`);
            if (book.page_count) metadata.push(`Pages: ${{book.page_count}}`);

            if (metadata.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Metadata</div>
                        <div class="detail-value">${{metadata.join(' • ')}}</div>
                    </div>
                `;
            }}

            // Subjects
            if (book.subjects.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Subjects</div>
                        <div class="tags">
                            ${{book.subjects.map(s => `<span class="tag">${{s}}</span>`).join('')}}
                        </div>
                    </div>
                `;
            }}

            // Keywords
            if (book.keywords && book.keywords.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Keywords</div>
                        <div class="tags">
                            ${{book.keywords.map(k => `<span class="tag">${{k}}</span>`).join('')}}
                        </div>
                    </div>
                `;
            }}

            // Files
            if (book.files.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Files</div>
                        <ul class="contributors-list">
                            ${{book.files.map(f => {{
                                const fileUrl = BASE_URL ? `${{BASE_URL}}/${{f.path}}` : f.path;
                                return `
                                    <li>
                                        <a href="${{fileUrl}}" class="file-link" target="_blank">
                                            ${{f.format.toUpperCase()}}
                                        </a>
                                        • ${{formatBytes(f.size_bytes)}}
                                        ${{f.creator_application ? ` • Created with ${{f.creator_application}}` : ''}}
                                    </li>
                                `;
                            }}).join('')}}
                        </ul>
                    </div>
                `;
            }}

            // Identifiers
            if (book.identifiers.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Identifiers</div>
                        <ul class="identifiers-list">
                            ${{book.identifiers.map(i => `<li>${{i.scheme.toUpperCase()}}: ${{i.value}}</li>`).join('')}}
                        </ul>
                    </div>
                `;
            }}

            // Personal tags
            if (book.personal.tags && book.personal.tags.length > 0) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Personal Tags</div>
                        <div class="tags">
                            ${{book.personal.tags.map(t => `<span class="tag">${{t}}</span>`).join('')}}
                        </div>
                    </div>
                `;
            }}

            // Rights
            if (book.rights) {{
                html += `
                    <div class="detail-section">
                        <div class="detail-label">Rights</div>
                        <div class="detail-value">${{escapeHtml(book.rights)}}</div>
                    </div>
                `;
            }}

            modalBody.innerHTML = html;
            modal.classList.add('active');
        }}

        function closeModal() {{
            document.getElementById('book-modal').classList.remove('active');
            editMode = false;
            currentBookId = null;
        }}

        function toggleSearchHelp() {{
            const helpDiv = document.getElementById('search-help');
            if (helpDiv.style.display === 'none') {{
                helpDiv.style.display = 'block';
            }} else {{
                helpDiv.style.display = 'none';
            }}
        }}

        function toggleEditMode() {{
            editMode = !editMode;
            const btn = document.getElementById('edit-mode-btn');

            if (editMode) {{
                btn.textContent = 'Save & Close';
                renderEditMode();
            }} else {{
                btn.textContent = 'Edit Metadata';
                saveMetadataOverrides();
                showBookDetails(currentBookId);
            }}
        }}

        function renderEditMode() {{
            const book = BOOKS.find(b => b.id === currentBookId);
            if (!book) return;

            const overrides = loadMetadataOverrides()[currentBookId] || {{}};
            const modalBody = document.getElementById('modal-body');

            modalBody.innerHTML = `
                <div class="detail-section">
                    <p style="color: #6b7280; margin-bottom: 20px;">
                        ℹ️ Changes are saved locally in your browser and won't affect the original database.
                    </p>
                </div>

                <div class="detail-section">
                    <label class="detail-label">Title</label>
                    <input type="text" id="edit-title" class="form-control" value="${{escapeHtml(overrides.title || book.title)}}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">
                </div>

                <div class="detail-section">
                    <label class="detail-label">Subtitle</label>
                    <input type="text" id="edit-subtitle" class="form-control" value="${{escapeHtml(overrides.subtitle || book.subtitle || '')}}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">
                </div>

                <div class="detail-section">
                    <label class="detail-label">Publisher</label>
                    <input type="text" id="edit-publisher" class="form-control" value="${{escapeHtml(overrides.publisher || book.publisher || '')}}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">
                </div>

                <div class="detail-section">
                    <label class="detail-label">Publication Date</label>
                    <input type="text" id="edit-publication-date" class="form-control" value="${{escapeHtml(overrides.publication_date || book.publication_date || '')}}" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;" placeholder="YYYY-MM-DD">
                </div>

                <div class="detail-section">
                    <label class="detail-label">Rating (1-5)</label>
                    <input type="number" id="edit-rating" class="form-control" value="${{overrides.rating !== undefined ? overrides.rating : (book.personal.rating || '')}}" min="1" max="5" step="0.5" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">
                </div>

                <div class="detail-section">
                    <label class="detail-label">
                        <input type="checkbox" id="edit-favorite" ${{(overrides.favorite !== undefined ? overrides.favorite : book.personal.favorite) ? 'checked' : ''}}>
                        Favorite
                    </label>
                </div>

                <div class="detail-section">
                    <label class="detail-label">Description</label>
                    <textarea id="edit-description" class="form-control" rows="6" style="width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 4px;">${{escapeHtml(overrides.description || book.description || '')}}</textarea>
                </div>

                <div class="detail-section">
                    <button onclick="clearOverrides()" class="btn-secondary" style="padding: 8px 16px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Clear Local Overrides
                    </button>
                </div>
            `;
        }}

        function saveMetadataOverrides() {{
            const overrides = loadMetadataOverrides();
            if (!overrides[currentBookId]) overrides[currentBookId] = {{}};

            const title = document.getElementById('edit-title').value;
            const subtitle = document.getElementById('edit-subtitle').value;
            const publisher = document.getElementById('edit-publisher').value;
            const publication_date = document.getElementById('edit-publication-date').value;
            const rating = document.getElementById('edit-rating').value;
            const favorite = document.getElementById('edit-favorite').checked;
            const description = document.getElementById('edit-description').value;

            const book = BOOKS.find(b => b.id === currentBookId);

            // Only save if different from original
            if (title !== book.title) overrides[currentBookId].title = title;
            if (subtitle !== (book.subtitle || '')) overrides[currentBookId].subtitle = subtitle;
            if (publisher !== (book.publisher || '')) overrides[currentBookId].publisher = publisher;
            if (publication_date !== (book.publication_date || '')) overrides[currentBookId].publication_date = publication_date;
            if (rating !== (book.personal.rating || '')) overrides[currentBookId].rating = parseFloat(rating) || null;
            if (favorite !== book.personal.favorite) overrides[currentBookId].favorite = favorite;
            if (description !== (book.description || '')) overrides[currentBookId].description = description;

            localStorage.setItem('ebk_metadata_overrides', JSON.stringify(overrides));

            // Refresh the filtered books with overrides
            filteredBooks = BOOKS.map(applyMetadataOverrides);
            filterBooks();
        }}

        function clearOverrides() {{
            if (!confirm('Clear all local metadata overrides for this book?')) return;

            const overrides = loadMetadataOverrides();
            delete overrides[currentBookId];
            localStorage.setItem('ebk_metadata_overrides', JSON.stringify(overrides));

            editMode = false;
            showBookDetails(currentBookId);
            filterBooks();
        }}

        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function formatBytes(bytes) {{
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }}
    </script>
</body>
</html>'''
