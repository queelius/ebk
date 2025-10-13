"""
Web server for ebk library management.

Provides a REST API and web interface for managing ebook libraries.
"""

from pathlib import Path
from typing import Optional, List
import tempfile
import shutil

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .library_db import Library
from .extract_metadata import extract_metadata


# Pydantic models for API
class BookResponse(BaseModel):
    id: int
    title: str
    subtitle: Optional[str]
    authors: List[str]
    language: Optional[str]
    publisher: Optional[str]
    publication_date: Optional[str]
    series: Optional[str]
    series_index: Optional[float]
    description: Optional[str]
    subjects: List[str]
    files: List[dict]
    rating: Optional[float]
    favorite: bool
    reading_status: str
    tags: List[str]
    cover_path: Optional[str]


class BookUpdateRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    language: Optional[str] = None
    publisher: Optional[str] = None
    publication_date: Optional[str] = None
    description: Optional[str] = None
    rating: Optional[float] = None
    favorite: Optional[bool] = None
    reading_status: Optional[str] = None
    tags: Optional[List[str]] = None


class LibraryStats(BaseModel):
    total_books: int
    total_authors: int
    total_subjects: int
    total_files: int
    total_size_mb: float
    languages: List[str]
    formats: List[str]


# Global library instance
_library: Optional[Library] = None
_library_path: Optional[Path] = None


def get_library() -> Library:
    """Get the current library instance."""
    if _library is None:
        raise HTTPException(status_code=500, detail="Library not initialized")
    return _library


def init_library(library_path: Path):
    """Initialize the library."""
    global _library, _library_path
    _library_path = library_path
    _library = Library.open(library_path)


def create_app(library_path: Path) -> FastAPI:
    """Create FastAPI application with initialized library."""
    # Initialize library
    init_library(library_path)

    # Return the pre-configured app with all routes
    return app


# Create FastAPI app
app = FastAPI(
    title="ebk Library Manager",
    description="Web interface for managing ebook libraries",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web interface."""
    return get_web_interface()


@app.get("/api/books", response_model=List[BookResponse])
async def list_books(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    language: Optional[str] = None,
    favorite: Optional[bool] = None,
    format_filter: Optional[str] = None,
    sort_by: Optional[str] = Query(None, alias="sort"),
    sort_order: Optional[str] = Query("asc", alias="order"),
    min_rating: Optional[float] = Query(None, alias="rating")
):
    """List books with filtering, sorting, and pagination."""
    lib = get_library()

    query = lib.query()

    # Apply filters
    if author:
        query = query.filter_by_author(author)
    if subject:
        query = query.filter_by_subject(subject)
    if language:
        query = query.filter_by_language(language)
    if favorite is not None:
        query = query.filter_by_favorite(favorite)
    if format_filter:
        query = query.filter_by_format(format_filter)

    # Apply sorting before pagination
    if sort_by:
        desc = (sort_order == "desc")
        query = query.order_by(sort_by, desc=desc)
    else:
        # Default sort by title
        query = query.order_by("title", desc=False)

    # Apply pagination after sorting
    query = query.limit(limit).offset(offset)
    books = query.all()

    # Search if provided (in-memory after fetching)
    if search:
        search_lower = search.lower()
        books = [
            b for b in books
            if search_lower in b.title.lower() or
               any(search_lower in a.name.lower() for a in b.authors) or
               (b.description and search_lower in b.description.lower())
        ]

    # Apply rating filter (in-memory for now)
    if min_rating is not None:
        books = [
            b for b in books
            if b.personal and b.personal.rating and b.personal.rating >= min_rating
        ]

    # Convert to response format
    return [_book_to_response(book) for book in books]


@app.get("/api/books/{book_id}", response_model=BookResponse)
async def get_book(book_id: int):
    """Get a specific book by ID."""
    lib = get_library()
    book = lib.get_book(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    return _book_to_response(book)


@app.patch("/api/books/{book_id}")
async def update_book(book_id: int, update: BookUpdateRequest):
    """Update book metadata."""
    lib = get_library()
    book = lib.get_book(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Update fields
    if update.title is not None:
        book.title = update.title
    if update.subtitle is not None:
        book.subtitle = update.subtitle
    if update.language is not None:
        book.language = update.language
    if update.publisher is not None:
        book.publisher = update.publisher
    if update.publication_date is not None:
        book.publication_date = update.publication_date
    if update.description is not None:
        book.description = update.description

    # Update personal metadata
    # Handle reading status and rating together to avoid multiple calls
    if update.reading_status is not None or update.rating is not None:
        current_status = book.personal.reading_status if book.personal else 'unread'
        new_status = update.reading_status if update.reading_status is not None else current_status
        lib.update_reading_status(book_id, status=new_status, rating=update.rating)

    if update.favorite is not None:
        lib.set_favorite(book_id, update.favorite)

    if update.tags is not None:
        # Clear existing tags and add new ones
        if book.personal and book.personal.personal_tags:
            lib.remove_tags(book_id, book.personal.personal_tags)
        if update.tags:
            lib.add_tags(book_id, update.tags)

    lib.session.commit()

    # Refresh and return
    lib.session.refresh(book)
    return _book_to_response(book)


@app.delete("/api/books/{book_id}")
async def delete_book(book_id: int, delete_files: bool = Query(False)):
    """Delete a book from the library."""
    lib = get_library()
    book = lib.get_book(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Delete files if requested
    if delete_files and _library_path:
        for file in book.files:
            file_path = _library_path / file.path
            if file_path.exists():
                file_path.unlink()

    # Delete from database
    lib.session.delete(book)
    lib.session.commit()

    return {"message": "Book deleted successfully"}


@app.post("/api/books/import")
async def import_book(
    file: UploadFile = File(...),
    extract_text: bool = Form(True),
    extract_cover: bool = Form(True)
):
    """Import a new book file."""
    lib = get_library()

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        # Extract metadata
        metadata = extract_metadata(str(tmp_path))

        # Import to library
        book = lib.add_book(
            tmp_path,
            metadata=metadata,
            extract_text=extract_text,
            extract_cover=extract_cover
        )

        if not book:
            raise HTTPException(status_code=400, detail="Failed to import book")

        return _book_to_response(book)

    finally:
        # Clean up temp file
        tmp_path.unlink()


@app.get("/api/books/{book_id}/files/{file_format}")
async def download_file(book_id: int, file_format: str):
    """Download a book file."""
    lib = get_library()
    book = lib.get_book(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Find file with matching format
    book_file = next((f for f in book.files if f.format.lower() == file_format.lower()), None)

    if not book_file or not _library_path:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = _library_path / book_file.path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=f"{book.title}.{file_format}"
    )


@app.get("/api/books/{book_id}/cover")
async def get_cover(book_id: int):
    """Get the cover image for a book."""
    lib = get_library()
    book = lib.get_book(book_id)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Find primary cover
    if not book.covers:
        raise HTTPException(status_code=404, detail="No cover available")

    primary_cover = next((c for c in book.covers if c.is_primary), book.covers[0])

    if not _library_path:
        raise HTTPException(status_code=500, detail="Library path not initialized")

    cover_path = _library_path / primary_cover.path

    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found on disk")

    return FileResponse(
        cover_path,
        media_type="image/png",
        filename=f"cover_{book_id}.png"
    )


@app.get("/api/stats", response_model=LibraryStats)
async def get_stats():
    """Get library statistics."""
    lib = get_library()
    stats = lib.stats()

    # Calculate total size from all files
    from .db.models import File
    from sqlalchemy import func
    total_size = lib.session.query(func.sum(File.size_bytes)).scalar() or 0

    # Convert language/format dicts to lists
    languages = list(stats['languages'].keys()) if isinstance(stats['languages'], dict) else stats['languages']
    formats = list(stats['formats'].keys()) if isinstance(stats['formats'], dict) else stats['formats']

    return LibraryStats(
        total_books=stats['total_books'],
        total_authors=stats['total_authors'],
        total_subjects=stats['total_subjects'],
        total_files=stats['total_files'],
        total_size_mb=total_size / (1024 ** 2),
        languages=languages,
        formats=formats
    )


@app.get("/api/search")
async def search_books(q: str, limit: int = Query(50, ge=1, le=1000)):
    """Full-text search across books."""
    lib = get_library()
    results = lib.search(q, limit=limit)
    return [_book_to_response(book) for book in results]


def _book_to_response(book) -> dict:
    """Convert Book ORM object to API response."""
    # Get primary cover if available
    cover_path = None
    if book.covers:
        primary_cover = next((c for c in book.covers if c.is_primary), book.covers[0])
        cover_path = primary_cover.path

    return {
        "id": book.id,
        "title": book.title,
        "subtitle": book.subtitle,
        "authors": [a.name for a in book.authors],
        "language": book.language,
        "publisher": book.publisher,
        "publication_date": book.publication_date,
        "series": book.series,
        "series_index": book.series_index,
        "description": book.description,
        "subjects": [s.name for s in book.subjects],
        "files": [
            {
                "format": f.format,
                "size_bytes": f.size_bytes,
                "path": f.path
            }
            for f in book.files
        ],
        "rating": book.personal.rating if book.personal else None,
        "favorite": book.personal.favorite if book.personal else False,
        "reading_status": book.personal.reading_status if book.personal else "unread",
        "tags": book.personal.personal_tags if (book.personal and book.personal.personal_tags) else [],
        "cover_path": cover_path
    }


def get_web_interface() -> str:
    """Generate the web interface HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ebk Library Manager</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
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
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--background);
            color: var(--text);
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: var(--surface);
            border-bottom: 2px solid var(--border);
            padding: 20px 0;
            margin-bottom: 30px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        h1 {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 10px;
        }

        .toolbar {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
            background: var(--surface);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .search-bar {
            flex: 1;
            min-width: 300px;
            padding: 10px 15px;
            border: 2px solid var(--border);
            border-radius: 6px;
            font-size: 1rem;
        }

        .search-bar:focus {
            outline: none;
            border-color: var(--primary);
        }

        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--primary);
            color: white;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
        }

        .btn-secondary {
            background: var(--secondary);
            color: white;
        }

        .btn-danger {
            background: var(--danger);
            color: white;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        .stat-label {
            color: var(--text-light);
            font-size: 0.875rem;
            margin-bottom: 5px;
        }

        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--primary);
        }

        .book-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }

        .book-card {
            background: var(--surface);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }

        .book-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.15);
        }

        .book-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text);
        }

        .book-authors {
            color: var(--text-light);
            font-size: 0.9rem;
            margin-bottom: 8px;
        }

        .book-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 12px;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-format {
            background: #f3f4f6;
            color: var(--secondary);
        }

        .badge-language {
            background: #fef3c7;
            color: #92400e;
        }

        .favorite-star {
            color: var(--warning);
            font-size: 1.2rem;
        }

        .rating {
            color: var(--warning);
            font-size: 0.9rem;
        }

        .modal {
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
        }

        .modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .modal-content {
            background: var(--surface);
            border-radius: 12px;
            max-width: 800px;
            width: 100%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1);
        }

        .modal-header {
            padding: 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .modal-title {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .close-btn {
            background: none;
            border: none;
            font-size: 2rem;
            color: var(--text-light);
            cursor: pointer;
            padding: 0;
            width: 30px;
            height: 30px;
            line-height: 1;
        }

        .modal-body {
            padding: 24px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text);
        }

        .form-control {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 1rem;
        }

        textarea.form-control {
            min-height: 100px;
            resize: vertical;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-light);
        }

        .spinner {
            border: 3px solid var(--border);
            border-top: 3px solid var(--primary);
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .error {
            background: #fee2e2;
            color: #991b1b;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }

        .success {
            background: #d1fae5;
            color: #065f46;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>📚 ebk Library Manager</h1>
            <div id="stats-container" class="stats"></div>
        </div>
    </header>

    <div class="container">
        <div class="toolbar">
            <input
                type="text"
                id="search-input"
                class="search-bar"
                placeholder="Search books by title, author, or description..."
            >
            <button class="btn btn-primary" onclick="showImportModal()">
                ➕ Import Book
            </button>
            <button class="btn btn-secondary" onclick="refreshBooks()">
                🔄 Refresh
            </button>
        </div>

        <!-- Filters and Sorting -->
        <div style="background: var(--surface); padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 10px;">
                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Sort By</label>
                    <select id="sort-field" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="title">Title</option>
                        <option value="created_at">Date Added</option>
                        <option value="publication_date">Publication Date</option>
                        <option value="rating">Rating</option>
                    </select>
                </div>

                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Order</label>
                    <select id="sort-order" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="asc">Ascending</option>
                        <option value="desc">Descending</option>
                    </select>
                </div>

                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Language</label>
                    <select id="filter-language" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="">All Languages</option>
                    </select>
                </div>

                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Format</label>
                    <select id="filter-format" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="">All Formats</option>
                    </select>
                </div>

                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Favorites</label>
                    <select id="filter-favorite" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="">All Books</option>
                        <option value="true">Favorites Only</option>
                        <option value="false">Non-Favorites</option>
                    </select>
                </div>

                <div style="flex: 1; min-width: 150px;">
                    <label style="display: block; font-size: 0.875rem; font-weight: 600; margin-bottom: 5px; color: var(--text-light);">Min Rating</label>
                    <select id="filter-rating" class="form-control" onchange="applyFiltersAndSort()">
                        <option value="">Any Rating</option>
                        <option value="1">1+ Stars</option>
                        <option value="2">2+ Stars</option>
                        <option value="3">3+ Stars</option>
                        <option value="4">4+ Stars</option>
                        <option value="5">5 Stars</option>
                    </select>
                </div>
            </div>

            <div style="display: flex; gap: 10px; align-items: center;">
                <button class="btn btn-secondary" onclick="clearFilters()" style="font-size: 0.875rem; padding: 8px 16px;">
                    Clear Filters
                </button>
                <span id="filter-count" style="color: var(--text-light); font-size: 0.875rem;"></span>
            </div>
        </div>

        <div id="message-container"></div>

        <div id="loading" class="loading" style="display: none;">
            <div class="spinner"></div>
            <p>Loading books...</p>
        </div>

        <div id="book-grid" class="book-grid"></div>

        <div id="pagination" style="display: flex; justify-content: center; align-items: center; gap: 15px; margin-top: 30px; padding: 20px;">
            <button class="btn btn-secondary" onclick="previousPage()" id="prev-btn">
                ← Previous
            </button>
            <span id="page-info" style="color: var(--text-light);">Page 1</span>
            <button class="btn btn-secondary" onclick="nextPage()" id="next-btn">
                Next →
            </button>
        </div>
    </div>

    <!-- Edit Book Modal -->
    <div id="edit-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Edit Book</h2>
                <button class="close-btn" onclick="closeModal('edit-modal')">&times;</button>
            </div>
            <div class="modal-body">
                <form id="edit-form" onsubmit="saveBook(event)">
                    <input type="hidden" id="edit-book-id">

                    <div class="form-group">
                        <label class="form-label">Title</label>
                        <input type="text" id="edit-title" class="form-control">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Subtitle</label>
                        <input type="text" id="edit-subtitle" class="form-control">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Language</label>
                        <input type="text" id="edit-language" class="form-control">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Publisher</label>
                        <input type="text" id="edit-publisher" class="form-control">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Publication Date</label>
                        <input type="text" id="edit-publication-date" class="form-control" placeholder="YYYY-MM-DD">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Description</label>
                        <textarea id="edit-description" class="form-control"></textarea>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Rating (1-5)</label>
                        <input type="number" id="edit-rating" class="form-control" min="1" max="5" step="0.5">
                    </div>

                    <div class="form-group">
                        <label class="form-label">Reading Status</label>
                        <select id="edit-status" class="form-control">
                            <option value="unread">Unread</option>
                            <option value="reading">Reading</option>
                            <option value="completed">Completed</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <input type="checkbox" id="edit-favorite">
                            Favorite
                        </label>
                    </div>

                    <div class="form-group">
                        <label class="form-label">Tags (comma-separated)</label>
                        <input type="text" id="edit-tags" class="form-control">
                    </div>

                    <div style="display: flex; gap: 10px;">
                        <button type="submit" class="btn btn-primary">Save Changes</button>
                        <button type="button" class="btn btn-danger" onclick="deleteBook()">Delete Book</button>
                        <button type="button" class="btn btn-secondary" onclick="closeModal('edit-modal')">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Import Book Modal -->
    <div id="import-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Import Book</h2>
                <button class="close-btn" onclick="closeModal('import-modal')">&times;</button>
            </div>
            <div class="modal-body">
                <form id="import-form" onsubmit="importBook(event)">
                    <div class="form-group">
                        <label class="form-label">Select File (PDF, EPUB, MOBI, etc.)</label>
                        <input type="file" id="import-file" class="form-control" accept=".pdf,.epub,.mobi,.azw,.azw3,.txt" required>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="import-extract-text" checked>
                            Extract full text for search
                        </label>
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="import-extract-cover" checked>
                            Extract cover image
                        </label>
                    </div>

                    <div style="display: flex; gap: 10px;">
                        <button type="submit" class="btn btn-primary">Import</button>
                        <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- View Book Details Modal -->
    <div id="details-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="details-title"></h2>
                <button class="close-btn" onclick="closeModal('details-modal')">&times;</button>
            </div>
            <div class="modal-body" id="details-body"></div>
        </div>
    </div>

    <script>
        let books = [];
        let currentBookId = null;
        let currentPage = 1;
        let booksPerPage = 100;
        let totalBooks = 0;
        let isSearching = false;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            loadStats();

            // Restore state from URL
            restoreStateFromURL();
            loadBooks();

            // Search debouncing
            let searchTimeout;
            document.getElementById('search-input').addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    if (e.target.value.length >= 3) {
                        isSearching = true;
                        currentPage = 1;
                        updateURL();
                        searchBooks(e.target.value);
                    } else if (e.target.value.length === 0) {
                        isSearching = false;
                        currentPage = 1;
                        updateURL();
                        loadBooks();
                    }
                }, 300);
            });

            // Handle browser back/forward
            window.addEventListener('popstate', () => {
                restoreStateFromURL();
                if (isSearching) {
                    searchBooks(document.getElementById('search-input').value);
                } else {
                    loadBooks();
                }
            });
        });

        function updateURL() {
            const params = new URLSearchParams();

            // Page
            if (currentPage > 1) params.set('page', currentPage);

            // Search
            const searchQuery = document.getElementById('search-input').value;
            if (searchQuery) params.set('q', searchQuery);

            // Filters
            const language = document.getElementById('filter-language').value;
            const format = document.getElementById('filter-format').value;
            const favorite = document.getElementById('filter-favorite').value;
            const minRating = document.getElementById('filter-rating').value;

            if (language) params.set('language', language);
            if (format) params.set('format', format);
            if (favorite) params.set('favorite', favorite);
            if (minRating) params.set('rating', minRating);

            // Sorting
            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;

            if (sortField !== 'title') params.set('sort', sortField);
            if (sortOrder !== 'asc') params.set('order', sortOrder);

            // Update URL without reloading
            const newURL = params.toString() ? `?${params.toString()}` : window.location.pathname;
            window.history.pushState({}, '', newURL);
        }

        function restoreStateFromURL() {
            const params = new URLSearchParams(window.location.search);

            // Restore page
            currentPage = parseInt(params.get('page')) || 1;

            // Restore search
            const searchQuery = params.get('q') || '';
            document.getElementById('search-input').value = searchQuery;
            isSearching = searchQuery.length >= 3;

            // Restore filters
            document.getElementById('filter-language').value = params.get('language') || '';
            document.getElementById('filter-format').value = params.get('format') || '';
            document.getElementById('filter-favorite').value = params.get('favorite') || '';
            document.getElementById('filter-rating').value = params.get('rating') || '';

            // Restore sorting
            document.getElementById('sort-field').value = params.get('sort') || 'title';
            document.getElementById('sort-order').value = params.get('order') || 'asc';
        }

        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();

                // Populate filter dropdowns
                const languageSelect = document.getElementById('filter-language');
                const formatSelect = document.getElementById('filter-format');

                stats.languages.forEach(lang => {
                    const option = document.createElement('option');
                    option.value = lang;
                    option.textContent = lang.toUpperCase();
                    languageSelect.appendChild(option);
                });

                stats.formats.forEach(fmt => {
                    const option = document.createElement('option');
                    option.value = fmt;
                    option.textContent = fmt.toUpperCase();
                    formatSelect.appendChild(option);
                });

                document.getElementById('stats-container').innerHTML = `
                    <div class="stat-card">
                        <div class="stat-label">Total Books</div>
                        <div class="stat-value">${stats.total_books}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Authors</div>
                        <div class="stat-value">${stats.total_authors}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Files</div>
                        <div class="stat-value">${stats.total_files}</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-label">Storage</div>
                        <div class="stat-value">${stats.total_size_mb.toFixed(1)} MB</div>
                    </div>
                `;
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        function buildQueryParams() {
            const params = new URLSearchParams();
            const offset = (currentPage - 1) * booksPerPage;

            params.append('limit', booksPerPage);
            params.append('offset', offset);

            // Add filters
            const language = document.getElementById('filter-language').value;
            const format = document.getElementById('filter-format').value;
            const favorite = document.getElementById('filter-favorite').value;
            const minRating = document.getElementById('filter-rating').value;

            if (language) params.append('language', language);
            if (format) params.append('format_filter', format);
            if (favorite) params.append('favorite', favorite);
            if (minRating) params.append('rating', minRating);

            // Add sorting
            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;

            if (sortField) params.append('sort', sortField);
            if (sortOrder) params.append('order', sortOrder);

            return params.toString();
        }

        async function loadBooks() {
            const loading = document.getElementById('loading');
            const grid = document.getElementById('book-grid');

            loading.style.display = 'block';
            grid.innerHTML = '';

            try {
                const queryParams = buildQueryParams();
                const response = await fetch(`/api/books?${queryParams}`);
                books = await response.json();

                // Get total count from stats (approximate for filtered results)
                const statsResponse = await fetch('/api/stats');
                const stats = await statsResponse.json();
                totalBooks = stats.total_books;

                renderBooks(books);
                updatePagination();
                updateFilterCount();
            } catch (error) {
                showError('Failed to load books: ' + error.message);
            } finally {
                loading.style.display = 'none';
            }
        }

        async function searchBooks(query) {
            const loading = document.getElementById('loading');
            const grid = document.getElementById('book-grid');

            loading.style.display = 'block';
            grid.innerHTML = '';

            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                books = await response.json();
                renderBooks(books);
            } catch (error) {
                showError('Search failed: ' + error.message);
            } finally {
                loading.style.display = 'none';
            }
        }

        function renderBooks(books) {
            const grid = document.getElementById('book-grid');

            if (books.length === 0) {
                grid.innerHTML = '<p class="loading">No books found</p>';
                return;
            }

            grid.innerHTML = books.map(book => {
                // Find preferred format (pdf > epub > mobi > others)
                const preferredFormat = book.files.find(f => f.format.toLowerCase() === 'pdf') ||
                                       book.files.find(f => f.format.toLowerCase() === 'epub') ||
                                       book.files.find(f => f.format.toLowerCase() === 'mobi') ||
                                       book.files[0];

                return `
                <div class="book-card">
                    ${book.cover_path ? `
                        <div style="text-align: center; margin-bottom: 10px; cursor: pointer;"
                             onclick="openBookFile(${book.id}, '${preferredFormat?.format || ''}'); event.stopPropagation();"
                             title="Click to open ${preferredFormat?.format.toUpperCase() || 'book'}">
                            <img src="/api/books/${book.id}/cover" alt="Cover" style="max-width: 100%; max-height: 200px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        </div>
                    ` : ''}
                    <div class="book-title" onclick="showBookDetails(${book.id})" style="cursor: pointer;">
                        ${escapeHtml(book.title)}
                        ${book.favorite ? '<span class="favorite-star">⭐</span>' : ''}
                    </div>
                    <div class="book-authors" onclick="showBookDetails(${book.id})" style="cursor: pointer;">
                        ${book.authors.join(', ') || 'Unknown Author'}
                    </div>
                    ${book.publication_date ? `<div style="color: var(--text-light); font-size: 0.85rem; margin-top: 4px;" onclick="showBookDetails(${book.id})">📅 ${book.publication_date}</div>` : ''}
                    ${book.rating ? `<div class="rating" onclick="showBookDetails(${book.id})">${'★'.repeat(Math.round(book.rating))} ${book.rating}</div>` : ''}
                    <div class="book-meta">
                        ${book.files.map(f => `<span class="badge badge-format" style="cursor: pointer;" onclick="openBookFile(${book.id}, '${f.format}'); event.stopPropagation();" title="Click to open ${f.format.toUpperCase()}">${f.format.toUpperCase()}</span>`).join('')}
                        ${book.language ? `<span class="badge badge-language" onclick="showBookDetails(${book.id})">${book.language.toUpperCase()}</span>` : ''}
                    </div>
                </div>
            `;
            }).join('');
        }

        function openBookFile(bookId, format) {
            if (!format) {
                showError('No file format available');
                return;
            }
            // Open in new tab
            window.open(`/api/books/${bookId}/files/${format.toLowerCase()}`, '_blank');
        }

        async function showBookDetails(bookId) {
            try {
                const response = await fetch(`/api/books/${bookId}`);
                const book = await response.json();

                document.getElementById('details-title').textContent = book.title;

                let html = '';

                // Cover image
                if (book.cover_path) {
                    html += `
                        <div style="text-align: center; margin-bottom: 20px;">
                            <img src="/api/books/${book.id}/cover" alt="Cover"
                                 style="max-width: 300px; max-height: 400px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.2);">
                        </div>
                    `;
                }

                // Available formats with clickable links
                if (book.files && book.files.length > 0) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Available Formats</div>
                            <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px;">
                                ${book.files.map(f => `
                                    <a href="/api/books/${book.id}/files/${f.format.toLowerCase()}"
                                       target="_blank"
                                       class="btn btn-primary"
                                       style="text-decoration: none; display: inline-flex; align-items: center; gap: 8px;">
                                        <span>📄</span>
                                        <span>${f.format.toUpperCase()}</span>
                                        <span style="font-size: 0.875rem; opacity: 0.8;">(${formatBytes(f.size_bytes)})</span>
                                    </a>
                                `).join('')}
                            </div>
                        </div>
                    `;
                }

                // Authors
                if (book.authors && book.authors.length > 0) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Authors</div>
                            <div class="detail-value">${book.authors.join(', ')}</div>
                        </div>
                    `;
                }

                // Subtitle
                if (book.subtitle) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Subtitle</div>
                            <div class="detail-value">${escapeHtml(book.subtitle)}</div>
                        </div>
                    `;
                }

                // Description
                if (book.description) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Description</div>
                            <div class="detail-value">${book.description}</div>
                        </div>
                    `;
                }

                // Metadata
                const metadata = [];
                if (book.publisher) metadata.push(`Publisher: ${book.publisher}`);
                if (book.publication_date) metadata.push(`Published: ${book.publication_date}`);
                if (book.language) metadata.push(`Language: ${book.language.toUpperCase()}`);
                if (book.rating) metadata.push(`Rating: ${'★'.repeat(Math.round(book.rating))} (${book.rating}/5)`);
                if (book.reading_status) metadata.push(`Status: ${book.reading_status}`);

                if (metadata.length > 0) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Metadata</div>
                            <div class="detail-value">${metadata.join(' • ')}</div>
                        </div>
                    `;
                }

                // Subjects/Tags
                if (book.subjects && book.subjects.length > 0) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Subjects</div>
                            <div class="detail-value">${book.subjects.join(', ')}</div>
                        </div>
                    `;
                }

                // Personal tags
                if (book.tags && book.tags.length > 0) {
                    html += `
                        <div class="detail-section">
                            <div class="detail-label">Personal Tags</div>
                            <div class="detail-value">${book.tags.join(', ')}</div>
                        </div>
                    `;
                }

                // Edit button
                html += `
                    <div style="margin-top: 20px;">
                        <button class="btn btn-primary" onclick="closeModal('details-modal'); editBook(${book.id});">
                            ✏️ Edit Metadata
                        </button>
                    </div>
                `;

                document.getElementById('details-body').innerHTML = html;
                document.getElementById('details-modal').classList.add('active');
            } catch (error) {
                showError('Failed to load book details: ' + error.message);
            }
        }

        async function editBook(bookId) {
            currentBookId = bookId;

            try {
                const response = await fetch(`/api/books/${bookId}`);
                const book = await response.json();

                document.getElementById('edit-book-id').value = book.id;
                document.getElementById('edit-title').value = book.title || '';
                document.getElementById('edit-subtitle').value = book.subtitle || '';
                document.getElementById('edit-language').value = book.language || '';
                document.getElementById('edit-publisher').value = book.publisher || '';
                document.getElementById('edit-publication-date').value = book.publication_date || '';
                document.getElementById('edit-description').value = book.description || '';
                document.getElementById('edit-rating').value = book.rating || '';
                document.getElementById('edit-status').value = book.reading_status || 'unread';
                document.getElementById('edit-favorite').checked = book.favorite || false;
                document.getElementById('edit-tags').value = (book.tags || []).join(', ');

                document.getElementById('edit-modal').classList.add('active');
            } catch (error) {
                showError('Failed to load book: ' + error.message);
            }
        }

        async function saveBook(event) {
            event.preventDefault();

            const bookId = document.getElementById('edit-book-id').value;
            const tags = document.getElementById('edit-tags').value
                .split(',')
                .map(t => t.trim())
                .filter(t => t);

            const update = {
                title: document.getElementById('edit-title').value,
                subtitle: document.getElementById('edit-subtitle').value,
                language: document.getElementById('edit-language').value,
                publisher: document.getElementById('edit-publisher').value,
                publication_date: document.getElementById('edit-publication-date').value,
                description: document.getElementById('edit-description').value,
                rating: parseFloat(document.getElementById('edit-rating').value) || null,
                reading_status: document.getElementById('edit-status').value,
                favorite: document.getElementById('edit-favorite').checked,
                tags: tags
            };

            try {
                const response = await fetch(`/api/books/${bookId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(update)
                });

                if (!response.ok) throw new Error('Failed to update book');

                closeModal('edit-modal');
                showSuccess('Book updated successfully');
                refreshBooks();
            } catch (error) {
                showError('Failed to save changes: ' + error.message);
            }
        }

        async function deleteBook() {
            if (!confirm('Are you sure you want to delete this book?')) {
                return;
            }

            const bookId = currentBookId;
            const deleteFiles = confirm('Also delete files from disk?');

            try {
                const response = await fetch(`/api/books/${bookId}?delete_files=${deleteFiles}`, {
                    method: 'DELETE'
                });

                if (!response.ok) throw new Error('Failed to delete book');

                closeModal('edit-modal');
                showSuccess('Book deleted successfully');
                refreshBooks();
            } catch (error) {
                showError('Failed to delete book: ' + error.message);
            }
        }

        function showImportModal() {
            document.getElementById('import-modal').classList.add('active');
        }

        async function importBook(event) {
            event.preventDefault();

            const fileInput = document.getElementById('import-file');
            const file = fileInput.files[0];

            if (!file) {
                showError('Please select a file');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('extract_text', document.getElementById('import-extract-text').checked);
            formData.append('extract_cover', document.getElementById('import-extract-cover').checked);

            try {
                const response = await fetch('/api/books/import', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) throw new Error('Import failed');

                closeModal('import-modal');
                showSuccess('Book imported successfully');
                document.getElementById('import-form').reset();
                refreshBooks();
                loadStats();
            } catch (error) {
                showError('Import failed: ' + error.message);
            }
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }

        function refreshBooks() {
            loadBooks();
            loadStats();
        }

        function showError(message) {
            const container = document.getElementById('message-container');
            container.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
            setTimeout(() => container.innerHTML = '', 5000);
        }

        function showSuccess(message) {
            const container = document.getElementById('message-container');
            container.innerHTML = `<div class="success">${escapeHtml(message)}</div>`;
            setTimeout(() => container.innerHTML = '', 3000);
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatBytes(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        }

        function updatePagination() {
            const totalPages = Math.ceil(totalBooks / booksPerPage);
            const pageInfo = document.getElementById('page-info');
            const prevBtn = document.getElementById('prev-btn');
            const nextBtn = document.getElementById('next-btn');

            pageInfo.textContent = `Page ${currentPage} of ${totalPages} (${totalBooks} total books)`;

            prevBtn.disabled = currentPage <= 1;
            nextBtn.disabled = currentPage >= totalPages;

            prevBtn.style.opacity = currentPage <= 1 ? '0.5' : '1';
            nextBtn.style.opacity = currentPage >= totalPages ? '0.5' : '1';
        }

        function nextPage() {
            const totalPages = Math.ceil(totalBooks / booksPerPage);
            if (currentPage < totalPages) {
                currentPage++;
                updateURL();
                if (isSearching) {
                    const query = document.getElementById('search-input').value;
                    searchBooks(query);
                } else {
                    loadBooks();
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }

        function previousPage() {
            if (currentPage > 1) {
                currentPage--;
                updateURL();
                if (isSearching) {
                    const query = document.getElementById('search-input').value;
                    searchBooks(query);
                } else {
                    loadBooks();
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
        }

        function applyFiltersAndSort() {
            currentPage = 1;
            updateURL();
            if (isSearching) {
                const query = document.getElementById('search-input').value;
                searchBooks(query);
            } else {
                loadBooks();
            }
        }

        function clearFilters() {
            document.getElementById('sort-field').value = 'title';
            document.getElementById('sort-order').value = 'asc';
            document.getElementById('filter-language').value = '';
            document.getElementById('filter-format').value = '';
            document.getElementById('filter-favorite').value = '';
            document.getElementById('filter-rating').value = '';
            document.getElementById('search-input').value = '';
            isSearching = false;
            currentPage = 1;
            updateURL();
            loadBooks();
        }

        function updateFilterCount() {
            const language = document.getElementById('filter-language').value;
            const format = document.getElementById('filter-format').value;
            const favorite = document.getElementById('filter-favorite').value;
            const rating = document.getElementById('filter-rating').value;

            let activeFilters = 0;
            if (language) activeFilters++;
            if (format) activeFilters++;
            if (favorite) activeFilters++;
            if (rating) activeFilters++;

            const filterCount = document.getElementById('filter-count');
            if (activeFilters > 0) {
                filterCount.textContent = `${activeFilters} filter${activeFilters > 1 ? 's' : ''} active`;
                filterCount.style.fontWeight = '600';
            } else {
                filterCount.textContent = '';
            }
        }
    </script>
</body>
</html>
"""
