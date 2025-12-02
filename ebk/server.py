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
from . import opds


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
    favorites_count: int = 0
    reading_count: int = 0
    completed_count: int = 0


class PaginatedBooksResponse(BaseModel):
    items: List[BookResponse]
    total: int
    offset: int
    limit: int


class FolderImportRequest(BaseModel):
    folder_path: str
    recursive: bool = True
    extensions: str = "pdf,epub,mobi,azw3,txt"
    limit: Optional[int] = None
    extract_text: bool = True
    extract_cover: bool = True


class CalibreImportRequest(BaseModel):
    calibre_path: str
    limit: Optional[int] = None


class ImportProgress(BaseModel):
    total: int
    imported: int
    failed: int
    current_file: Optional[str] = None
    status: str  # "running", "completed", "failed"
    errors: List[str] = []


class URLImportRequest(BaseModel):
    url: str
    extract_text: bool = True
    extract_cover: bool = True


class OPDSImportRequest(BaseModel):
    opds_url: str
    limit: Optional[int] = None
    extract_text: bool = True
    extract_cover: bool = True


class ISBNImportRequest(BaseModel):
    isbn: str


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


def set_library(library: Library):
    """Set the library instance directly (for testing)."""
    global _library, _library_path
    _library = library
    _library_path = library.library_path


def create_app(library_path: Path) -> FastAPI:
    """Create FastAPI application with initialized library."""
    # Initialize library
    init_library(library_path)

    # Initialize OPDS with the same library
    opds.set_library(_library)

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

# Include OPDS router
app.include_router(opds.router)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web interface."""
    return get_web_interface()


@app.get("/api/books", response_model=PaginatedBooksResponse)
async def list_books(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    author: Optional[str] = None,
    subject: Optional[str] = None,
    language: Optional[str] = None,
    favorite: Optional[bool] = None,
    reading_status: Optional[str] = None,
    format_filter: Optional[str] = None,
    sort_by: Optional[str] = Query(None, alias="sort"),
    sort_order: Optional[str] = Query("asc", alias="order"),
    min_rating: Optional[float] = Query(None, alias="rating")
):
    """List books with filtering, sorting, and pagination."""
    lib = get_library()

    query = lib.query()

    # Apply filters BEFORE pagination
    if author:
        query = query.filter_by_author(author)
    if subject:
        query = query.filter_by_subject(subject)
    if language:
        query = query.filter_by_language(language)
    if favorite is not None:
        query = query.filter_by_favorite(favorite)
    if reading_status:
        query = query.filter_by_reading_status(reading_status)
    if format_filter:
        query = query.filter_by_format(format_filter)
    if min_rating is not None:
        query = query.filter_by_rating(int(min_rating))
    if search:
        query = query.filter_by_text(search)

    # Get total count BEFORE pagination
    total = query.count()

    # Apply sorting before pagination
    if sort_by:
        desc = (sort_order == "desc")
        query = query.order_by(sort_by, desc=desc)
    else:
        # Default sort by title
        query = query.order_by("title", desc=False)

    # Apply pagination AFTER all filters and sorting
    query = query.limit(limit).offset(offset)
    books = query.all()

    # Convert to paginated response format
    return PaginatedBooksResponse(
        items=[_book_to_response(book) for book in books],
        total=total,
        offset=offset,
        limit=limit
    )


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


@app.post("/api/books/import/folder")
async def import_folder(request: FolderImportRequest):
    """Import books from a folder."""
    lib = get_library()
    folder_path = Path(request.folder_path)

    if not folder_path.exists():
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder_path}")

    if not folder_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {folder_path}")

    # Parse extensions
    extensions = [ext.strip().lower() for ext in request.extensions.split(",")]

    # Find all matching files
    files = []
    if request.recursive:
        for ext in extensions:
            files.extend(folder_path.rglob(f"*.{ext}"))
    else:
        for ext in extensions:
            files.extend(folder_path.glob(f"*.{ext}"))

    # Apply limit if specified
    if request.limit:
        files = files[:request.limit]

    # Import books
    results = {
        "total": len(files),
        "imported": 0,
        "failed": 0,
        "errors": [],
        "books": []
    }

    for file_path in files:
        try:
            metadata = extract_metadata(str(file_path))
            book = lib.add_book(
                file_path,
                metadata=metadata,
                extract_text=request.extract_text,
                extract_cover=request.extract_cover
            )
            if book:
                results["imported"] += 1
                results["books"].append(_book_to_response(book))
            else:
                results["failed"] += 1
                results["errors"].append(f"Failed to import: {file_path.name}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{file_path.name}: {str(e)}")

    return results


@app.post("/api/books/import/calibre")
async def import_calibre(request: CalibreImportRequest):
    """Import books from a Calibre library."""
    from .calibre_import import import_calibre_library

    lib = get_library()
    calibre_path = Path(request.calibre_path)

    if not calibre_path.exists():
        raise HTTPException(status_code=400, detail=f"Calibre library not found: {calibre_path}")

    # Check for Calibre metadata database
    metadata_db = calibre_path / "metadata.db"
    if not metadata_db.exists():
        raise HTTPException(status_code=400, detail="Not a valid Calibre library (metadata.db not found)")

    try:
        results = import_calibre_library(
            calibre_path,
            lib,
            limit=request.limit
        )
        return {
            "total": results.get("total", 0),
            "imported": results.get("imported", 0),
            "failed": results.get("failed", 0),
            "errors": results.get("errors", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibre import failed: {str(e)}")


@app.post("/api/books/import/url")
async def import_from_url(request: URLImportRequest):
    """Import an ebook from a URL."""
    import httpx
    import re

    lib = get_library()
    url = request.url.strip()

    # Validate URL
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="Invalid URL. Must start with http:// or https://")

    # Supported extensions
    supported_extensions = {'.pdf', '.epub', '.mobi', '.azw', '.azw3', '.txt'}

    try:
        # Download the file
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Try to determine filename from Content-Disposition header or URL
            filename = None
            content_disposition = response.headers.get('content-disposition', '')
            if 'filename=' in content_disposition:
                match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disposition)
                if match:
                    filename = match.group(1)

            if not filename:
                # Extract from URL path
                from urllib.parse import urlparse, unquote
                parsed = urlparse(url)
                filename = unquote(parsed.path.split('/')[-1])

            if not filename:
                filename = 'downloaded_book'

            # Check extension
            ext = Path(filename).suffix.lower()
            if ext not in supported_extensions:
                # Try to guess from content-type
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type:
                    ext = '.pdf'
                elif 'epub' in content_type:
                    ext = '.epub'
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Unsupported file type. Supported: {', '.join(supported_extensions)}"
                    )
                filename = Path(filename).stem + ext

            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(response.content)
                tmp_path = Path(tmp.name)

        # Extract metadata and import
        metadata = extract_metadata(str(tmp_path))
        book = lib.add_book(
            tmp_path,
            metadata=metadata,
            extract_text=request.extract_text,
            extract_cover=request.extract_cover
        )

        # Clean up temp file
        tmp_path.unlink()

        if not book:
            raise HTTPException(status_code=400, detail="Failed to import book from URL")

        return _book_to_response(book)

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to download file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@app.post("/api/books/import/opds")
async def import_from_opds(request: OPDSImportRequest):
    """Import books from an OPDS catalog feed."""
    import httpx
    import xml.etree.ElementTree as ET

    lib = get_library()
    opds_url = request.opds_url.strip()

    if not opds_url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail="Invalid URL. Must start with http:// or https://")

    results = {
        "total": 0,
        "imported": 0,
        "failed": 0,
        "errors": [],
        "books": []
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
            # Fetch OPDS feed
            response = await client.get(opds_url)
            response.raise_for_status()

            # Parse OPDS (Atom) feed
            root = ET.fromstring(response.content)

            # OPDS uses Atom namespace
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'opds': 'http://opds-spec.org/2010/catalog',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }

            entries = root.findall('.//atom:entry', ns)
            if not entries:
                # Try without namespace (some feeds don't use it properly)
                entries = root.findall('.//entry')

            if request.limit:
                entries = entries[:request.limit]

            results["total"] = len(entries)

            for entry in entries:
                try:
                    # Find acquisition link (the actual book file)
                    acquisition_link = None
                    for link in entry.findall('atom:link', ns) or entry.findall('link'):
                        rel = link.get('rel', '')
                        href = link.get('href', '')
                        link_type = link.get('type', '')

                        # Look for acquisition links
                        if 'acquisition' in rel and href:
                            # Prefer epub, then pdf
                            if 'epub' in link_type:
                                acquisition_link = href
                                break
                            elif 'pdf' in link_type and not acquisition_link:
                                acquisition_link = href

                    if not acquisition_link:
                        results["failed"] += 1
                        title_el = entry.find('atom:title', ns) or entry.find('title')
                        title = title_el.text if title_el is not None else 'Unknown'
                        results["errors"].append(f"No download link found for: {title}")
                        continue

                    # Make URL absolute if needed
                    if not acquisition_link.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        acquisition_link = urljoin(opds_url, acquisition_link)

                    # Download and import
                    file_response = await client.get(acquisition_link, timeout=60.0)
                    file_response.raise_for_status()

                    # Determine extension
                    content_type = file_response.headers.get('content-type', '')
                    if 'epub' in content_type:
                        ext = '.epub'
                    elif 'pdf' in content_type:
                        ext = '.pdf'
                    elif 'mobi' in content_type:
                        ext = '.mobi'
                    else:
                        ext = '.epub'  # Default guess

                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(file_response.content)
                        tmp_path = Path(tmp.name)

                    metadata = extract_metadata(str(tmp_path))
                    book = lib.add_book(
                        tmp_path,
                        metadata=metadata,
                        extract_text=request.extract_text,
                        extract_cover=request.extract_cover
                    )

                    tmp_path.unlink()

                    if book:
                        results["imported"] += 1
                        results["books"].append(_book_to_response(book))
                    else:
                        results["failed"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append(str(e))

        return results

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch OPDS feed: {str(e)}")
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid OPDS feed format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OPDS import failed: {str(e)}")


@app.post("/api/books/import/isbn")
async def import_from_isbn(request: ISBNImportRequest):
    """Create a book entry from ISBN lookup (metadata only, no file)."""
    import httpx
    import re

    lib = get_library()
    isbn = re.sub(r'[^0-9X]', '', request.isbn.upper())

    if len(isbn) not in (10, 13):
        raise HTTPException(status_code=400, detail="Invalid ISBN. Must be 10 or 13 digits.")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Try Google Books API first
            google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}"
            response = await client.get(google_url)

            metadata = None

            if response.status_code == 200:
                data = response.json()
                if data.get('totalItems', 0) > 0:
                    volume = data['items'][0]['volumeInfo']
                    metadata = {
                        'title': volume.get('title', 'Unknown'),
                        'subtitle': volume.get('subtitle'),
                        'authors': volume.get('authors', []),
                        'publisher': volume.get('publisher'),
                        'publication_date': volume.get('publishedDate'),
                        'description': volume.get('description'),
                        'page_count': volume.get('pageCount'),
                        'language': volume.get('language'),
                        'subjects': volume.get('categories', []),
                        'identifiers': [{'scheme': 'isbn', 'value': isbn}],
                    }

            # Fallback to Open Library if Google didn't find it
            if not metadata:
                ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
                response = await client.get(ol_url)

                if response.status_code == 200:
                    data = response.json()
                    key = f"ISBN:{isbn}"
                    if key in data:
                        book_data = data[key]
                        metadata = {
                            'title': book_data.get('title', 'Unknown'),
                            'subtitle': book_data.get('subtitle'),
                            'authors': [a.get('name') for a in book_data.get('authors', [])],
                            'publisher': book_data.get('publishers', [{}])[0].get('name') if book_data.get('publishers') else None,
                            'publication_date': book_data.get('publish_date'),
                            'page_count': book_data.get('number_of_pages'),
                            'subjects': [s.get('name') for s in book_data.get('subjects', [])],
                            'identifiers': [{'scheme': 'isbn', 'value': isbn}],
                        }

            if not metadata:
                raise HTTPException(status_code=404, detail=f"No book found for ISBN: {isbn}")

            # Create book entry without a file
            from .db.models import Book, Author, Subject, Identifier
            from .services.import_service import get_sort_name
            import hashlib

            # Generate unique_id based on ISBN
            unique_id = hashlib.md5(f"isbn:{isbn}".encode()).hexdigest()

            book = Book(
                unique_id=unique_id,
                title=metadata['title'],
                subtitle=metadata.get('subtitle'),
                publisher=metadata.get('publisher'),
                publication_date=metadata.get('publication_date'),
                description=metadata.get('description'),
                page_count=metadata.get('page_count'),
                language=metadata.get('language'),
            )

            # Add authors
            for author_name in metadata.get('authors', []):
                if author_name:
                    author = lib.session.query(Author).filter_by(name=author_name).first()
                    if not author:
                        author = Author(name=author_name, sort_name=get_sort_name(author_name))
                        lib.session.add(author)
                    book.authors.append(author)

            # Add subjects
            for subject_name in metadata.get('subjects', []):
                if subject_name:
                    subject = lib.session.query(Subject).filter_by(name=subject_name).first()
                    if not subject:
                        subject = Subject(name=subject_name)
                        lib.session.add(subject)
                    book.subjects.append(subject)

            # Add identifiers
            for ident in metadata.get('identifiers', []):
                identifier = Identifier(scheme=ident['scheme'], value=ident['value'])
                book.identifiers.append(identifier)

            lib.session.add(book)
            lib.session.commit()

            return _book_to_response(book)

    except httpx.HTTPError as e:
        raise HTTPException(status_code=400, detail=f"Failed to lookup ISBN: {str(e)}")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"ISBN import failed: {str(e)}")


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
    from .db.models import File, PersonalMetadata
    from sqlalchemy import func
    total_size = lib.session.query(func.sum(File.size_bytes)).scalar() or 0

    # Get favorites count
    favorites_count = lib.session.query(func.count(PersonalMetadata.id)).filter(
        PersonalMetadata.favorite == True
    ).scalar() or 0

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
        formats=formats,
        favorites_count=favorites_count,
        reading_count=stats.get('reading_count', 0),
        completed_count=stats.get('read_count', 0)
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
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ebk Library Manager</title>
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        :root {
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
            --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
            --shadow: 0 1px 3px rgba(0,0,0,0.1), 0 1px 2px rgba(0,0,0,0.06);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
            --radius: 8px;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --transition: 0.15s ease;
        }

        [data-theme="dark"] {
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
        }

        html { font-size: 16px; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }

        /* Layout */
        .app { display: flex; min-height: 100vh; }

        /* Sidebar */
        .sidebar {
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
        }

        .sidebar.open { transform: translateX(0); }

        @media (min-width: 1024px) {
            .sidebar {
                transform: translateX(0);
                position: sticky;
                height: 100vh;
            }
        }

        .sidebar-header {
            padding: 24px;
            border-bottom: 1px solid var(--border);
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--accent);
        }

        .logo-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent), #8b5cf6);
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
            color: white;
        }

        .sidebar-nav {
            flex: 1;
            overflow-y: auto;
            padding: 16px;
        }

        .nav-section { margin-bottom: 24px; }

        .nav-section-title {
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--text-muted);
            padding: 8px 12px;
            margin-bottom: 4px;
        }

        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 10px 12px;
            border-radius: var(--radius);
            color: var(--text-secondary);
            cursor: pointer;
            transition: all var(--transition);
            font-size: 0.9rem;
            font-weight: 500;
        }

        .nav-item:hover {
            background: var(--bg-tertiary);
            color: var(--text-primary);
        }

        .nav-item.active {
            background: var(--accent);
            color: white;
        }

        .nav-item-icon { font-size: 1.1rem; opacity: 0.9; }

        .nav-item-count {
            margin-left: auto;
            font-size: 0.75rem;
            font-weight: 600;
            background: var(--bg-tertiary);
            padding: 2px 8px;
            border-radius: 10px;
            color: var(--text-muted);
        }

        .nav-item.active .nav-item-count {
            background: rgba(255,255,255,0.2);
            color: white;
        }

        .sidebar-footer {
            padding: 16px 24px;
            border-top: 1px solid var(--border);
        }

        .sidebar-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.5);
            z-index: 99;
        }

        .sidebar-overlay.active { display: block; }

        /* Main Content */
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }

        /* Header */
        .header {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
            position: sticky;
            top: 0;
            z-index: 50;
        }

        .menu-btn {
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
            transition: all var(--transition);
        }

        .menu-btn:hover { background: var(--bg-hover); }

        @media (min-width: 1024px) { .menu-btn { display: none; } }

        .search-box {
            flex: 1;
            max-width: 600px;
            position: relative;
        }

        .search-input {
            width: 100%;
            padding: 12px 16px 12px 48px;
            border: 2px solid var(--border);
            border-radius: var(--radius-lg);
            font-size: 0.95rem;
            background: var(--bg-primary);
            color: var(--text-primary);
            transition: all var(--transition);
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-light);
        }

        .search-input::placeholder { color: var(--text-muted); }

        .search-icon {
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            font-size: 1.1rem;
        }

        .header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .icon-btn {
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
            transition: all var(--transition);
        }

        .icon-btn:hover {
            background: var(--accent);
            color: white;
        }

        .icon-btn.active {
            background: var(--accent);
            color: white;
        }

        /* Toolbar */
        .toolbar {
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }

        .toolbar-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .toolbar-label {
            font-size: 0.8rem;
            color: var(--text-muted);
            font-weight: 500;
        }

        .toolbar-select {
            padding: 8px 12px;
            border: 1px solid var(--border);
            border-radius: var(--radius);
            font-size: 0.85rem;
            background: var(--bg-primary);
            color: var(--text-primary);
            cursor: pointer;
            transition: all var(--transition);
        }

        .toolbar-select:focus {
            outline: none;
            border-color: var(--accent);
        }

        .toolbar-divider {
            width: 1px;
            height: 24px;
            background: var(--border);
            margin: 0 8px;
        }

        .results-info {
            margin-left: auto;
            font-size: 0.85rem;
            color: var(--text-muted);
        }

        /* Stats Bar */
        .stats-bar {
            display: flex;
            gap: 24px;
            padding: 16px 24px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            overflow-x: auto;
        }

        .stat-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            min-width: fit-content;
        }

        .stat-icon {
            width: 40px;
            height: 40px;
            border-radius: var(--radius);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }

        .stat-icon.books { background: var(--accent-light); color: var(--accent); }
        .stat-icon.authors { background: var(--success-light); color: var(--success); }
        .stat-icon.files { background: var(--warning-light); color: var(--warning); }
        .stat-icon.storage { background: var(--danger-light); color: var(--danger); }

        .stat-content { display: flex; flex-direction: column; }
        .stat-value { font-size: 1.25rem; font-weight: 700; color: var(--text-primary); line-height: 1.2; }
        .stat-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }

        /* Content Area */
        .content {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
        }

        /* Grid View */
        .book-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
        }

        .book-card {
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: all var(--transition);
            cursor: pointer;
        }

        .book-card:hover {
            transform: translateY(-4px);
            box-shadow: var(--shadow-lg);
        }

        .book-cover {
            aspect-ratio: 2/3;
            background: var(--bg-tertiary);
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
        }

        .book-cover img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .book-cover-placeholder {
            font-size: 3rem;
            color: var(--text-muted);
        }

        .book-favorite {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(0,0,0,0.5);
            color: var(--warning);
            padding: 4px 8px;
            border-radius: var(--radius);
            font-size: 0.9rem;
        }

        .book-info { padding: 16px; }

        .book-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            margin-bottom: 4px;
        }

        .book-author {
            font-size: 0.85rem;
            color: var(--text-secondary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .book-meta {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-top: 12px;
            flex-wrap: wrap;
        }

        .badge {
            font-size: 0.7rem;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.02em;
        }

        .badge-format { background: var(--bg-tertiary); color: var(--text-secondary); }
        .badge-language { background: var(--warning-light); color: #92400e; }
        .badge-rating { background: var(--accent-light); color: var(--accent); }

        .book-rating {
            display: flex;
            align-items: center;
            gap: 4px;
            color: var(--warning);
            font-size: 0.85rem;
        }

        /* List View */
        .book-list { display: flex; flex-direction: column; gap: 12px; }

        .book-list-item {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 16px;
            display: flex;
            gap: 16px;
            align-items: flex-start;
            box-shadow: var(--shadow);
            cursor: pointer;
            transition: all var(--transition);
        }

        .book-list-item:hover { box-shadow: var(--shadow-md); }

        .book-list-cover {
            width: 60px;
            height: 90px;
            background: var(--bg-tertiary);
            border-radius: 4px;
            overflow: hidden;
            flex-shrink: 0;
        }

        .book-list-cover img { width: 100%; height: 100%; object-fit: cover; }

        .book-list-info { flex: 1; min-width: 0; }

        .book-list-title { font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
        .book-list-author { font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 8px; }

        .book-list-meta {
            display: flex;
            gap: 16px;
            font-size: 0.8rem;
            color: var(--text-muted);
            flex-wrap: wrap;
        }

        /* Table View */
        .book-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }

        .book-table th {
            text-align: left;
            padding: 12px 16px;
            background: var(--bg-tertiary);
            font-weight: 600;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border);
            cursor: pointer;
            user-select: none;
            transition: background var(--transition);
        }

        .book-table th:hover { background: var(--bg-hover); }

        .book-table td {
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            color: var(--text-primary);
        }

        .book-table tr:hover td { background: var(--bg-tertiary); }

        .table-title { font-weight: 500; cursor: pointer; }
        .table-title:hover { color: var(--accent); }

        /* Pagination */
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 8px;
            margin-top: 32px;
            flex-wrap: wrap;
        }

        .page-btn {
            padding: 10px 16px;
            border: 1px solid var(--border);
            background: var(--bg-secondary);
            color: var(--text-primary);
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all var(--transition);
        }

        .page-btn:hover:not(:disabled) {
            border-color: var(--accent);
            color: var(--accent);
        }

        .page-btn.active {
            background: var(--accent);
            border-color: var(--accent);
            color: white;
        }

        .page-btn:disabled { opacity: 0.5; cursor: not-allowed; }

        .page-info {
            padding: 0 16px;
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 80px 20px;
            color: var(--text-muted);
        }

        .empty-state-icon { font-size: 4rem; margin-bottom: 16px; opacity: 0.5; }
        .empty-state h3 { color: var(--text-secondary); margin-bottom: 8px; font-size: 1.25rem; }

        /* Loading */
        .loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }

        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 16px;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        /* Modal */
        .modal {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.6);
            z-index: 200;
            padding: 20px;
            overflow-y: auto;
            backdrop-filter: blur(4px);
        }

        .modal.active {
            display: flex;
            align-items: flex-start;
            justify-content: center;
        }

        .modal-content {
            background: var(--bg-secondary);
            border-radius: var(--radius-xl);
            max-width: 700px;
            width: 100%;
            margin-top: 40px;
            box-shadow: var(--shadow-lg);
            animation: modalIn 0.2s ease;
        }

        @keyframes modalIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .modal-header {
            padding: 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
        }

        .modal-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.3;
        }

        .modal-close {
            width: 36px;
            height: 36px;
            border: none;
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            cursor: pointer;
            font-size: 1.5rem;
            color: var(--text-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: all var(--transition);
        }

        .modal-close:hover { background: var(--danger); color: white; }

        .modal-body {
            padding: 24px;
            max-height: 70vh;
            overflow-y: auto;
        }

        /* Form Elements */
        .form-group { margin-bottom: 20px; }

        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-primary);
            font-size: 0.9rem;
        }

        .form-control {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid var(--border);
            border-radius: var(--radius);
            font-size: 0.95rem;
            background: var(--bg-primary);
            color: var(--text-primary);
            transition: all var(--transition);
        }

        .form-control:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-light);
        }

        textarea.form-control { min-height: 120px; resize: vertical; }

        .form-check {
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
        }

        .form-check input[type="checkbox"] {
            width: 18px;
            height: 18px;
            accent-color: var(--accent);
        }

        /* Buttons */
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 12px 20px;
            border: none;
            border-radius: var(--radius);
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all var(--transition);
        }

        .btn-primary { background: var(--accent); color: white; }
        .btn-primary:hover { background: var(--accent-hover); }

        .btn-secondary { background: var(--bg-tertiary); color: var(--text-primary); }
        .btn-secondary:hover { background: var(--bg-hover); }

        .btn-success { background: var(--success); color: white; }
        .btn-success:hover { background: #059669; }

        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: #dc2626; }

        .btn-outline {
            background: transparent;
            border: 2px solid var(--border);
            color: var(--text-primary);
        }
        .btn-outline:hover { border-color: var(--accent); color: var(--accent); }

        .btn-group { display: flex; gap: 12px; flex-wrap: wrap; }

        /* Alerts */
        .alert {
            padding: 16px 20px;
            border-radius: var(--radius);
            margin-bottom: 20px;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .alert-success { background: var(--success-light); color: #065f46; }
        .alert-error { background: var(--danger-light); color: #991b1b; }

        /* Detail Section */
        .detail-section { margin-bottom: 24px; }

        .detail-label {
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-muted);
            margin-bottom: 8px;
        }

        .detail-value { color: var(--text-primary); line-height: 1.6; }

        .detail-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .tag {
            background: var(--bg-tertiary);
            color: var(--text-secondary);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
        }

        /* File List */
        .file-list { list-style: none; }

        .file-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 0;
            border-bottom: 1px solid var(--border);
        }

        .file-item:last-child { border-bottom: none; }

        .file-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            background: var(--accent);
            color: white;
            border-radius: var(--radius);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.85rem;
            transition: all var(--transition);
        }

        .file-btn:hover { background: var(--accent-hover); }

        .file-size { color: var(--text-muted); font-size: 0.85rem; }

        /* Modal Cover */
        .modal-cover {
            text-align: center;
            margin-bottom: 24px;
        }

        .modal-cover img {
            max-width: 200px;
            max-height: 300px;
            border-radius: var(--radius);
            box-shadow: var(--shadow-lg);
        }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 2px solid var(--border);
            margin-bottom: 20px;
        }

        .tab {
            padding: 12px 20px;
            border: none;
            background: none;
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            margin-bottom: -2px;
            transition: all var(--transition);
        }

        .tab:hover {
            color: var(--text-primary);
            background: var(--bg-tertiary);
        }

        .tab.active {
            color: var(--accent);
            border-bottom-color: var(--accent);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .import-help {
            background: var(--bg-tertiary);
            border-radius: var(--radius);
            padding: 12px 16px;
            margin-bottom: 16px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        .import-help code {
            background: var(--bg-secondary);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: monospace;
        }

        /* Keyboard Shortcuts Hint */
        .keyboard-hint {
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
            display: none;
        }

        @media (min-width: 1024px) { .keyboard-hint { display: block; } }

        .kbd {
            display: inline-block;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 4px;
            padding: 2px 6px;
            font-family: monospace;
            font-size: 0.75rem;
            margin: 0 2px;
        }

        /* Print Styles */
        @media print {
            .sidebar, .header, .toolbar, .pagination, .keyboard-hint { display: none !important; }
            .main { margin-left: 0 !important; }
            .book-card, .book-list-item { break-inside: avoid; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
    </style>
</head>
<body>
    <div class="sidebar-overlay" onclick="toggleSidebar()"></div>

    <div class="app">
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <div class="logo-icon">&#128218;</div>
                    <span>ebk Library</span>
                </div>
            </div>
            <nav class="sidebar-nav">
                <div class="nav-section">
                    <div class="nav-section-title">Library</div>
                    <div class="nav-item active" data-filter="all" onclick="setFilter('all')">
                        <span class="nav-item-icon">&#128214;</span>
                        All Books
                        <span class="nav-item-count" id="count-all">0</span>
                    </div>
                    <div class="nav-item" data-filter="favorites" onclick="setFilter('favorites')">
                        <span class="nav-item-icon">&#11088;</span>
                        Favorites
                        <span class="nav-item-count" id="count-favorites">0</span>
                    </div>
                    <div class="nav-item" data-filter="reading" onclick="setFilter('reading')">
                        <span class="nav-item-icon">&#128196;</span>
                        Currently Reading
                        <span class="nav-item-count" id="count-reading">0</span>
                    </div>
                    <div class="nav-item" data-filter="completed" onclick="setFilter('completed')">
                        <span class="nav-item-icon">&#9989;</span>
                        Completed
                        <span class="nav-item-count" id="count-completed">0</span>
                    </div>
                </div>
                <div class="nav-section">
                    <div class="nav-section-title">Actions</div>
                    <div class="nav-item" onclick="showImportModal()">
                        <span class="nav-item-icon">&#10133;</span>
                        Import Book
                    </div>
                    <div class="nav-item" onclick="refreshBooks()">
                        <span class="nav-item-icon">&#128260;</span>
                        Refresh
                    </div>
                </div>
            </nav>
            <div class="sidebar-footer">
                <div style="font-size: 0.75rem; color: var(--text-muted);">
                    ebk Library Manager
                </div>
            </div>
        </aside>

        <main class="main">
            <header class="header">
                <button class="menu-btn" onclick="toggleSidebar()">&#9776;</button>
                <div class="search-box">
                    <span class="search-icon">&#128269;</span>
                    <input type="text" class="search-input" id="search-input"
                           placeholder="Search books by title, author, description..." autocomplete="off">
                </div>
                <div class="header-actions">
                    <button class="icon-btn active" id="view-grid" onclick="setView('grid')" title="Grid View">&#9638;</button>
                    <button class="icon-btn" id="view-list" onclick="setView('list')" title="List View">&#9776;</button>
                    <button class="icon-btn" id="view-table" onclick="setView('table')" title="Table View">&#9636;</button>
                    <button class="icon-btn" id="theme-toggle" onclick="toggleTheme()" title="Toggle Dark Mode">&#127769;</button>
                </div>
            </header>

            <div class="stats-bar" id="stats-bar">
                <div class="stat-item">
                    <div class="stat-icon books">&#128218;</div>
                    <div class="stat-content">
                        <div class="stat-value" id="stat-books">0</div>
                        <div class="stat-label">Books</div>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon authors">&#128100;</div>
                    <div class="stat-content">
                        <div class="stat-value" id="stat-authors">0</div>
                        <div class="stat-label">Authors</div>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon files">&#128196;</div>
                    <div class="stat-content">
                        <div class="stat-value" id="stat-files">0</div>
                        <div class="stat-label">Files</div>
                    </div>
                </div>
                <div class="stat-item">
                    <div class="stat-icon storage">&#128190;</div>
                    <div class="stat-content">
                        <div class="stat-value" id="stat-storage">0 MB</div>
                        <div class="stat-label">Storage</div>
                    </div>
                </div>
            </div>

            <div class="toolbar">
                <div class="toolbar-group">
                    <span class="toolbar-label">Sort:</span>
                    <select class="toolbar-select" id="sort-field" onchange="applyFilters()">
                        <option value="title">Title</option>
                        <option value="created_at">Date Added</option>
                        <option value="publication_date">Published</option>
                        <option value="rating">Rating</option>
                    </select>
                    <select class="toolbar-select" id="sort-order" onchange="applyFilters()">
                        <option value="asc">A-Z</option>
                        <option value="desc">Z-A</option>
                    </select>
                </div>
                <div class="toolbar-divider"></div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Language:</span>
                    <select class="toolbar-select" id="filter-language" onchange="applyFilters()">
                        <option value="">All</option>
                    </select>
                </div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Format:</span>
                    <select class="toolbar-select" id="filter-format" onchange="applyFilters()">
                        <option value="">All</option>
                    </select>
                </div>
                <div class="toolbar-group">
                    <span class="toolbar-label">Rating:</span>
                    <select class="toolbar-select" id="filter-rating" onchange="applyFilters()">
                        <option value="">Any</option>
                        <option value="4">4+ Stars</option>
                        <option value="3">3+ Stars</option>
                        <option value="2">2+ Stars</option>
                        <option value="1">1+ Stars</option>
                    </select>
                </div>
                <button class="btn btn-outline" onclick="clearFilters()" style="padding: 8px 12px; font-size: 0.8rem;">
                    Clear Filters
                </button>
                <div class="results-info" id="results-info"></div>
            </div>

            <div id="message-container"></div>

            <div class="content">
                <div id="loading" class="loading" style="display: none;">
                    <div class="spinner"></div>
                    <p>Loading books...</p>
                </div>
                <div id="book-container"></div>
                <div id="empty-state" class="empty-state" style="display: none;">
                    <div class="empty-state-icon">&#128366;</div>
                    <h3>No books found</h3>
                    <p>Try adjusting your search or filters</p>
                </div>
                <div class="pagination" id="pagination"></div>
            </div>
        </main>
    </div>

    <!-- Edit Modal -->
    <div id="edit-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title">Edit Book</h2>
                <button class="modal-close" onclick="closeModal('edit-modal')">&times;</button>
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
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label class="form-label">Language</label>
                            <input type="text" id="edit-language" class="form-control">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Publisher</label>
                            <input type="text" id="edit-publisher" class="form-control">
                        </div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label class="form-label">Publication Date</label>
                            <input type="text" id="edit-publication-date" class="form-control" placeholder="YYYY-MM-DD">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Rating (1-5)</label>
                            <input type="number" id="edit-rating" class="form-control" min="1" max="5" step="0.5">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Description</label>
                        <textarea id="edit-description" class="form-control"></textarea>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                        <div class="form-group">
                            <label class="form-label">Reading Status</label>
                            <select id="edit-status" class="form-control">
                                <option value="unread">Unread</option>
                                <option value="reading">Reading</option>
                                <option value="completed">Completed</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Tags (comma-separated)</label>
                            <input type="text" id="edit-tags" class="form-control">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-check">
                            <input type="checkbox" id="edit-favorite">
                            <span>Mark as Favorite</span>
                        </label>
                    </div>
                    <div class="btn-group">
                        <button type="submit" class="btn btn-primary">Save Changes</button>
                        <button type="button" class="btn btn-danger" onclick="deleteBook()">Delete Book</button>
                        <button type="button" class="btn btn-secondary" onclick="closeModal('edit-modal')">Cancel</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Import Modal -->
    <div id="import-modal" class="modal">
        <div class="modal-content" style="max-width: 600px;">
            <div class="modal-header">
                <h2 class="modal-title">Import Books</h2>
                <button class="modal-close" onclick="closeModal('import-modal')">&times;</button>
            </div>
            <div class="modal-body">
                <div class="tabs">
                    <button class="tab active" onclick="switchImportTab('file')">File</button>
                    <button class="tab" onclick="switchImportTab('url')">URL</button>
                    <button class="tab" onclick="switchImportTab('folder')">Folder</button>
                    <button class="tab" onclick="switchImportTab('calibre')">Calibre</button>
                    <button class="tab" onclick="switchImportTab('opds')">OPDS</button>
                    <button class="tab" onclick="switchImportTab('isbn')">ISBN</button>
                </div>

                <!-- Single File Import -->
                <div id="import-tab-file" class="tab-content active">
                    <div class="import-help">
                        Upload a single ebook file (PDF, EPUB, MOBI, AZW3, TXT)
                    </div>
                    <form id="import-form-file" onsubmit="importSingleFile(event)">
                        <div class="form-group">
                            <label class="form-label">Select File</label>
                            <input type="file" id="import-file" class="form-control"
                                   accept=".pdf,.epub,.mobi,.azw,.azw3,.txt" required>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-extract-text" checked>
                                <span>Extract full text for search</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-extract-cover" checked>
                                <span>Extract cover image</span>
                            </label>
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Import File</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- Folder Import -->
                <div id="import-tab-folder" class="tab-content">
                    <div class="import-help">
                        Import all ebook files from a folder on the server. Enter the absolute path to the folder.
                    </div>
                    <form id="import-form-folder" onsubmit="importFolder(event)">
                        <div class="form-group">
                            <label class="form-label">Folder Path</label>
                            <input type="text" id="import-folder-path" class="form-control"
                                   placeholder="/path/to/ebooks" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">File Extensions</label>
                            <input type="text" id="import-folder-extensions" class="form-control"
                                   value="pdf,epub,mobi,azw3,txt" placeholder="pdf,epub,mobi">
                        </div>
                        <div class="form-group">
                            <label class="form-label">Limit (optional)</label>
                            <input type="number" id="import-folder-limit" class="form-control"
                                   placeholder="No limit" min="1">
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-folder-recursive" checked>
                                <span>Search subdirectories recursively</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-folder-extract-text" checked>
                                <span>Extract full text for search</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-folder-extract-cover" checked>
                                <span>Extract cover images</span>
                            </label>
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Import Folder</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- Calibre Import -->
                <div id="import-tab-calibre" class="tab-content">
                    <div class="import-help">
                        Import books from a Calibre library. Enter the path to the Calibre library folder
                        (the folder containing <code>metadata.db</code>).
                    </div>
                    <form id="import-form-calibre" onsubmit="importCalibre(event)">
                        <div class="form-group">
                            <label class="form-label">Calibre Library Path</label>
                            <input type="text" id="import-calibre-path" class="form-control"
                                   placeholder="/path/to/Calibre Library" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Limit (optional)</label>
                            <input type="number" id="import-calibre-limit" class="form-control"
                                   placeholder="No limit" min="1">
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Import from Calibre</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- URL Import -->
                <div id="import-tab-url" class="tab-content">
                    <div class="import-help">
                        Download and import an ebook from a direct URL. The URL must point directly to an ebook file (PDF, EPUB, MOBI, etc.).
                    </div>
                    <form id="import-form-url" onsubmit="importFromURL(event)">
                        <div class="form-group">
                            <label class="form-label">Book URL</label>
                            <input type="url" id="import-url" class="form-control"
                                   placeholder="https://example.com/book.epub" required>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-url-extract-text" checked>
                                <span>Extract full text for search</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-url-extract-cover" checked>
                                <span>Extract cover image</span>
                            </label>
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Download &amp; Import</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- OPDS Import -->
                <div id="import-tab-opds" class="tab-content">
                    <div class="import-help">
                        Import books from an OPDS catalog feed. OPDS is a standard format used by many digital libraries and ebook servers.
                    </div>
                    <form id="import-form-opds" onsubmit="importFromOPDS(event)">
                        <div class="form-group">
                            <label class="form-label">OPDS Catalog URL</label>
                            <input type="url" id="import-opds-url" class="form-control"
                                   placeholder="https://example.com/opds/catalog.xml" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Limit (optional)</label>
                            <input type="number" id="import-opds-limit" class="form-control"
                                   placeholder="No limit" min="1">
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-opds-extract-text" checked>
                                <span>Extract full text for search</span>
                            </label>
                        </div>
                        <div class="form-group">
                            <label class="form-check">
                                <input type="checkbox" id="import-opds-extract-cover" checked>
                                <span>Extract cover images</span>
                            </label>
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Import from OPDS</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- ISBN Lookup Import -->
                <div id="import-tab-isbn" class="tab-content">
                    <div class="import-help">
                        Create a book entry by ISBN lookup. Fetches metadata from Google Books and Open Library.
                        <strong>Note:</strong> This creates a metadata-only entry without an actual ebook file.
                    </div>
                    <form id="import-form-isbn" onsubmit="importFromISBN(event)">
                        <div class="form-group">
                            <label class="form-label">ISBN (10 or 13 digits)</label>
                            <input type="text" id="import-isbn" class="form-control"
                                   placeholder="978-3-16-148410-0" required
                                   pattern="[0-9Xx\\-\\s]{10,17}">
                        </div>
                        <div class="btn-group">
                            <button type="submit" class="btn btn-success">Lookup &amp; Create</button>
                            <button type="button" class="btn btn-secondary" onclick="closeModal('import-modal')">Cancel</button>
                        </div>
                    </form>
                </div>

                <!-- Import Progress -->
                <div id="import-progress" style="display: none;">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p id="import-progress-text">Importing books...</p>
                    </div>
                </div>

                <!-- Import Results -->
                <div id="import-results" style="display: none;"></div>
            </div>
        </div>
    </div>

    <!-- Details Modal -->
    <div id="details-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h2 class="modal-title" id="details-title"></h2>
                <button class="modal-close" onclick="closeModal('details-modal')">&times;</button>
            </div>
            <div class="modal-body" id="details-body"></div>
        </div>
    </div>

    <div class="keyboard-hint">
        <kbd>/</kbd> Search &nbsp; <kbd>Esc</kbd> Close &nbsp; <kbd>g</kbd> Grid &nbsp; <kbd>l</kbd> List &nbsp; <kbd>t</kbd> Table
    </div>

    <script>
        // State
        let books = [];
        let currentBookId = null;
        let currentPage = 1;
        let booksPerPage = 48;
        let totalBooks = 0;
        let currentView = 'grid';
        let currentFilter = 'all';
        let isSearching = false;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            initTheme();
            loadStats();
            restoreStateFromURL();
            loadBooks();
            setupEventListeners();
        });

        function initTheme() {
            const saved = localStorage.getItem('ebk_theme');
            if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                document.documentElement.setAttribute('data-theme', 'dark');
            }
        }

        function toggleTheme() {
            const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
            document.documentElement.setAttribute('data-theme', isDark ? 'light' : 'dark');
            localStorage.setItem('ebk_theme', isDark ? 'light' : 'dark');
        }

        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('open');
            document.querySelector('.sidebar-overlay').classList.toggle('active');
        }

        function setupEventListeners() {
            // Search debouncing
            let searchTimeout;
            document.getElementById('search-input').addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    if (e.target.value.length >= 2) {
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

            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    if (e.key === 'Escape') e.target.blur();
                    return;
                }
                if (e.key === '/') { e.preventDefault(); document.getElementById('search-input').focus(); }
                else if (e.key === 'Escape') { closeAllModals(); }
                else if (e.key === 'g') { setView('grid'); }
                else if (e.key === 'l') { setView('list'); }
                else if (e.key === 't') { setView('table'); }
            });

            // Browser back/forward
            window.addEventListener('popstate', () => {
                restoreStateFromURL();
                loadBooks();
            });
        }

        function updateURL() {
            const params = new URLSearchParams();
            if (currentPage > 1) params.set('page', currentPage);
            const searchQuery = document.getElementById('search-input').value;
            if (searchQuery) params.set('q', searchQuery);
            if (currentFilter !== 'all') params.set('filter', currentFilter);
            const language = document.getElementById('filter-language').value;
            const format = document.getElementById('filter-format').value;
            const rating = document.getElementById('filter-rating').value;
            if (language) params.set('language', language);
            if (format) params.set('format', format);
            if (rating) params.set('rating', rating);
            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;
            if (sortField !== 'title') params.set('sort', sortField);
            if (sortOrder !== 'asc') params.set('order', sortOrder);
            const newURL = params.toString() ? '?' + params.toString() : window.location.pathname;
            window.history.pushState({}, '', newURL);
        }

        function restoreStateFromURL() {
            const params = new URLSearchParams(window.location.search);
            currentPage = parseInt(params.get('page')) || 1;
            const searchQuery = params.get('q') || '';
            document.getElementById('search-input').value = searchQuery;
            isSearching = searchQuery.length >= 2;
            currentFilter = params.get('filter') || 'all';
            document.getElementById('filter-language').value = params.get('language') || '';
            document.getElementById('filter-format').value = params.get('format') || '';
            document.getElementById('filter-rating').value = params.get('rating') || '';
            document.getElementById('sort-field').value = params.get('sort') || 'title';
            document.getElementById('sort-order').value = params.get('order') || 'asc';
            updateNavItems();
        }

        let libraryStats = null;

        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                libraryStats = await response.json();

                document.getElementById('stat-books').textContent = libraryStats.total_books;
                document.getElementById('stat-authors').textContent = libraryStats.total_authors;
                document.getElementById('stat-files').textContent = libraryStats.total_files;
                document.getElementById('stat-storage').textContent = libraryStats.total_size_mb.toFixed(1) + ' MB';

                // Update sidebar counts
                document.getElementById('count-all').textContent = libraryStats.total_books;
                document.getElementById('count-favorites').textContent = libraryStats.favorites_count;
                document.getElementById('count-reading').textContent = libraryStats.reading_count;
                document.getElementById('count-completed').textContent = libraryStats.completed_count;

                // Populate dropdowns
                const langSelect = document.getElementById('filter-language');
                libraryStats.languages.forEach(lang => {
                    const opt = document.createElement('option');
                    opt.value = lang;
                    opt.textContent = lang.toUpperCase();
                    langSelect.appendChild(opt);
                });

                const formatSelect = document.getElementById('filter-format');
                libraryStats.formats.forEach(fmt => {
                    const opt = document.createElement('option');
                    opt.value = fmt;
                    opt.textContent = fmt.toUpperCase();
                    formatSelect.appendChild(opt);
                });
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }

        function buildQueryParams() {
            const params = new URLSearchParams();
            const offset = (currentPage - 1) * booksPerPage;
            params.append('limit', booksPerPage);
            params.append('offset', offset);

            // Sidebar filter
            if (currentFilter === 'favorites') params.append('favorite', 'true');
            if (currentFilter === 'reading') params.append('reading_status', 'reading');
            if (currentFilter === 'completed') params.append('reading_status', 'completed');

            const language = document.getElementById('filter-language').value;
            const format = document.getElementById('filter-format').value;
            const rating = document.getElementById('filter-rating').value;
            if (language) params.append('language', language);
            if (format) params.append('format_filter', format);
            if (rating) params.append('rating', rating);

            const sortField = document.getElementById('sort-field').value;
            const sortOrder = document.getElementById('sort-order').value;
            params.append('sort', sortField);
            params.append('order', sortOrder);

            return params.toString();
        }

        async function loadBooks() {
            const loading = document.getElementById('loading');
            const container = document.getElementById('book-container');
            const emptyState = document.getElementById('empty-state');

            loading.style.display = 'flex';
            container.innerHTML = '';
            emptyState.style.display = 'none';

            try {
                const queryParams = buildQueryParams();
                const response = await fetch('/api/books?' + queryParams);
                const data = await response.json();

                books = data.items;
                totalBooks = data.total;

                if (books.length === 0) {
                    emptyState.style.display = 'block';
                } else {
                    renderBooks();
                }
                updatePagination();
                updateResultsInfo();
                updateNavCounts();
            } catch (error) {
                showError('Failed to load books: ' + error.message);
            } finally {
                loading.style.display = 'none';
            }
        }

        async function searchBooks(query) {
            const loading = document.getElementById('loading');
            const container = document.getElementById('book-container');
            const emptyState = document.getElementById('empty-state');

            loading.style.display = 'flex';
            container.innerHTML = '';
            emptyState.style.display = 'none';

            try {
                const response = await fetch('/api/search?q=' + encodeURIComponent(query));
                books = await response.json();
                totalBooks = books.length;

                if (books.length === 0) {
                    emptyState.style.display = 'block';
                } else {
                    renderBooks();
                }
                updateResultsInfo();
                document.getElementById('pagination').innerHTML = '';
            } catch (error) {
                showError('Search failed: ' + error.message);
            } finally {
                loading.style.display = 'none';
            }
        }

        function renderBooks() {
            const container = document.getElementById('book-container');
            if (currentView === 'grid') {
                container.innerHTML = '<div class="book-grid">' + books.map(renderGridCard).join('') + '</div>';
            } else if (currentView === 'list') {
                container.innerHTML = '<div class="book-list">' + books.map(renderListItem).join('') + '</div>';
            } else {
                container.innerHTML = renderTable();
            }
        }

        function renderGridCard(book) {
            const author = book.authors.join(', ') || 'Unknown Author';
            const rating = book.rating ? '&#9733;'.repeat(Math.round(book.rating)) : '';
            return '<div class="book-card" onclick="showBookDetails(' + book.id + ')">' +
                '<div class="book-cover">' +
                    (book.cover_path ?
                        '<img src="/api/books/' + book.id + '/cover" alt="" loading="lazy" onerror="this.parentElement.innerHTML=\\'<div class=book-cover-placeholder>&#128214;</div>\\'">' :
                        '<div class="book-cover-placeholder">&#128214;</div>') +
                    (book.favorite ? '<span class="book-favorite">&#11088;</span>' : '') +
                '</div>' +
                '<div class="book-info">' +
                    '<div class="book-title">' + escapeHtml(book.title) + '</div>' +
                    '<div class="book-author">' + escapeHtml(author) + '</div>' +
                    '<div class="book-meta">' +
                        book.files.map(f => '<span class="badge badge-format">' + f.format.toUpperCase() + '</span>').join('') +
                        (book.language ? '<span class="badge badge-language">' + book.language.toUpperCase() + '</span>' : '') +
                    '</div>' +
                    (rating ? '<div class="book-rating">' + rating + '</div>' : '') +
                '</div>' +
            '</div>';
        }

        function renderListItem(book) {
            const author = book.authors.join(', ') || 'Unknown Author';
            return '<div class="book-list-item" onclick="showBookDetails(' + book.id + ')">' +
                '<div class="book-list-cover">' +
                    (book.cover_path ? '<img src="/api/books/' + book.id + '/cover" alt="" loading="lazy">' : '') +
                '</div>' +
                '<div class="book-list-info">' +
                    '<div class="book-list-title">' + (book.favorite ? '&#11088; ' : '') + escapeHtml(book.title) + '</div>' +
                    '<div class="book-list-author">' + escapeHtml(author) + '</div>' +
                    '<div class="book-list-meta">' +
                        (book.publication_date ? '<span>&#128197; ' + book.publication_date + '</span>' : '') +
                        (book.language ? '<span>&#127760; ' + book.language.toUpperCase() + '</span>' : '') +
                        book.files.map(f => '<span>&#128196; ' + f.format.toUpperCase() + '</span>').join('') +
                        (book.rating ? '<span>&#11088; ' + book.rating + '</span>' : '') +
                    '</div>' +
                '</div>' +
            '</div>';
        }

        function renderTable() {
            return '<table class="book-table">' +
                '<thead><tr>' +
                    '<th>Title</th>' +
                    '<th>Author</th>' +
                    '<th>Year</th>' +
                    '<th>Format</th>' +
                    '<th>Rating</th>' +
                '</tr></thead>' +
                '<tbody>' +
                books.map(book => '<tr>' +
                    '<td><span class="table-title" onclick="showBookDetails(' + book.id + ')">' +
                        (book.favorite ? '&#11088; ' : '') + escapeHtml(book.title) + '</span></td>' +
                    '<td>' + escapeHtml(book.authors.join(', ') || '-') + '</td>' +
                    '<td>' + (book.publication_date ? book.publication_date.substring(0,4) : '-') + '</td>' +
                    '<td>' + book.files.map(f => f.format.toUpperCase()).join(', ') + '</td>' +
                    '<td>' + (book.rating ? '&#9733;'.repeat(Math.round(book.rating)) : '-') + '</td>' +
                '</tr>').join('') +
                '</tbody></table>';
        }

        function setView(view) {
            currentView = view;
            document.querySelectorAll('.header-actions .icon-btn').forEach(b => b.classList.remove('active'));
            document.getElementById('view-' + view).classList.add('active');
            renderBooks();
        }

        function setFilter(filter) {
            currentFilter = filter;
            currentPage = 1;
            updateNavItems();
            updateURL();
            loadBooks();
            if (window.innerWidth < 1024) toggleSidebar();
        }

        function updateNavItems() {
            document.querySelectorAll('.nav-item[data-filter]').forEach(item => {
                item.classList.toggle('active', item.dataset.filter === currentFilter);
            });
        }

        function updateNavCounts() {
            // Update counts from cached stats
            if (libraryStats) {
                document.getElementById('count-all').textContent = libraryStats.total_books;
                document.getElementById('count-favorites').textContent = libraryStats.favorites_count;
                document.getElementById('count-reading').textContent = libraryStats.reading_count;
                document.getElementById('count-completed').textContent = libraryStats.completed_count;
            }
        }

        function updateResultsInfo() {
            const info = document.getElementById('results-info');
            if (isSearching) {
                info.textContent = totalBooks + ' results found';
            } else {
                const start = (currentPage - 1) * booksPerPage + 1;
                const end = Math.min(currentPage * booksPerPage, totalBooks);
                info.textContent = 'Showing ' + start + '-' + end + ' of ' + totalBooks + ' books';
            }
        }

        function updatePagination() {
            const pagination = document.getElementById('pagination');
            const totalPages = Math.ceil(totalBooks / booksPerPage);

            if (totalPages <= 1) {
                pagination.innerHTML = '';
                return;
            }

            let html = '<button class="page-btn" onclick="goToPage(' + (currentPage - 1) + ')" ' +
                       (currentPage === 1 ? 'disabled' : '') + '>&#8592; Prev</button>';

            const start = Math.max(1, currentPage - 2);
            const end = Math.min(totalPages, currentPage + 2);

            if (start > 1) html += '<button class="page-btn" onclick="goToPage(1)">1</button>';
            if (start > 2) html += '<span class="page-info">...</span>';

            for (let i = start; i <= end; i++) {
                html += '<button class="page-btn' + (i === currentPage ? ' active' : '') + '" onclick="goToPage(' + i + ')">' + i + '</button>';
            }

            if (end < totalPages - 1) html += '<span class="page-info">...</span>';
            if (end < totalPages) html += '<button class="page-btn" onclick="goToPage(' + totalPages + ')">' + totalPages + '</button>';

            html += '<button class="page-btn" onclick="goToPage(' + (currentPage + 1) + ')" ' +
                    (currentPage === totalPages ? 'disabled' : '') + '>Next &#8594;</button>';

            pagination.innerHTML = html;
        }

        function goToPage(page) {
            const totalPages = Math.ceil(totalBooks / booksPerPage);
            if (page < 1 || page > totalPages) return;
            currentPage = page;
            updateURL();
            loadBooks();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }

        function applyFilters() {
            currentPage = 1;
            updateURL();
            loadBooks();
        }

        function clearFilters() {
            document.getElementById('sort-field').value = 'title';
            document.getElementById('sort-order').value = 'asc';
            document.getElementById('filter-language').value = '';
            document.getElementById('filter-format').value = '';
            document.getElementById('filter-rating').value = '';
            document.getElementById('search-input').value = '';
            currentFilter = 'all';
            isSearching = false;
            currentPage = 1;
            updateNavItems();
            updateURL();
            loadBooks();
        }

        async function showBookDetails(bookId) {
            try {
                const response = await fetch('/api/books/' + bookId);
                const book = await response.json();

                document.getElementById('details-title').textContent = book.title;

                let html = '';

                if (book.cover_path) {
                    html += '<div class="modal-cover"><img src="/api/books/' + book.id + '/cover" alt="" onerror="this.style.display=\\'none\\'"></div>';
                }

                if (book.files && book.files.length > 0) {
                    html += '<div class="detail-section"><div class="detail-label">Download</div><div class="detail-tags">' +
                        book.files.map(f =>
                            '<a href="/api/books/' + book.id + '/files/' + f.format.toLowerCase() + '" target="_blank" class="file-btn">' +
                            '&#128196; ' + f.format.toUpperCase() + ' <span style="opacity:0.7">(' + formatBytes(f.size_bytes) + ')</span></a>'
                        ).join('') + '</div></div>';
                }

                if (book.authors && book.authors.length > 0) {
                    html += '<div class="detail-section"><div class="detail-label">Authors</div><div class="detail-value">' + book.authors.join(', ') + '</div></div>';
                }

                if (book.subtitle) {
                    html += '<div class="detail-section"><div class="detail-label">Subtitle</div><div class="detail-value">' + escapeHtml(book.subtitle) + '</div></div>';
                }

                if (book.description) {
                    html += '<div class="detail-section"><div class="detail-label">Description</div><div class="detail-value">' + book.description + '</div></div>';
                }

                const meta = [];
                if (book.publisher) meta.push('Publisher: ' + book.publisher);
                if (book.publication_date) meta.push('Published: ' + book.publication_date);
                if (book.language) meta.push('Language: ' + book.language.toUpperCase());
                if (book.rating) meta.push('Rating: ' + '&#9733;'.repeat(Math.round(book.rating)) + ' (' + book.rating + '/5)');
                if (book.reading_status) meta.push('Status: ' + book.reading_status);

                if (meta.length > 0) {
                    html += '<div class="detail-section"><div class="detail-label">Details</div><div class="detail-value">' + meta.join(' &bull; ') + '</div></div>';
                }

                if (book.subjects && book.subjects.length > 0) {
                    html += '<div class="detail-section"><div class="detail-label">Subjects</div><div class="detail-tags">' +
                        book.subjects.map(s => '<span class="tag">' + escapeHtml(s) + '</span>').join('') + '</div></div>';
                }

                if (book.tags && book.tags.length > 0) {
                    html += '<div class="detail-section"><div class="detail-label">Tags</div><div class="detail-tags">' +
                        book.tags.map(t => '<span class="tag">' + escapeHtml(t) + '</span>').join('') + '</div></div>';
                }

                html += '<div style="margin-top: 24px;"><button class="btn btn-primary" onclick="closeModal(\\'details-modal\\'); editBook(' + book.id + ');">&#9998; Edit Metadata</button></div>';

                document.getElementById('details-body').innerHTML = html;
                document.getElementById('details-modal').classList.add('active');
            } catch (error) {
                showError('Failed to load book details: ' + error.message);
            }
        }

        async function editBook(bookId) {
            currentBookId = bookId;
            try {
                const response = await fetch('/api/books/' + bookId);
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
            const tags = document.getElementById('edit-tags').value.split(',').map(t => t.trim()).filter(t => t);

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
                const response = await fetch('/api/books/' + bookId, {
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
            if (!confirm('Are you sure you want to delete this book?')) return;
            const bookId = currentBookId;
            const deleteFiles = confirm('Also delete files from disk?');

            try {
                const response = await fetch('/api/books/' + bookId + '?delete_files=' + deleteFiles, { method: 'DELETE' });
                if (!response.ok) throw new Error('Failed to delete book');
                closeModal('edit-modal');
                showSuccess('Book deleted successfully');
                refreshBooks();
            } catch (error) {
                showError('Failed to delete book: ' + error.message);
            }
        }

        function showImportModal() {
            // Reset modal state
            document.getElementById('import-progress').style.display = 'none';
            document.getElementById('import-results').style.display = 'none';
            document.querySelectorAll('.tab-content').forEach(t => t.style.display = '');
            document.querySelectorAll('.tabs').forEach(t => t.style.display = '');
            switchImportTab('file');
            document.getElementById('import-modal').classList.add('active');
            if (window.innerWidth < 1024) toggleSidebar();
        }

        function switchImportTab(tabName) {
            // Update tab buttons
            document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tabs .tab[onclick*="${tabName}"]`).classList.add('active');

            // Update tab content
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('import-tab-' + tabName).classList.add('active');
        }

        function showImportProgress(text) {
            document.querySelectorAll('.tab-content').forEach(t => t.style.display = 'none');
            document.querySelectorAll('.tabs').forEach(t => t.style.display = 'none');
            document.getElementById('import-progress-text').textContent = text;
            document.getElementById('import-progress').style.display = 'block';
            document.getElementById('import-results').style.display = 'none';
        }

        function showImportResults(results, type) {
            document.getElementById('import-progress').style.display = 'none';
            const resultsDiv = document.getElementById('import-results');

            let html = '<div class="detail-section">';
            if (results.imported > 0) {
                html += `<div class="alert alert-success">Successfully imported ${results.imported} of ${results.total} books</div>`;
            }
            if (results.failed > 0) {
                html += `<div class="alert alert-error">${results.failed} books failed to import</div>`;
            }
            if (results.errors && results.errors.length > 0) {
                html += '<div class="detail-label">Errors</div>';
                html += '<ul style="color: var(--danger); font-size: 0.85rem; margin-left: 20px;">';
                results.errors.slice(0, 10).forEach(err => {
                    html += `<li>${escapeHtml(err)}</li>`;
                });
                if (results.errors.length > 10) {
                    html += `<li>...and ${results.errors.length - 10} more errors</li>`;
                }
                html += '</ul>';
            }
            html += '</div>';
            html += '<div class="btn-group">';
            html += '<button class="btn btn-primary" onclick="closeModal(&apos;import-modal&apos;); refreshBooks();">Done</button>';
            html += '</div>';

            resultsDiv.innerHTML = html;
            resultsDiv.style.display = 'block';
        }

        async function importSingleFile(event) {
            event.preventDefault();
            const fileInput = document.getElementById('import-file');
            const file = fileInput.files[0];
            if (!file) { showError('Please select a file'); return; }

            showImportProgress('Importing ' + file.name + '...');

            const formData = new FormData();
            formData.append('file', file);
            formData.append('extract_text', document.getElementById('import-extract-text').checked);
            formData.append('extract_cover', document.getElementById('import-extract-cover').checked);

            try {
                const response = await fetch('/api/books/import', { method: 'POST', body: formData });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Import failed');
                }
                showImportResults({ total: 1, imported: 1, failed: 0, errors: [] }, 'file');
                document.getElementById('import-form-file').reset();
            } catch (error) {
                showImportResults({ total: 1, imported: 0, failed: 1, errors: [error.message] }, 'file');
            }
        }

        async function importFolder(event) {
            event.preventDefault();
            const folderPath = document.getElementById('import-folder-path').value.trim();
            if (!folderPath) { showError('Please enter a folder path'); return; }

            showImportProgress('Scanning folder for ebooks...');

            const data = {
                folder_path: folderPath,
                recursive: document.getElementById('import-folder-recursive').checked,
                extensions: document.getElementById('import-folder-extensions').value.trim() || 'pdf,epub,mobi,azw3,txt',
                limit: document.getElementById('import-folder-limit').value || null,
                extract_text: document.getElementById('import-folder-extract-text').checked,
                extract_cover: document.getElementById('import-folder-extract-cover').checked
            };

            try {
                const response = await fetch('/api/books/import/folder', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Folder import failed');
                }
                const results = await response.json();
                showImportResults(results, 'folder');
                document.getElementById('import-form-folder').reset();
            } catch (error) {
                showImportResults({ total: 0, imported: 0, failed: 0, errors: [error.message] }, 'folder');
            }
        }

        async function importCalibre(event) {
            event.preventDefault();
            const calibrePath = document.getElementById('import-calibre-path').value.trim();
            if (!calibrePath) { showError('Please enter a Calibre library path'); return; }

            showImportProgress('Importing from Calibre library...');

            const data = {
                calibre_path: calibrePath,
                limit: document.getElementById('import-calibre-limit').value || null
            };

            try {
                const response = await fetch('/api/books/import/calibre', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Calibre import failed');
                }
                const results = await response.json();
                showImportResults(results, 'calibre');
                document.getElementById('import-form-calibre').reset();
            } catch (error) {
                showImportResults({ total: 0, imported: 0, failed: 0, errors: [error.message] }, 'calibre');
            }
        }

        async function importFromURL(event) {
            event.preventDefault();
            const url = document.getElementById('import-url').value.trim();
            if (!url) { showError('Please enter a URL'); return; }

            showImportProgress('Downloading and importing from URL...');

            const data = {
                url: url,
                extract_text: document.getElementById('import-url-extract-text').checked,
                extract_cover: document.getElementById('import-url-extract-cover').checked
            };

            try {
                const response = await fetch('/api/books/import/url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'URL import failed');
                }
                showImportResults({ total: 1, imported: 1, failed: 0, errors: [] }, 'url');
                document.getElementById('import-form-url').reset();
            } catch (error) {
                showImportResults({ total: 1, imported: 0, failed: 1, errors: [error.message] }, 'url');
            }
        }

        async function importFromOPDS(event) {
            event.preventDefault();
            const opdsUrl = document.getElementById('import-opds-url').value.trim();
            if (!opdsUrl) { showError('Please enter an OPDS catalog URL'); return; }

            showImportProgress('Fetching OPDS catalog...');

            const data = {
                opds_url: opdsUrl,
                limit: document.getElementById('import-opds-limit').value || null,
                extract_text: document.getElementById('import-opds-extract-text').checked,
                extract_cover: document.getElementById('import-opds-extract-cover').checked
            };

            try {
                const response = await fetch('/api/books/import/opds', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'OPDS import failed');
                }
                const results = await response.json();
                showImportResults(results, 'opds');
                document.getElementById('import-form-opds').reset();
            } catch (error) {
                showImportResults({ total: 0, imported: 0, failed: 0, errors: [error.message] }, 'opds');
            }
        }

        async function importFromISBN(event) {
            event.preventDefault();
            const isbn = document.getElementById('import-isbn').value.trim();
            if (!isbn) { showError('Please enter an ISBN'); return; }

            showImportProgress('Looking up ISBN...');

            const data = { isbn: isbn };

            try {
                const response = await fetch('/api/books/import/isbn', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'ISBN lookup failed');
                }
                showImportResults({ total: 1, imported: 1, failed: 0, errors: [] }, 'isbn');
                document.getElementById('import-form-isbn').reset();
            } catch (error) {
                showImportResults({ total: 1, imported: 0, failed: 1, errors: [error.message] }, 'isbn');
            }
        }

        function closeModal(modalId) {
            document.getElementById(modalId).classList.remove('active');
        }

        function closeAllModals() {
            document.querySelectorAll('.modal.active').forEach(m => m.classList.remove('active'));
        }

        function refreshBooks() {
            loadBooks();
            loadStats();
        }

        function showError(message) {
            const container = document.getElementById('message-container');
            container.innerHTML = '<div class="alert alert-error">&#9888; ' + escapeHtml(message) + '</div>';
            setTimeout(() => container.innerHTML = '', 5000);
        }

        function showSuccess(message) {
            const container = document.getElementById('message-container');
            container.innerHTML = '<div class="alert alert-success">&#9989; ' + escapeHtml(message) + '</div>';
            setTimeout(() => container.innerHTML = '', 3000);
        }

        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function formatBytes(bytes) {
            if (!bytes) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
        }
    </script>
</body>
</html>'''
