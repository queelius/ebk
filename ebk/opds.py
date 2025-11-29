"""
OPDS (Open Publication Distribution System) catalog server.

Provides an OPDS 1.2 compatible catalog feed for e-reader apps like:
- Foliate (Linux)
- KOReader
- Moon+ Reader (Android)
- Marvin (iOS)
- Thorium Reader

OPDS Spec: https://specs.opds.io/opds-1.2
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote, urlencode
import mimetypes

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response, FileResponse

from .library_db import Library
from .db.models import Book


router = APIRouter(prefix="/opds", tags=["OPDS"])

# MIME types
OPDS_MIME = "application/atom+xml;profile=opds-catalog;kind=navigation"
OPDS_ACQUISITION_MIME = "application/atom+xml;profile=opds-catalog;kind=acquisition"
OPENSEARCH_MIME = "application/opensearchdescription+xml"

# File format MIME types
FORMAT_MIMES = {
    "pdf": "application/pdf",
    "epub": "application/epub+zip",
    "mobi": "application/x-mobipocket-ebook",
    "azw": "application/vnd.amazon.ebook",
    "azw3": "application/vnd.amazon.ebook",
    "txt": "text/plain",
    "html": "text/html",
    "htm": "text/html",
    "djvu": "image/vnd.djvu",
    "cbz": "application/vnd.comicbook+zip",
    "cbr": "application/vnd.comicbook-rar",
}


def get_mime_type(format: str) -> str:
    """Get MIME type for ebook format."""
    return FORMAT_MIMES.get(format.lower(), "application/octet-stream")


def escape_xml(text: str) -> str:
    """Escape XML special characters."""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))


def format_datetime(dt: Optional[datetime] = None) -> str:
    """Format datetime for Atom feed."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_entry(book: Book, base_url: str) -> str:
    """Build an OPDS entry for a book."""
    book_id = book.id
    title = escape_xml(book.title or "Untitled")

    # Authors
    authors_xml = ""
    if book.authors:
        for author in book.authors:
            authors_xml += f"""
    <author>
      <name>{escape_xml(author.name)}</name>
    </author>"""

    # Summary/description
    summary = ""
    if book.description:
        summary = f"<summary>{escape_xml(book.description[:500])}</summary>"

    # Categories (subjects)
    categories = ""
    if book.subjects:
        for subj in book.subjects:
            categories += f'<category term="{escape_xml(subj.name)}" label="{escape_xml(subj.name)}"/>'

    # Language
    language = f"<dc:language>{escape_xml(book.language)}</dc:language>" if book.language else ""

    # Publisher
    publisher = f"<dc:publisher>{escape_xml(book.publisher)}</dc:publisher>" if book.publisher else ""

    # Publication date
    pub_date = ""
    if book.publication_date:
        pub_date = f"<dc:date>{escape_xml(str(book.publication_date))}</dc:date>"

    # Cover image
    cover_link = ""
    if book.covers:
        cover = book.covers[0]
        if cover.path:
            # Use full cover for both (thumbnails generated on-the-fly if needed)
            cover_link = f'<link rel="http://opds-spec.org/image/thumbnail" href="{base_url}/opds/cover/{book_id}" type="image/jpeg"/>'
            cover_link += f'\n    <link rel="http://opds-spec.org/image" href="{base_url}/opds/cover/{book_id}" type="image/jpeg"/>'

    # Acquisition links (download links for each format)
    acquisition_links = ""
    if book.files:
        for file in book.files:
            mime = get_mime_type(file.format)
            size_bytes = file.size_bytes or 0
            size_kb = size_bytes // 1024 if size_bytes else 0
            acquisition_links += f"""
    <link rel="http://opds-spec.org/acquisition"
          href="{base_url}/opds/download/{book_id}/{file.format}"
          type="{mime}"
          length="{size_bytes}"
          title="{file.format.upper()} ({size_kb} KB)"/>"""

    # Updated timestamp
    updated = format_datetime(book.updated_at if hasattr(book, 'updated_at') else None)

    return f"""
  <entry>
    <id>urn:ebk:book:{book_id}</id>
    <title>{title}</title>
    <updated>{updated}</updated>{authors_xml}
    {summary}
    {categories}
    {language}
    {publisher}
    {pub_date}
    {cover_link}
    {acquisition_links}
    <link rel="alternate" href="{base_url}/opds/book/{book_id}" type="{OPDS_ACQUISITION_MIME}"/>
  </entry>"""


def build_feed(
    id: str,
    title: str,
    entries: str,
    base_url: str,
    links: str = "",
    subtitle: str = "",
    total_results: Optional[int] = None,
    start_index: int = 1,
    items_per_page: int = 50,
) -> str:
    """Build an OPDS Atom feed."""
    updated = format_datetime()

    # Pagination info for OpenSearch
    pagination = ""
    if total_results is not None:
        pagination = f"""
  <opensearch:totalResults>{total_results}</opensearch:totalResults>
  <opensearch:startIndex>{start_index}</opensearch:startIndex>
  <opensearch:itemsPerPage>{items_per_page}</opensearch:itemsPerPage>"""

    subtitle_xml = f"<subtitle>{escape_xml(subtitle)}</subtitle>" if subtitle else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:dc="http://purl.org/dc/terms/"
      xmlns:opds="http://opds-spec.org/2010/catalog"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <id>{id}</id>
  <title>{escape_xml(title)}</title>
  {subtitle_xml}
  <updated>{updated}</updated>
  <icon>{base_url}/favicon.ico</icon>

  <link rel="self" href="{base_url}/opds" type="{OPDS_MIME}"/>
  <link rel="start" href="{base_url}/opds" type="{OPDS_MIME}"/>
  <link rel="search" href="{base_url}/opds/opensearch.xml" type="{OPENSEARCH_MIME}"/>
  {links}
  {pagination}
  {entries}
</feed>"""


# Global library reference (set by server.py)
_library: Optional[Library] = None


def set_library(lib: Library):
    """Set the library instance for OPDS routes."""
    global _library
    _library = lib


def get_library() -> Library:
    """Get the current library instance."""
    if _library is None:
        raise HTTPException(status_code=500, detail="Library not initialized")
    return _library


def get_base_url(request: Request) -> str:
    """Get base URL from request."""
    return str(request.base_url).rstrip("/")


@router.get("/", response_class=Response)
async def opds_root(request: Request):
    """
    OPDS root catalog - navigation feed with links to browse the library.
    """
    base_url = get_base_url(request)
    lib = get_library()
    stats = lib.stats()

    entries = f"""
  <entry>
    <id>urn:ebk:all</id>
    <title>All Books</title>
    <content type="text">Browse all {stats['total_books']} books in the library</content>
    <link rel="subsection" href="{base_url}/opds/all" type="{OPDS_ACQUISITION_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>

  <entry>
    <id>urn:ebk:recent</id>
    <title>Recently Added</title>
    <content type="text">Most recently added books</content>
    <link rel="subsection" href="{base_url}/opds/recent" type="{OPDS_ACQUISITION_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>

  <entry>
    <id>urn:ebk:authors</id>
    <title>By Author</title>
    <content type="text">Browse {stats['total_authors']} authors</content>
    <link rel="subsection" href="{base_url}/opds/authors" type="{OPDS_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>

  <entry>
    <id>urn:ebk:subjects</id>
    <title>By Subject</title>
    <content type="text">Browse {stats['total_subjects']} subjects</content>
    <link rel="subsection" href="{base_url}/opds/subjects" type="{OPDS_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>

  <entry>
    <id>urn:ebk:languages</id>
    <title>By Language</title>
    <content type="text">Browse by language</content>
    <link rel="subsection" href="{base_url}/opds/languages" type="{OPDS_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>"""

    feed = build_feed(
        id="urn:ebk:root",
        title="ebk Library",
        subtitle=f"{stats['total_books']} books",
        entries=entries,
        base_url=base_url,
    )

    return Response(content=feed, media_type=OPDS_MIME)


@router.get("/opensearch.xml", response_class=Response)
async def opensearch_description(request: Request):
    """OpenSearch description document for search integration."""
    base_url = get_base_url(request)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
  <ShortName>ebk Library</ShortName>
  <Description>Search the ebk ebook library</Description>
  <Url type="{OPDS_ACQUISITION_MIME}"
       template="{base_url}/opds/search?q={{searchTerms}}&amp;page={{startPage?}}&amp;limit={{count?}}"/>
  <InputEncoding>UTF-8</InputEncoding>
  <OutputEncoding>UTF-8</OutputEncoding>
</OpenSearchDescription>"""

    return Response(content=xml, media_type=OPENSEARCH_MIME)


@router.get("/all", response_class=Response)
async def opds_all_books(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """All books - acquisition feed with pagination."""
    base_url = get_base_url(request)
    lib = get_library()

    offset = (page - 1) * limit
    total = lib.query().count()
    books = lib.query().order_by('title').limit(limit).offset(offset).all()

    entries = "".join(build_entry(book, base_url) for book in books)

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/all?page={page-1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'
    if offset + len(books) < total:
        links += f'<link rel="next" href="{base_url}/opds/all?page={page+1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'

    feed = build_feed(
        id="urn:ebk:all",
        title="All Books",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/recent", response_class=Response)
async def opds_recent(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
):
    """Recently added books."""
    base_url = get_base_url(request)
    lib = get_library()

    books = lib.query().order_by('created_at', desc=True).limit(limit).all()
    entries = "".join(build_entry(book, base_url) for book in books)

    feed = build_feed(
        id="urn:ebk:recent",
        title="Recently Added",
        entries=entries,
        base_url=base_url,
        total_results=len(books),
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/search", response_class=Response)
async def opds_search(
    request: Request,
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Search books - returns acquisition feed."""
    base_url = get_base_url(request)
    lib = get_library()

    offset = (page - 1) * limit
    books = lib.search(q, limit=limit, offset=offset)

    entries = "".join(build_entry(book, base_url) for book in books)

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/search?q={quote(q)}&amp;page={page-1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'
    if len(books) == limit:  # Might be more
        links += f'<link rel="next" href="{base_url}/opds/search?q={quote(q)}&amp;page={page+1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'

    feed = build_feed(
        id=f"urn:ebk:search:{quote(q)}",
        title=f"Search: {q}",
        entries=entries,
        base_url=base_url,
        links=links,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/authors", response_class=Response)
async def opds_authors(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """List all authors - navigation feed."""
    base_url = get_base_url(request)
    lib = get_library()

    from .db.models import Author
    offset = (page - 1) * limit

    authors = lib.session.query(Author).order_by(Author.sort_name).offset(offset).limit(limit).all()
    total = lib.session.query(Author).count()

    entries = ""
    for author in authors:
        book_count = len(author.books)
        entries += f"""
  <entry>
    <id>urn:ebk:author:{author.id}</id>
    <title>{escape_xml(author.name)}</title>
    <content type="text">{book_count} books</content>
    <link rel="subsection" href="{base_url}/opds/author/{author.id}" type="{OPDS_ACQUISITION_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>"""

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/authors?page={page-1}&amp;limit={limit}" type="{OPDS_MIME}"/>'
    if offset + len(authors) < total:
        links += f'<link rel="next" href="{base_url}/opds/authors?page={page+1}&amp;limit={limit}" type="{OPDS_MIME}"/>'

    feed = build_feed(
        id="urn:ebk:authors",
        title="Authors",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_MIME)


@router.get("/author/{author_id}", response_class=Response)
async def opds_author_books(
    request: Request,
    author_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Books by a specific author."""
    base_url = get_base_url(request)
    lib = get_library()

    from .db.models import Author
    author = lib.session.query(Author).filter(Author.id == author_id).first()

    if not author:
        raise HTTPException(status_code=404, detail="Author not found")

    offset = (page - 1) * limit
    books = author.books[offset:offset + limit]
    total = len(author.books)

    entries = "".join(build_entry(book, base_url) for book in books)

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/author/{author_id}?page={page-1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'
    if offset + len(books) < total:
        links += f'<link rel="next" href="{base_url}/opds/author/{author_id}?page={page+1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'

    feed = build_feed(
        id=f"urn:ebk:author:{author_id}",
        title=f"Books by {author.name}",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/subjects", response_class=Response)
async def opds_subjects(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """List all subjects - navigation feed."""
    base_url = get_base_url(request)
    lib = get_library()

    from .db.models import Subject
    offset = (page - 1) * limit

    subjects = lib.session.query(Subject).order_by(Subject.name).offset(offset).limit(limit).all()
    total = lib.session.query(Subject).count()

    entries = ""
    for subject in subjects:
        book_count = len(subject.books)
        entries += f"""
  <entry>
    <id>urn:ebk:subject:{subject.id}</id>
    <title>{escape_xml(subject.name)}</title>
    <content type="text">{book_count} books</content>
    <link rel="subsection" href="{base_url}/opds/subject/{subject.id}" type="{OPDS_ACQUISITION_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>"""

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/subjects?page={page-1}&amp;limit={limit}" type="{OPDS_MIME}"/>'
    if offset + len(subjects) < total:
        links += f'<link rel="next" href="{base_url}/opds/subjects?page={page+1}&amp;limit={limit}" type="{OPDS_MIME}"/>'

    feed = build_feed(
        id="urn:ebk:subjects",
        title="Subjects",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_MIME)


@router.get("/subject/{subject_id}", response_class=Response)
async def opds_subject_books(
    request: Request,
    subject_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Books in a specific subject."""
    base_url = get_base_url(request)
    lib = get_library()

    from .db.models import Subject
    subject = lib.session.query(Subject).filter(Subject.id == subject_id).first()

    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    offset = (page - 1) * limit
    books = subject.books[offset:offset + limit]
    total = len(subject.books)

    entries = "".join(build_entry(book, base_url) for book in books)

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/subject/{subject_id}?page={page-1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'
    if offset + len(books) < total:
        links += f'<link rel="next" href="{base_url}/opds/subject/{subject_id}?page={page+1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'

    feed = build_feed(
        id=f"urn:ebk:subject:{subject_id}",
        title=f"Subject: {subject.name}",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/languages", response_class=Response)
async def opds_languages(request: Request):
    """List all languages - navigation feed."""
    base_url = get_base_url(request)
    lib = get_library()

    from .db.models import Book
    from sqlalchemy import func

    # Get languages with book counts
    languages = (lib.session.query(Book.language, func.count(Book.id))
                 .filter(Book.language.isnot(None))
                 .group_by(Book.language)
                 .order_by(func.count(Book.id).desc())
                 .all())

    entries = ""
    for lang, count in languages:
        entries += f"""
  <entry>
    <id>urn:ebk:language:{lang}</id>
    <title>{escape_xml(lang)}</title>
    <content type="text">{count} books</content>
    <link rel="subsection" href="{base_url}/opds/language/{quote(lang)}" type="{OPDS_ACQUISITION_MIME}"/>
    <updated>{format_datetime()}</updated>
  </entry>"""

    feed = build_feed(
        id="urn:ebk:languages",
        title="Languages",
        entries=entries,
        base_url=base_url,
        total_results=len(languages),
    )

    return Response(content=feed, media_type=OPDS_MIME)


@router.get("/language/{lang}", response_class=Response)
async def opds_language_books(
    request: Request,
    lang: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    """Books in a specific language."""
    base_url = get_base_url(request)
    lib = get_library()

    offset = (page - 1) * limit
    total = lib.query().filter_by_language(lang).count()
    books = lib.query().filter_by_language(lang).order_by('title').limit(limit).offset(offset).all()

    entries = "".join(build_entry(book, base_url) for book in books)

    # Pagination links
    links = ""
    if page > 1:
        links += f'<link rel="previous" href="{base_url}/opds/language/{quote(lang)}?page={page-1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'
    if offset + len(books) < total:
        links += f'<link rel="next" href="{base_url}/opds/language/{quote(lang)}?page={page+1}&amp;limit={limit}" type="{OPDS_ACQUISITION_MIME}"/>'

    feed = build_feed(
        id=f"urn:ebk:language:{lang}",
        title=f"Language: {lang}",
        entries=entries,
        base_url=base_url,
        links=links,
        total_results=total,
        start_index=offset + 1,
        items_per_page=limit,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/book/{book_id}", response_class=Response)
async def opds_book_detail(request: Request, book_id: int):
    """Single book detail - acquisition feed."""
    base_url = get_base_url(request)
    lib = get_library()

    book = lib.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    entry = build_entry(book, base_url)

    feed = build_feed(
        id=f"urn:ebk:book:{book_id}",
        title=book.title or "Untitled",
        entries=entry,
        base_url=base_url,
    )

    return Response(content=feed, media_type=OPDS_ACQUISITION_MIME)


@router.get("/download/{book_id}/{format}")
async def opds_download(book_id: int, format: str):
    """Download a book file."""
    lib = get_library()

    book = lib.get_book(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Find file with requested format
    file = None
    for f in book.files:
        if f.format.lower() == format.lower():
            file = f
            break

    if not file:
        raise HTTPException(status_code=404, detail=f"Format {format} not found for this book")

    # Resolve relative path against library directory
    file_path = lib.library_path / file.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Generate filename
    safe_title = "".join(c for c in (book.title or "book") if c.isalnum() or c in " -_")[:50]
    filename = f"{safe_title}.{format}"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=get_mime_type(format),
    )


@router.get("/cover/{book_id}")
async def opds_cover(book_id: int):
    """Get book cover image."""
    lib = get_library()

    book = lib.get_book(book_id)
    if not book or not book.covers:
        raise HTTPException(status_code=404, detail="Cover not found")

    cover = book.covers[0]
    if not cover.path:
        raise HTTPException(status_code=404, detail="Cover path not set")

    # Resolve relative path against library directory
    cover_path = lib.library_path / cover.path

    if not cover_path.exists():
        raise HTTPException(status_code=404, detail="Cover file not found")

    # Determine media type from extension
    suffix = cover_path.suffix.lower()
    media_type = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }.get(suffix, 'image/jpeg')

    return FileResponse(path=cover_path, media_type=media_type)


@router.get("/cover/{book_id}/thumbnail")
async def opds_cover_thumbnail(book_id: int):
    """Get book cover thumbnail (falls back to full cover)."""
    # Just return the full cover for now
    # TODO: Generate actual thumbnails if needed
    return await opds_cover(book_id)
