"""
OPDS Catalog Export.

Exports the library to a static OPDS (Atom) catalog file that can be
served from any static file host or used for backup/sharing.

OPDS Spec: https://specs.opds.io/opds-1.2
"""

from datetime import datetime
from pathlib import Path
from typing import Optional, List
import shutil


# MIME types
OPDS_ACQUISITION_MIME = "application/atom+xml;profile=opds-catalog;kind=acquisition"

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


def build_entry(book, base_url: str, files_dir: str = "files", covers_dir: str = "covers") -> str:
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

    # Cover image (using static file path)
    cover_link = ""
    if book.covers:
        cover = book.covers[0]
        if cover.path:
            cover_filename = f"{book_id}.jpg"
            cover_url = f"{base_url}/{covers_dir}/{cover_filename}" if base_url else f"{covers_dir}/{cover_filename}"
            cover_link = f'<link rel="http://opds-spec.org/image/thumbnail" href="{cover_url}" type="image/jpeg"/>'
            cover_link += f'\n    <link rel="http://opds-spec.org/image" href="{cover_url}" type="image/jpeg"/>'

    # Acquisition links (download links for each format)
    acquisition_links = ""
    if book.files:
        for file in book.files:
            mime = get_mime_type(file.format)
            size_bytes = file.size_bytes or 0
            size_kb = size_bytes // 1024 if size_bytes else 0
            # Use hash-based filename for static export
            file_ext = file.format.lower()
            file_url = f"{base_url}/{files_dir}/{file.file_hash[:8]}_{book_id}.{file_ext}" if base_url else f"{files_dir}/{file.file_hash[:8]}_{book_id}.{file_ext}"
            acquisition_links += f"""
    <link rel="http://opds-spec.org/acquisition"
          href="{file_url}"
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
  </entry>"""


def build_feed(
    title: str,
    entries: str,
    base_url: str = "",
    subtitle: str = "",
    author_name: str = "ebk Library",
) -> str:
    """Build an OPDS Atom feed."""
    updated = format_datetime()
    feed_id = f"urn:ebk:catalog:{updated.replace(':', '-')}"

    subtitle_xml = f"<subtitle>{escape_xml(subtitle)}</subtitle>" if subtitle else ""
    base_url_escaped = escape_xml(base_url) if base_url else ""

    # Self link
    self_link = f'<link rel="self" href="{base_url_escaped}/catalog.xml" type="{OPDS_ACQUISITION_MIME}"/>' if base_url else ""
    start_link = f'<link rel="start" href="{base_url_escaped}/catalog.xml" type="{OPDS_ACQUISITION_MIME}"/>' if base_url else ""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:dc="http://purl.org/dc/terms/"
      xmlns:opds="http://opds-spec.org/2010/catalog">
  <id>{feed_id}</id>
  <title>{escape_xml(title)}</title>
  {subtitle_xml}
  <updated>{updated}</updated>
  <author>
    <name>{escape_xml(author_name)}</name>
  </author>
  {self_link}
  {start_link}
{entries}
</feed>"""


def export_to_opds(
    books: List,
    output_path: Path,
    library_path: Path,
    title: str = "ebk Library",
    subtitle: str = "",
    base_url: str = "",
    copy_files: bool = False,
    copy_covers: bool = False,
) -> dict:
    """
    Export library to an OPDS catalog file.

    Args:
        books: List of Book objects to export
        output_path: Path to output XML file
        library_path: Path to the library (for copying files)
        title: Feed title
        subtitle: Feed subtitle
        base_url: Base URL for file links (e.g., "https://example.com/library")
        copy_files: If True, copy ebook files to output directory
        copy_covers: If True, copy cover images to output directory

    Returns:
        Dict with export statistics
    """
    output_path = Path(output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    files_dir = output_dir / "files"
    covers_dir = output_dir / "covers"

    stats = {
        "books": len(books),
        "files_copied": 0,
        "covers_copied": 0,
        "errors": []
    }

    if copy_files:
        files_dir.mkdir(exist_ok=True)

    if copy_covers:
        covers_dir.mkdir(exist_ok=True)

    # Build entries
    entries = []
    for book in books:
        # Copy files if requested
        if copy_files and book.files:
            for file in book.files:
                try:
                    src_path = library_path / file.path
                    if src_path.exists():
                        file_ext = file.format.lower()
                        dst_filename = f"{file.file_hash[:8]}_{book.id}.{file_ext}"
                        dst_path = files_dir / dst_filename
                        if not dst_path.exists():
                            shutil.copy2(src_path, dst_path)
                            stats["files_copied"] += 1
                except Exception as e:
                    stats["errors"].append(f"Failed to copy file for book {book.id}: {e}")

        # Copy covers if requested
        if copy_covers and book.covers:
            try:
                cover = book.covers[0]
                if cover.path:
                    src_path = library_path / cover.path
                    if src_path.exists():
                        dst_filename = f"{book.id}.jpg"
                        dst_path = covers_dir / dst_filename
                        if not dst_path.exists():
                            shutil.copy2(src_path, dst_path)
                            stats["covers_copied"] += 1
            except Exception as e:
                stats["errors"].append(f"Failed to copy cover for book {book.id}: {e}")

        # Build entry
        entries.append(build_entry(book, base_url, "files", "covers"))

    # Build feed
    feed = build_feed(
        title=title,
        entries="".join(entries),
        base_url=base_url,
        subtitle=subtitle,
    )

    # Write output
    output_path.write_text(feed, encoding="utf-8")

    return stats
