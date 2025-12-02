"""
Export library to a self-contained HTML5 file with embedded CSS and JavaScript.

Creates an interactive, searchable, filterable library catalog that works offline.
All metadata, including contributors, series, keywords, etc., is preserved.

Features:
- Dark/light mode toggle
- Grid/list/table view modes
- Advanced search syntax (field:value, boolean operators)
- Sidebar navigation (authors, subjects, series)
- Keyboard shortcuts (/, Escape, j/k navigation)
- Print-friendly styling
- Reading queue display
- Responsive mobile design
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
    authors_set = set()
    subjects_set = set()
    series_set = set()
    languages_set = set()
    formats_set = set()

    for book in books:
        # Get primary cover if available
        cover_path = None
        if book.covers:
            primary_cover = next((c for c in book.covers if c.is_primary), book.covers[0])
            cover_path = primary_cover.path

        # Collect for sidebar navigation
        for author in book.authors:
            authors_set.add(author.name)
        for subject in book.subjects:
            subjects_set.add(subject.name)
        if book.series:
            series_set.add(book.series)
        if book.language:
            languages_set.add(book.language)
        for file in book.files:
            formats_set.add(file.format.upper())

        # Get queue position if available
        queue_position = None
        if book.personal and hasattr(book.personal, 'queue_position'):
            queue_position = book.personal.queue_position

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
                    'path': f.path,
                }
                for f in book.files
            ],
            'cover_path': cover_path,
            'personal': {
                'rating': book.personal.rating if book.personal else None,
                'favorite': book.personal.favorite if book.personal else False,
                'reading_status': book.personal.reading_status if book.personal else 'unread',
                'reading_progress': book.personal.reading_progress if book.personal else 0,
                'queue_position': queue_position,
                'tags': book.personal.personal_tags or [] if book.personal else [],
            },
            'created_at': book.created_at.isoformat(),
        }
        books_data.append(book_data)

    # Generate statistics and navigation data
    stats = {
        'total_books': len(books),
        'total_authors': len(authors_set),
        'total_subjects': len(subjects_set),
        'total_series': len(series_set),
        'languages': sorted(list(languages_set)),
        'formats': sorted(list(formats_set)),
    }

    nav_data = {
        'authors': sorted(list(authors_set)),
        'subjects': sorted(list(subjects_set)),
        'series': sorted(list(series_set)),
    }

    # Create HTML content
    html_content = _generate_html_template(books_data, stats, nav_data, base_url)

    # Write to file
    output_path.write_text(html_content, encoding='utf-8')


def _generate_html_template(books_data: List[dict], stats: dict, nav_data: dict, base_url: str = "") -> str:
    """Generate the complete HTML template with embedded CSS and JavaScript."""

    books_json = json.dumps(books_data, indent=None, ensure_ascii=False)
    stats_json = json.dumps(stats, indent=None, ensure_ascii=False)
    nav_json = json.dumps(nav_data, indent=None, ensure_ascii=False)
    base_url_json = json.dumps(base_url, ensure_ascii=False)
    export_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ebk Library</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --bg-tertiary: #f1f5f9;
            --bg-hover: #e2e8f0;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --border: #e2e8f0;
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --accent-light: #eef2ff;
            --success: #10b981;
            --success-light: #d1fae5;
            --warning: #f59e0b;
            --warning-light: #fef3c7;
            --danger: #ef4444;
            --danger-light: #fee2e2;
            --shadow: 0 1px 3px rgba(0,0,0,0.1);
            --shadow-lg: 0 4px 12px rgba(0,0,0,0.1);
            --radius: 8px;
            --radius-lg: 12px;
            --transition: 0.15s ease;
        }}

        [data-theme="dark"] {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --bg-hover: #475569;
            --text-primary: #f1f5f9;
            --text-secondary: #cbd5e1;
            --text-muted: #64748b;
            --border: #334155;
            --accent-light: #312e81;
            --success-light: #064e3b;
            --warning-light: #78350f;
            --danger-light: #7f1d1d;
            --shadow: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-lg: 0 4px 12px rgba(0,0,0,0.3);
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* Layout */
        .app-container {{
            display: flex;
            min-height: 100vh;
        }}

        .sidebar {{
            width: 280px;
            background: var(--bg-secondary);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            z-index: 100;
            transform: translateX(-100%);
            transition: transform 0.3s ease;
        }}

        .sidebar.open {{
            transform: translateX(0);
        }}

        @media (min-width: 1024px) {{
            .sidebar {{
                transform: translateX(0);
                position: sticky;
                height: 100vh;
            }}
        }}

        .sidebar-header {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
        }}

        .sidebar-logo {{
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .logo-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent), #8b5cf6);
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            color: white;
        }}

        .sidebar-nav {{
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }}

        .nav-section {{
            margin-bottom: 16px;
        }}

        .nav-section-title {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            padding: 8px 12px;
        }}

        .nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: var(--radius);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s ease;
            font-size: 0.9rem;
        }}

        .nav-item:hover {{
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }}

        .nav-item.active {{
            background: var(--accent);
            color: white;
        }}

        .nav-item-count {{
            margin-left: auto;
            font-size: 0.75rem;
            background: var(--bg-tertiary);
            padding: 2px 8px;
            border-radius: 12px;
            color: var(--text-muted);
        }}

        .nav-item.active .nav-item-count {{
            background: rgba(255,255,255,0.2);
            color: white;
        }}

        /* Main Content */
        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }}

        @media (min-width: 1024px) {{
            .main-content {{
                margin-left: 0;
            }}
        }}

        /* Header */
        .header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            position: sticky;
            top: 0;
            z-index: 50;
        }}

        .menu-toggle {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border: none;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            cursor: pointer;
            color: var(--text-primary);
            font-size: 1.25rem;
        }}

        @media (min-width: 1024px) {{
            .menu-toggle {{
                display: none;
            }}
        }}

        .search-container {{
            flex: 1;
            max-width: 600px;
            position: relative;
        }}

        .search-input {{
            width: 100%;
            padding: 10px 16px 10px 44px;
            border: 2px solid var(--border);
            border-radius: var(--radius);
            font-size: 0.95rem;
            background: var(--bg-primary);
            color: var(--text-primary);
            transition: border-color 0.2s;
        }}

        .search-input:focus {{
            outline: none;
            border-color: var(--accent);
        }}

        .search-input::placeholder {{
            color: var(--text-muted);
        }}

        .search-icon {{
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
        }}

        .header-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .icon-btn {{
            display: flex;
            align-items: center;
            justify-content: center;
            width: 40px;
            height: 40px;
            border: none;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            cursor: pointer;
            color: var(--text-secondary);
            font-size: 1.1rem;
            transition: all 0.15s ease;
        }}

        .icon-btn:hover {{
            background: var(--accent);
            color: white;
        }}

        .icon-btn.active {{
            background: var(--accent);
            color: white;
        }}

        /* Toolbar */
        .toolbar {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .filter-group {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .filter-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .filter-select {{
            padding: 6px 12px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 0.85rem;
            background: var(--bg-primary);
            color: var(--text-primary);
            cursor: pointer;
        }}

        .results-info {{
            margin-left: auto;
            font-size: 0.85rem;
            color: var(--text-muted);
        }}

        /* Stats Bar */
        .stats-bar {{
            display: flex;
            gap: 16px;
            padding: 16px 24px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            min-width: fit-content;
        }}

        .stat-icon {{
            width: 40px;
            height: 40px;
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }}

        .stat-icon.books {{ background: var(--accent-light); color: var(--accent); }}
        .stat-icon.authors {{ background: var(--success-light); color: var(--success); }}
        .stat-icon.subjects {{ background: var(--warning-light); color: var(--warning); }}
        .stat-icon.series {{ background: var(--danger-light); color: var(--danger); }}

        .stat-content {{ display: flex; flex-direction: column; }}
        .stat-value {{ font-size: 1.25rem; font-weight: 700; color: var(--text-primary); line-height: 1.2; }}
        .stat-label {{ font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }}

        /* Content Area */
        .content {{
            flex: 1;
            padding: 24px;
            overflow-y: auto;
        }}

        /* Grid View */
        .book-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
        }}

        .book-card {{
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }}

        .book-card:hover {{
            transform: translateY(-4px);
            box-shadow: var(--shadow-lg);
        }}

        .book-cover {{
            aspect-ratio: 2/3;
            background: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }}

        .book-cover img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .book-cover-placeholder {{
            font-size: 3rem;
            color: var(--text-muted);
        }}

        .book-info {{
            padding: 12px;
        }}

        .book-title {{
            font-size: 0.9rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.3;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}

        .book-author {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .book-meta {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}

        .book-badge {{
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-format {{
            background: var(--bg-tertiary);
            color: var(--text-secondary);
        }}

        .badge-favorite {{
            background: #fef3c7;
            color: #92400e;
        }}

        .badge-queue {{
            background: #dbeafe;
            color: #1e40af;
        }}

        .book-rating {{
            color: var(--warning);
            font-size: 0.75rem;
        }}

        /* List View */
        .book-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .book-list-item {{
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 16px;
            display: flex;
            gap: 16px;
            align-items: flex-start;
            box-shadow: var(--shadow);
            cursor: pointer;
            transition: box-shadow 0.2s;
        }}

        .book-list-item:hover {{
            box-shadow: var(--shadow-lg);
        }}

        .book-list-cover {{
            width: 60px;
            height: 90px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            flex-shrink: 0;
        }}

        .book-list-cover img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .book-list-info {{
            flex: 1;
            min-width: 0;
        }}

        .book-list-title {{
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 4px;
        }}

        .book-list-author {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        .book-list-meta {{
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--text-muted);
            flex-wrap: wrap;
        }}

        /* Table View */
        .book-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}

        .book-table th {{
            text-align: left;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border);
            cursor: pointer;
            user-select: none;
        }}

        .book-table th:hover {{
            background: var(--border);
        }}

        .book-table td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
        }}

        .book-table tr:hover td {{
            background: var(--bg-tertiary);
        }}

        .table-title {{
            font-weight: 500;
            cursor: pointer;
        }}

        .table-title:hover {{
            color: var(--accent);
        }}

        /* Modal */
        .modal-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 200;
            padding: 20px;
            overflow-y: auto;
        }}

        .modal-overlay.active {{
            display: flex;
            align-items: flex-start;
            justify-content: center;
        }}

        .modal {{
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            max-width: 800px;
            width: 100%;
            margin-top: 40px;
            box-shadow: var(--shadow-lg);
        }}

        .modal-header {{
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
        }}

        .modal-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .modal-close {{
            width: 32px;
            height: 32px;
            border: none;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 1.25rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .modal-close:hover {{
            background: var(--danger);
            color: white;
        }}

        .modal-body {{
            padding: 24px;
            max-height: 70vh;
            overflow-y: auto;
        }}

        .modal-cover {{
            text-align: center;
            margin-bottom: 24px;
        }}

        .modal-cover img {{
            max-width: 200px;
            max-height: 300px;
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
        }}

        .detail-section {{
            margin-bottom: 20px;
        }}

        .detail-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}

        .detail-value {{
            color: var(--text-primary);
        }}

        .detail-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}

        .tag {{
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            padding: 4px 10px;
            border-radius: 16px;
            font-size: 0.8rem;
        }}

        .file-list {{
            list-style: none;
        }}

        .file-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }}

        .file-item:last-child {{
            border-bottom: none;
        }}

        .file-link {{
            color: var(--accent);
            text-decoration: none;
            font-weight: 500;
        }}

        .file-link:hover {{
            text-decoration: underline;
        }}

        .file-size {{
            color: var(--text-muted);
            font-size: 0.85rem;
        }}

        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }}

        .empty-state-icon {{
            font-size: 4rem;
            margin-bottom: 16px;
        }}

        .empty-state h3 {{
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        /* Pagination */
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 24px;
            flex-wrap: wrap;
        }}

        .page-btn {{
            padding: 8px 14px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-primary);
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.15s ease;
        }}

        .page-btn:hover:not(:disabled) {{
            border-color: var(--accent);
            color: var(--accent);
        }}

        .page-btn.active {{
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }}

        .page-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        /* Keyboard shortcuts hint */
        .keyboard-hint {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 12px 16px;
            font-size: 0.8rem;
            color: var(--text-muted);
            box-shadow: var(--shadow-lg);
            z-index: 50;
        }}

        .kbd {{
            display: inline-block;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 2px 6px;
            font-family: monospace;
            font-size: 0.75rem;
            margin: 0 2px;
        }}

        /* Sidebar overlay for mobile */
        .sidebar-overlay {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 99;
        }}

        .sidebar-overlay.active {{
            display: block;
        }}

        /* Print styles */
        @media print {{
            .sidebar, .header, .toolbar, .stats-bar, .pagination, .keyboard-hint {{
                display: none !important;
            }}
            .main-content {{
                margin-left: 0 !important;
            }}
            .book-card, .book-list-item {{
                break-inside: avoid;
            }}
        }}

        /* Scrollbar styling */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}

        ::-webkit-scrollbar-track {{
            background: var(--bg-primary);
        }}

        ::-webkit-scrollbar-thumb {{
            background: var(--border);
            border-radius: 4px;
        }}

        ::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="sidebar-overlay" onclick="toggleSidebar()"></div>

    <div class="app-container">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-logo">
                    <div class="logo-icon">📚</div>
                    <span>ebk Library</span>
                </div>
            </div>
            <nav class="sidebar-nav">
                <div class="nav-section">
                    <div class="nav-section-title">Library</div>
                    <div class="nav-item active" data-filter="all" onclick="setFilter('all')">
                        <span>📖</span> All Books
                        <span class="nav-item-count" id="count-all">0</span>
                    </div>
                    <div class="nav-item" data-filter="favorites" onclick="setFilter('favorites')">
                        <span>⭐</span> Favorites
                        <span class="nav-item-count" id="count-favorites">0</span>
                    </div>
                    <div class="nav-item" data-filter="queue" onclick="setFilter('queue')">
                        <span>📋</span> Reading Queue
                        <span class="nav-item-count" id="count-queue">0</span>
                    </div>
                    <div class="nav-item" data-filter="reading" onclick="setFilter('reading')">
                        <span>📖</span> Currently Reading
                        <span class="nav-item-count" id="count-reading">0</span>
                    </div>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">Browse</div>
                    <div class="nav-item" data-filter="authors" onclick="toggleSubnav('authors')">
                        <span>👤</span> Authors
                        <span class="nav-item-count" id="count-authors">0</span>
                    </div>
                    <div id="subnav-authors" class="subnav" style="display:none; max-height: 200px; overflow-y: auto; margin-left: 20px;"></div>
                    <div class="nav-item" data-filter="subjects" onclick="toggleSubnav('subjects')">
                        <span>🏷️</span> Subjects
                        <span class="nav-item-count" id="count-subjects">0</span>
                    </div>
                    <div id="subnav-subjects" class="subnav" style="display:none; max-height: 200px; overflow-y: auto; margin-left: 20px;"></div>
                    <div class="nav-item" data-filter="series" onclick="toggleSubnav('series')">
                        <span>📚</span> Series
                        <span class="nav-item-count" id="count-series">0</span>
                    </div>
                    <div id="subnav-series" class="subnav" style="display:none; max-height: 200px; overflow-y: auto; margin-left: 20px;"></div>
                </div>
            </nav>
            <div style="padding: 16px; border-top: 1px solid var(--border); font-size: 0.75rem; color: var(--text-muted);">
                Exported: {export_date}
            </div>
        </aside>

        <main class="main-content">
            <header class="header">
                <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
                <div class="search-container">
                    <span class="search-icon">🔍</span>
                    <input type="text" class="search-input" id="search" placeholder="Search... (try title:python or author:knuth)" autocomplete="off">
                </div>
                <div class="header-actions">
                    <button class="icon-btn active" id="view-grid" onclick="setView('grid')" title="Grid View">▦</button>
                    <button class="icon-btn" id="view-list" onclick="setView('list')" title="List View">☰</button>
                    <button class="icon-btn" id="view-table" onclick="setView('table')" title="Table View">▤</button>
                    <button class="icon-btn" id="theme-toggle" onclick="toggleTheme()" title="Toggle Dark Mode">🌓</button>
                </div>
            </header>

            <div class="toolbar">
                <div class="filter-group">
                    <span class="filter-label">Sort:</span>
                    <select class="filter-select" id="sort-field" onchange="applyFilters()">
                        <option value="title">Title</option>
                        <option value="author">Author</option>
                        <option value="date_added">Date Added</option>
                        <option value="publication_date">Publication Date</option>
                        <option value="rating">Rating</option>
                    </select>
                    <select class="filter-select" id="sort-order" onchange="applyFilters()">
                        <option value="asc">A-Z</option>
                        <option value="desc">Z-A</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Language:</span>
                    <select class="filter-select" id="filter-language" onchange="applyFilters()">
                        <option value="">All</option>
                    </select>
                </div>
                <div class="filter-group">
                    <span class="filter-label">Format:</span>
                    <select class="filter-select" id="filter-format" onchange="applyFilters()">
                        <option value="">All</option>
                    </select>
                </div>
                <div class="results-info" id="results-info"></div>
            </div>

            <div class="stats-bar">
                <div class="stat-item">
                    <div class="stat-icon books">📚</div>
                    <div class="stat-content">
                        <span class="stat-value" id="stat-books">0</span>
                        <span class="stat-label">Books</span>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon authors">👤</div>
                    <div class="stat-content">
                        <span class="stat-value" id="stat-authors">0</span>
                        <span class="stat-label">Authors</span>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon subjects">🏷️</div>
                    <div class="stat-content">
                        <span class="stat-value" id="stat-subjects">0</span>
                        <span class="stat-label">Subjects</span>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon series">📖</div>
                    <div class="stat-content">
                        <span class="stat-value" id="stat-series">0</span>
                        <span class="stat-label">Series</span>
                    </div>
                </div>
            </div>

            <div class="content">
                <div id="book-container"></div>
                <div class="empty-state" id="empty-state" style="display:none;">
                    <div class="empty-state-icon">📭</div>
                    <h3>No books found</h3>
                    <p>Try adjusting your search or filters</p>
                </div>
                <div class="pagination" id="pagination"></div>
            </div>
        </main>
    </div>

    <div class="modal-overlay" id="modal" onclick="if(event.target===this)closeModal()">
        <div class="modal">
            <div class="modal-header">
                <h2 class="modal-title" id="modal-title"></h2>
                <button class="modal-close" onclick="closeModal()">×</button>
            </div>
            <div class="modal-body" id="modal-body"></div>
        </div>
    </div>

    <div class="keyboard-hint" id="keyboard-hint">
        <kbd>/</kbd> Search &nbsp; <kbd>Esc</kbd> Close &nbsp; <kbd>j</kbd><kbd>k</kbd> Navigate
    </div>

    <script>
        // Data
        const BOOKS = {books_json};
        const STATS = {stats_json};
        const NAV = {nav_json};
        const BASE_URL = {base_url_json};

        // State
        let currentView = 'grid';
        let currentFilter = 'all';
        let currentSubfilter = null;
        let filteredBooks = [...BOOKS];
        let currentPage = 1;
        const perPage = 48;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            initTheme();
            populateFilters();
            updateCounts();
            applyFilters();
            setupKeyboardShortcuts();
        }});

        function initTheme() {{
            const saved = localStorage.getItem('ebk_theme');
            if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
                document.documentElement.setAttribute('data-theme', 'dark');
            }}
        }}

        function toggleTheme() {{
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
            localStorage.setItem('ebk_theme', isDark ? 'light' : 'dark');
        }}

        function toggleSidebar() {{
            document.getElementById('sidebar').classList.toggle('open');
            document.querySelector('.sidebar-overlay').classList.toggle('active');
        }}

        function populateFilters() {{
            const langSelect = document.getElementById('filter-language');
            STATS.languages.forEach(l => {{
                const opt = document.createElement('option');
                opt.value = l;
                opt.textContent = l.toUpperCase();
                langSelect.appendChild(opt);
            }});

            const formatSelect = document.getElementById('filter-format');
            STATS.formats.forEach(f => {{
                const opt = document.createElement('option');
                opt.value = f;
                opt.textContent = f;
                formatSelect.appendChild(opt);
            }});
        }}

        function updateCounts() {{
            // Update sidebar counts
            document.getElementById('count-all').textContent = BOOKS.length;
            document.getElementById('count-favorites').textContent = BOOKS.filter(b => b.personal?.favorite).length;
            document.getElementById('count-queue').textContent = BOOKS.filter(b => b.personal?.queue_position).length;
            document.getElementById('count-reading').textContent = BOOKS.filter(b => b.personal?.reading_status === 'reading').length;
            document.getElementById('count-authors').textContent = NAV.authors.length;
            document.getElementById('count-subjects').textContent = NAV.subjects.length;
            document.getElementById('count-series').textContent = NAV.series.length;

            // Update stats bar
            document.getElementById('stat-books').textContent = STATS.total_books.toLocaleString();
            document.getElementById('stat-authors').textContent = STATS.total_authors.toLocaleString();
            document.getElementById('stat-subjects').textContent = STATS.total_subjects.toLocaleString();
            document.getElementById('stat-series').textContent = STATS.total_series.toLocaleString();
        }}

        function toggleSubnav(type) {{
            const el = document.getElementById('subnav-' + type);
            if (el.style.display === 'none') {{
                el.style.display = 'block';
                const items = NAV[type].slice(0, 50);
                el.innerHTML = items.map(item =>
                    `<div class="nav-item" style="padding: 6px 12px; font-size: 0.8rem;" onclick="setSubfilter('${{type}}', '${{item.replace(/'/g, "\\\\'")}}')">
                        ${{item.length > 30 ? item.substring(0, 30) + '...' : item}}
                    </div>`
                ).join('');
                if (NAV[type].length > 50) {{
                    el.innerHTML += `<div style="padding: 6px 12px; font-size: 0.75rem; color: var(--text-muted);">+ ${{NAV[type].length - 50}} more</div>`;
                }}
            }} else {{
                el.style.display = 'none';
            }}
        }}

        function setFilter(filter) {{
            currentFilter = filter;
            currentSubfilter = null;
            currentPage = 1;
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            document.querySelector(`.nav-item[data-filter="${{filter}}"]`)?.classList.add('active');
            applyFilters();
            if (window.innerWidth < 1024) toggleSidebar();
        }}

        function setSubfilter(type, value) {{
            currentFilter = type;
            currentSubfilter = value;
            currentPage = 1;
            applyFilters();
            if (window.innerWidth < 1024) toggleSidebar();
        }}

        function setView(view) {{
            currentView = view;
            document.querySelectorAll('.header-actions .icon-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('view-' + view).classList.add('active');
            renderBooks();
        }}

        function parseSearch(query) {{
            const terms = {{}};
            const general = [];

            // Match field:value or field:"quoted value"
            const regex = /(\\w+):(?:"([^"]+)"|([^\\s]+))|"([^"]+)"|(\\S+)/g;
            let match;

            while ((match = regex.exec(query)) !== null) {{
                if (match[1]) {{
                    // field:value
                    const field = match[1].toLowerCase();
                    const value = (match[2] || match[3]).toLowerCase();
                    terms[field] = value;
                }} else {{
                    // general term
                    const term = (match[4] || match[5]).toLowerCase();
                    if (term !== 'or' && term !== 'and') {{
                        general.push(term);
                    }}
                }}
            }}

            return {{ terms, general }};
        }}

        function bookMatchesSearch(book, parsed) {{
            // Check field-specific terms
            for (const [field, value] of Object.entries(parsed.terms)) {{
                switch (field) {{
                    case 'title':
                        if (!book.title?.toLowerCase().includes(value)) return false;
                        break;
                    case 'author':
                        if (!book.authors.some(a => a.name.toLowerCase().includes(value))) return false;
                        break;
                    case 'tag':
                    case 'subject':
                        if (!book.subjects.some(s => s.toLowerCase().includes(value))) return false;
                        break;
                    case 'series':
                        if (!book.series?.toLowerCase().includes(value)) return false;
                        break;
                    case 'language':
                    case 'lang':
                        if (book.language?.toLowerCase() !== value) return false;
                        break;
                    case 'format':
                        if (!book.files.some(f => f.format.toLowerCase() === value)) return false;
                        break;
                    case 'rating':
                        const rating = parseFloat(value);
                        if (value.startsWith('>=')) {{
                            if ((book.personal?.rating || 0) < parseFloat(value.slice(2))) return false;
                        }} else if (value.startsWith('>')) {{
                            if ((book.personal?.rating || 0) <= parseFloat(value.slice(1))) return false;
                        }} else {{
                            if ((book.personal?.rating || 0) < rating) return false;
                        }}
                        break;
                    case 'favorite':
                        if (value === 'true' && !book.personal?.favorite) return false;
                        if (value === 'false' && book.personal?.favorite) return false;
                        break;
                    case 'status':
                        if (book.personal?.reading_status !== value) return false;
                        break;
                }}
            }}

            // Check general terms
            if (parsed.general.length > 0) {{
                const searchable = [
                    book.title,
                    book.subtitle,
                    ...book.authors.map(a => a.name),
                    ...book.subjects,
                    ...(book.keywords || []),
                    book.description,
                    book.publisher
                ].filter(Boolean).join(' ').toLowerCase();

                for (const term of parsed.general) {{
                    if (term.startsWith('-')) {{
                        if (searchable.includes(term.slice(1))) return false;
                    }} else {{
                        if (!searchable.includes(term)) return false;
                    }}
                }}
            }}

            return true;
        }}

        function applyFilters() {{
            const searchQuery = document.getElementById('search').value;
            const langFilter = document.getElementById('filter-language').value;
            const formatFilter = document.getElementById('filter-format').value;
            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;

            const parsed = parseSearch(searchQuery);

            filteredBooks = BOOKS.filter(book => {{
                // Category filter
                if (currentFilter === 'favorites' && !book.personal?.favorite) return false;
                if (currentFilter === 'queue' && !book.personal?.queue_position) return false;
                if (currentFilter === 'reading' && book.personal?.reading_status !== 'reading') return false;

                // Subfilter
                if (currentSubfilter) {{
                    if (currentFilter === 'authors' && !book.authors.some(a => a.name === currentSubfilter)) return false;
                    if (currentFilter === 'subjects' && !book.subjects.includes(currentSubfilter)) return false;
                    if (currentFilter === 'series' && book.series !== currentSubfilter) return false;
                }}

                // Search
                if (searchQuery && !bookMatchesSearch(book, parsed)) return false;

                // Language
                if (langFilter && book.language !== langFilter) return false;

                // Format
                if (formatFilter && !book.files.some(f => f.format.toUpperCase() === formatFilter)) return false;

                return true;
            }});

            // Sort
            filteredBooks.sort((a, b) => {{
                let aVal, bVal;
                switch (sortField) {{
                    case 'title':
                        aVal = a.title?.toLowerCase() || '';
                        bVal = b.title?.toLowerCase() || '';
                        break;
                    case 'author':
                        aVal = a.authors[0]?.name.toLowerCase() || '';
                        bVal = b.authors[0]?.name.toLowerCase() || '';
                        break;
                    case 'date_added':
                        aVal = new Date(a.created_at);
                        bVal = new Date(b.created_at);
                        break;
                    case 'publication_date':
                        aVal = a.publication_date || '';
                        bVal = b.publication_date || '';
                        break;
                    case 'rating':
                        aVal = a.personal?.rating || 0;
                        bVal = b.personal?.rating || 0;
                        break;
                    default:
                        return 0;
                }}
                const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
                return sortOrder === 'asc' ? cmp : -cmp;
            }});

            renderBooks();
        }}

        function renderBooks() {{
            const container = document.getElementById('book-container');
            const emptyState = document.getElementById('empty-state');
            const resultsInfo = document.getElementById('results-info');
            const pagination = document.getElementById('pagination');

            if (filteredBooks.length === 0) {{
                container.innerHTML = '';
                emptyState.style.display = 'block';
                pagination.innerHTML = '';
                resultsInfo.textContent = 'No books found';
                return;
            }}

            emptyState.style.display = 'none';

            // Pagination
            const totalPages = Math.ceil(filteredBooks.length / perPage);
            const start = (currentPage - 1) * perPage;
            const pageBooks = filteredBooks.slice(start, start + perPage);

            resultsInfo.textContent = `Showing ${{start + 1}}-${{Math.min(start + perPage, filteredBooks.length)}} of ${{filteredBooks.length}} books`;

            if (currentView === 'grid') {{
                container.innerHTML = `<div class="book-grid">${{pageBooks.map(renderGridCard).join('')}}</div>`;
            }} else if (currentView === 'list') {{
                container.innerHTML = `<div class="book-list">${{pageBooks.map(renderListItem).join('')}}</div>`;
            }} else {{
                container.innerHTML = renderTable(pageBooks);
            }}

            renderPagination(totalPages);
        }}

        function renderGridCard(book) {{
            const coverUrl = book.cover_path ? (BASE_URL ? BASE_URL + '/' + book.cover_path : book.cover_path) : null;
            const author = book.authors.map(a => a.name).join(', ') || 'Unknown';
            const rating = book.personal?.rating ? '★'.repeat(Math.round(book.personal.rating)) : '';

            return `
                <div class="book-card" onclick="showDetails(${{book.id}})">
                    <div class="book-cover">
                        ${{coverUrl ? `<img src="${{coverUrl}}" alt="" loading="lazy" onerror="this.parentElement.innerHTML='<div class=\\'book-cover-placeholder\\'>📖</div>'">` : '<div class="book-cover-placeholder">📖</div>'}}
                    </div>
                    <div class="book-info">
                        <div class="book-title">${{escapeHtml(book.title)}}</div>
                        <div class="book-author">${{escapeHtml(author)}}</div>
                        <div class="book-meta">
                            ${{book.personal?.favorite ? '<span class="book-badge badge-favorite">⭐</span>' : ''}}
                            ${{book.personal?.queue_position ? `<span class="book-badge badge-queue">#${{book.personal.queue_position}}</span>` : ''}}
                            ${{book.files.map(f => `<span class="book-badge badge-format">${{f.format}}</span>`).join('')}}
                        </div>
                        ${{rating ? `<div class="book-rating">${{rating}}</div>` : ''}}
                    </div>
                </div>
            `;
        }}

        function renderListItem(book) {{
            const coverUrl = book.cover_path ? (BASE_URL ? BASE_URL + '/' + book.cover_path : book.cover_path) : null;
            const author = book.authors.map(a => a.name).join(', ') || 'Unknown';

            return `
                <div class="book-list-item" onclick="showDetails(${{book.id}})">
                    <div class="book-list-cover">
                        ${{coverUrl ? `<img src="${{coverUrl}}" alt="" loading="lazy">` : ''}}
                    </div>
                    <div class="book-list-info">
                        <div class="book-list-title">
                            ${{book.personal?.favorite ? '⭐ ' : ''}}${{escapeHtml(book.title)}}
                        </div>
                        <div class="book-list-author">${{escapeHtml(author)}}</div>
                        <div class="book-list-meta">
                            ${{book.publication_date ? `<span>📅 ${{book.publication_date}}</span>` : ''}}
                            ${{book.language ? `<span>🌐 ${{book.language.toUpperCase()}}</span>` : ''}}
                            ${{book.files.map(f => `<span>📄 ${{f.format.toUpperCase()}}</span>`).join('')}}
                            ${{book.personal?.rating ? `<span>⭐ ${{book.personal.rating}}</span>` : ''}}
                        </div>
                    </div>
                </div>
            `;
        }}

        function renderTable(books) {{
            return `
                <table class="book-table">
                    <thead>
                        <tr>
                            <th onclick="sortBy('title')">Title</th>
                            <th onclick="sortBy('author')">Author</th>
                            <th onclick="sortBy('publication_date')">Year</th>
                            <th>Format</th>
                            <th onclick="sortBy('rating')">Rating</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${{books.map(book => `
                            <tr>
                                <td><span class="table-title" onclick="showDetails(${{book.id}})">${{book.personal?.favorite ? '⭐ ' : ''}}${{escapeHtml(book.title)}}</span></td>
                                <td>${{escapeHtml(book.authors.map(a => a.name).join(', ') || '-')}}</td>
                                <td>${{book.publication_date?.substring(0, 4) || '-'}}</td>
                                <td>${{book.files.map(f => f.format.toUpperCase()).join(', ')}}</td>
                                <td>${{book.personal?.rating ? '★'.repeat(Math.round(book.personal.rating)) : '-'}}</td>
                            </tr>
                        `).join('')}}
                    </tbody>
                </table>
            `;
        }}

        function renderPagination(totalPages) {{
            const pagination = document.getElementById('pagination');
            if (totalPages <= 1) {{
                pagination.innerHTML = '';
                return;
            }}

            let html = `<button class="page-btn" onclick="goToPage(${{currentPage - 1}})" ${{currentPage === 1 ? 'disabled' : ''}}>← Prev</button>`;

            const start = Math.max(1, currentPage - 2);
            const end = Math.min(totalPages, currentPage + 2);

            if (start > 1) html += `<button class="page-btn" onclick="goToPage(1)">1</button>`;
            if (start > 2) html += `<span style="color:var(--text-muted)">...</span>`;

            for (let i = start; i <= end; i++) {{
                html += `<button class="page-btn ${{i === currentPage ? 'active' : ''}}" onclick="goToPage(${{i}})">${{i}}</button>`;
            }}

            if (end < totalPages - 1) html += `<span style="color:var(--text-muted)">...</span>`;
            if (end < totalPages) html += `<button class="page-btn" onclick="goToPage(${{totalPages}})">${{totalPages}}</button>`;

            html += `<button class="page-btn" onclick="goToPage(${{currentPage + 1}})" ${{currentPage === totalPages ? 'disabled' : ''}}>Next →</button>`;

            pagination.innerHTML = html;
        }}

        function goToPage(page) {{
            const totalPages = Math.ceil(filteredBooks.length / perPage);
            if (page < 1 || page > totalPages) return;
            currentPage = page;
            renderBooks();
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }}

        function showDetails(id) {{
            const book = BOOKS.find(b => b.id === id);
            if (!book) return;

            document.getElementById('modal-title').textContent = book.title;

            const coverUrl = book.cover_path ? (BASE_URL ? BASE_URL + '/' + book.cover_path : book.cover_path) : null;

            let html = '';

            if (coverUrl) {{
                html += `<div class="modal-cover"><img src="${{coverUrl}}" alt="" onerror="this.style.display='none'"></div>`;
            }}

            if (book.subtitle) {{
                html += `<div class="detail-section"><div class="detail-label">Subtitle</div><div class="detail-value">${{escapeHtml(book.subtitle)}}</div></div>`;
            }}

            if (book.authors.length) {{
                html += `<div class="detail-section"><div class="detail-label">Authors</div><div class="detail-value">${{book.authors.map(a => escapeHtml(a.name)).join(', ')}}</div></div>`;
            }}

            if (book.series) {{
                html += `<div class="detail-section"><div class="detail-label">Series</div><div class="detail-value">${{escapeHtml(book.series)}} #${{book.series_index || '?'}}</div></div>`;
            }}

            if (book.description) {{
                html += `<div class="detail-section"><div class="detail-label">Description</div><div class="detail-value">${{book.description}}</div></div>`;
            }}

            const meta = [];
            if (book.publisher) meta.push(`Publisher: ${{escapeHtml(book.publisher)}}`);
            if (book.publication_date) meta.push(`Published: ${{book.publication_date}}`);
            if (book.language) meta.push(`Language: ${{book.language.toUpperCase()}}`);
            if (book.page_count) meta.push(`Pages: ${{book.page_count}}`);
            if (meta.length) {{
                html += `<div class="detail-section"><div class="detail-label">Details</div><div class="detail-value">${{meta.join(' • ')}}</div></div>`;
            }}

            if (book.subjects.length) {{
                html += `<div class="detail-section"><div class="detail-label">Subjects</div><div class="detail-tags">${{book.subjects.map(s => `<span class="tag">${{escapeHtml(s)}}</span>`).join('')}}</div></div>`;
            }}

            if (book.files.length) {{
                html += `<div class="detail-section"><div class="detail-label">Files</div><ul class="file-list">${{book.files.map(f => {{
                    const url = BASE_URL ? BASE_URL + '/' + f.path : f.path;
                    return `<li class="file-item"><a href="${{url}}" class="file-link" target="_blank">${{f.format.toUpperCase()}}</a><span class="file-size">${{formatBytes(f.size_bytes)}}</span></li>`;
                }}).join('')}}</ul></div>`;
            }}

            if (book.identifiers.length) {{
                html += `<div class="detail-section"><div class="detail-label">Identifiers</div><div class="detail-value">${{book.identifiers.map(i => `${{i.scheme.toUpperCase()}}: ${{i.value}}`).join('<br>')}}</div></div>`;
            }}

            document.getElementById('modal-body').innerHTML = html;
            document.getElementById('modal').classList.add('active');
        }}

        function closeModal() {{
            document.getElementById('modal').classList.remove('active');
        }}

        function setupKeyboardShortcuts() {{
            document.addEventListener('keydown', e => {{
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {{
                    if (e.key === 'Escape') {{
                        e.target.blur();
                    }}
                    return;
                }}

                if (e.key === '/') {{
                    e.preventDefault();
                    document.getElementById('search').focus();
                }} else if (e.key === 'Escape') {{
                    closeModal();
                }} else if (e.key === 'j') {{
                    goToPage(currentPage + 1);
                }} else if (e.key === 'k') {{
                    goToPage(currentPage - 1);
                }} else if (e.key === 'g') {{
                    setView('grid');
                }} else if (e.key === 'l') {{
                    setView('list');
                }} else if (e.key === 't') {{
                    setView('table');
                }}
            }});

            document.getElementById('search').addEventListener('input', () => {{
                currentPage = 1;
                applyFilters();
            }});
        }}

        function escapeHtml(text) {{
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function formatBytes(bytes) {{
            if (!bytes) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
        }}
    </script>
</body>
</html>'''
