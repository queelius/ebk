"""
ECHO format exporter for ebk e-book library.

Exports library in an ECHO-compliant directory structure with:
- README.md explaining the archive
- library.db (SQLite database copy)
- books.jsonl (one book per line)
- covers/ directory with cover images
- by-author/ directory with markdown indexes
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


def export_echo(
    library_path: Path,
    output_dir: Path,
    db_path: Optional[Path] = None,
    entries: Optional[List[Dict[str, Any]]] = None,
    owner_name: str = "Unknown"
) -> Dict[str, Any]:
    """
    Export library to ECHO-compliant directory structure.

    Args:
        library_path: Source library path
        output_dir: Output directory
        db_path: Path to SQLite database (optional, for copy)
        entries: List of book entries (if not provided, reads from library)
        owner_name: Name of archive owner for README

    Returns:
        Summary dict with export statistics
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load entries if not provided
    if entries is None:
        metadata_path = library_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)
        else:
            entries = []

    # Copy database
    db_included = False
    if db_path and db_path.exists():
        shutil.copy2(db_path, output_path / "library.db")
        db_included = True

    # Export JSONL
    jsonl_path = output_path / "books.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for entry in entries:
            record = {
                "id": entry.get("id"),
                "title": entry.get("title", "Unknown"),
                "creators": entry.get("creators", []),
                "language": entry.get("language"),
                "publisher": entry.get("publisher"),
                "published_date": entry.get("published_date"),
                "isbn": entry.get("isbn"),
                "subjects": entry.get("subjects", []),
                "description": entry.get("description"),
                "file_paths": entry.get("file_paths", []),
                "file_formats": entry.get("file_formats", []),
                "cover_path": entry.get("cover_path"),
                "added_at": entry.get("added_at"),
                "status": entry.get("status"),
                "rating": entry.get("rating"),
                "favorite": entry.get("favorite"),
                "tags": entry.get("tags", []),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Copy covers
    covers_dir = output_path / "covers"
    covers_dir.mkdir(exist_ok=True)
    covers_copied = 0

    for entry in entries:
        cover_path = entry.get("cover_path")
        if cover_path:
            src_cover = library_path / cover_path
            if src_cover.exists():
                # Use entry ID as filename
                entry_id = entry.get("id", "unknown")
                suffix = src_cover.suffix or ".jpg"
                dest_cover = covers_dir / f"{entry_id}{suffix}"
                shutil.copy2(src_cover, dest_cover)
                covers_copied += 1

    # Create by-author index
    by_author_dir = output_path / "by-author"
    by_author_dir.mkdir(exist_ok=True)

    author_books = {}
    for entry in entries:
        creators = entry.get("creators", [])
        if not creators:
            creators = ["Unknown"]
        for author in creators:
            if author not in author_books:
                author_books[author] = []
            author_books[author].append(entry)

    for author, books in sorted(author_books.items()):
        # Create safe filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in author)
        safe_name = safe_name[:100].strip()
        if not safe_name:
            safe_name = "unknown"

        md_path = by_author_dir / f"{safe_name}.md"

        lines = [f"# {author}", "", f"Books by {author} ({len(books)} total)", ""]

        for book in sorted(books, key=lambda x: x.get("title", "")):
            title = book.get("title", "Unknown")
            year = ""
            pub_date = book.get("published_date")
            if pub_date:
                year = f" ({pub_date[:4]})" if len(pub_date) >= 4 else ""

            lines.append(f"## {title}{year}")
            lines.append("")

            if book.get("description"):
                desc = book["description"]
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                lines.append(desc)
                lines.append("")

            formats = book.get("file_formats", [])
            if formats:
                lines.append(f"Formats: {', '.join(formats)}")
                lines.append("")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # Generate README
    readme_content = _generate_echo_readme(
        owner_name=owner_name,
        total_books=len(entries),
        total_authors=len(author_books),
        covers_included=covers_copied,
        db_included=db_included
    )
    (output_path / "README.md").write_text(readme_content, encoding="utf-8")

    return {
        "total_exported": len(entries),
        "covers_copied": covers_copied,
        "authors": len(author_books),
        "db_included": db_included,
        "output_dir": str(output_path)
    }


def _generate_echo_readme(
    owner_name: str,
    total_books: int,
    total_authors: int,
    covers_included: int,
    db_included: bool
) -> str:
    """Generate ECHO-compliant README for ebook archive."""
    db_section = ""
    if db_included:
        db_section = """
### SQLite Database

The `library.db` file is a copy of the source database.

Key tables:
- `books`: id, title, language, publisher, published_date, isbn, ...
- `authors`: id, name
- `book_authors`: book_id, author_id (many-to-many)
- `subjects`: id, name
- `book_subjects`: book_id, subject_id

Query examples:
```sql
-- List all books
sqlite3 library.db "SELECT title, published_date FROM books ORDER BY title"

-- Books by author
sqlite3 library.db "SELECT b.title FROM books b
  JOIN book_authors ba ON b.id = ba.book_id
  JOIN authors a ON ba.author_id = a.id
  WHERE a.name LIKE '%Tolkien%'"
```
"""

    return f"""# E-Book Library Archive

{owner_name}'s e-book collection.

Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
Total books: {total_books}
Total authors: {total_authors}
Covers included: {covers_included}

## Format

This is an ECHO-compliant archive. All data is in durable, open formats.

### Directory Structure

```
├── README.md            # This file
├── books.jsonl          # One book per line
{"├── library.db          # SQLite database" if db_included else ""}
├── covers/              # Cover images
│   └── {{id}}.jpg
└── by-author/           # Markdown index by author
    ├── author-name.md
    └── ...
```

### books.jsonl

Each line is a JSON object:

```json
{{"id": "...", "title": "...", "creators": ["..."], "subjects": [...], ...}}
```

Fields:
- `id`: Unique identifier
- `title`: Book title
- `creators`: Array of author names
- `language`: ISO language code
- `publisher`: Publisher name
- `published_date`: Publication date
- `isbn`: ISBN (if available)
- `subjects`: Array of subject/genre tags
- `description`: Book description
- `file_paths`: Relative paths to ebook files
- `file_formats`: Array of formats (epub, pdf, etc.)
- `cover_path`: Relative path to cover image
- `status`: Reading status (read, reading, to-read)
- `rating`: User rating (1-5)
- `favorite`: Boolean
- `tags`: User tags
{db_section}
### covers/ Directory

Cover images named by book ID. Original format preserved.

### by-author/ Directory

Markdown files for each author listing their books.

## Exploring

1. **Browse authors**: Look in `by-author/` directory
2. **Search**: `grep -l "search term" by-author/*.md`
3. **Parse**: Process `books.jsonl` with any JSON tool
4. **Query**: Use SQLite browser on `library.db` (if included)
5. **View covers**: Browse `covers/` directory

## About ECHO

ECHO is a philosophy for durable personal data archives.
Learn more: https://github.com/alextowell/longecho

---

*Generated by ebk (E-Book Library Manager)*
"""
