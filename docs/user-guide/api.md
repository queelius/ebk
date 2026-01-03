# Python API

Comprehensive guide to ebk's Python API for programmatic library management.

## Overview

ebk provides a SQLAlchemy-based API for managing ebook libraries. The API features:

- **Fluent Query Builder** for chainable, readable queries
- **SQLAlchemy ORM Models** (Book, Author, Subject, File, Cover, Tag)
- **Full-text Search** via SQLite FTS5
- **Services Layer** for metadata, import/export, and text extraction

## Quick Start

```python
from pathlib import Path
from ebk.library_db import Library

# Open or create a library
lib = Library.open(Path("~/my-library"))

# Add a book
book = lib.add_book(
    Path("book.epub"),
    metadata={
        "title": "Python Programming",
        "creators": ["John Doe"],
        "subjects": ["Programming", "Python"],
        "language": "en"
    }
)

# Search for books
results = lib.search("python")

# Use fluent query builder
python_books = (lib.query()
    .filter_by_subject("Python")
    .filter_by_language("en")
    .order_by("title")
    .limit(10)
    .all())

# Get statistics
stats = lib.stats()
print(f"Total books: {stats['total_books']}")

# Always close when done
lib.close()
```

## Core Classes

### Library

The main entry point for all library operations.

```python
from ebk.library_db import Library

# Open existing or create new library
lib = Library.open(Path("/path/to/library"))

# Basic operations
book = lib.get_book(book_id)           # Get by ID
books = lib.get_all_books()            # Get all books
results = lib.search("query string")   # Full-text search
stats = lib.stats()                    # Library statistics

# Adding books
book = lib.add_book(
    file_path=Path("book.pdf"),
    metadata={
        "title": "My Book",
        "creators": ["Author Name"],
        "subjects": ["Topic"],
        "language": "en",
        "publisher": "Publisher Name",
        "publication_date": "2024",
        "description": "Book description...",
        "series": "Series Name",
        "series_index": "1"
    },
    extract_text=True,   # Extract text for full-text search
    extract_cover=True   # Extract cover image
)

# Import from Calibre
book = lib.add_calibre_book(Path("/calibre/book/metadata.opf"))

# Batch import
books = lib.batch_import([
    (Path("book1.pdf"), {"title": "Book 1", "creators": ["Author"]}),
    (Path("book2.epub"), {"title": "Book 2", "creators": ["Author"]}),
])

# Close when done
lib.close()
```

### QueryBuilder

Fluent interface for building complex queries.

```python
# Start a query
query = lib.query()

# Filter methods (chainable)
query = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_subject("Algorithms")
    .filter_by_language("en")
    .filter_by_format("pdf")
    .filter_by_rating(4.0)         # Minimum rating
    .filter_by_favorite(True)
    .filter_by_status("reading")
    .filter_by_tag("Work/Projects")
    .filter_by_series("TAOCP"))

# Ordering
query = query.order_by("title")              # Ascending
query = query.order_by("created_at", desc=True)  # Descending

# Pagination
query = query.limit(20).offset(40)  # Page 3 of 20 results

# Execute query
books = query.all()           # Get all matching books
book = query.first()          # Get first match or None
count = query.count()         # Count matches
exists = query.exists()       # Check if any match
```

### ORM Models

SQLAlchemy models for database entities.

#### Book

```python
from ebk.db.models import Book

book = lib.get_book(1)

# Scalar fields
book.id              # int
book.unique_id       # str (UUID)
book.title           # str
book.subtitle        # Optional[str]
book.language        # Optional[str]
book.publisher       # Optional[str]
book.publication_date # Optional[str]
book.description     # Optional[str]
book.series          # Optional[str]
book.series_index    # Optional[float]
book.page_count      # Optional[int]
book.created_at      # datetime
book.updated_at      # datetime

# Relationships
book.authors         # List[Author]
book.subjects        # List[Subject]
book.files           # List[File]
book.covers          # List[Cover]
book.tags            # List[Tag]
book.identifiers     # List[Identifier]
book.personal        # Optional[PersonalMetadata]
book.annotations     # List[Annotation]
```

#### Author

```python
author.id      # int
author.name    # str
author.books   # List[Book]
```

#### Subject

```python
subject.id     # int
subject.name   # str
subject.books  # List[Book]
```

#### Tag

Hierarchical user-defined tags.

```python
tag.id         # int
tag.name       # str (leaf name)
tag.path       # str (e.g., "Work/Projects")
tag.full_path  # str (complete path)
tag.parent_id  # Optional[int]
tag.children   # List[Tag]
tag.books      # List[Book]
```

#### File

```python
file.id         # int
file.path       # str (relative to library)
file.format     # str (pdf, epub, etc.)
file.size_bytes # int
file.file_hash  # str (SHA256)
file.book_id    # int
```

#### PersonalMetadata

User-specific reading data.

```python
pm = book.personal

pm.rating           # Optional[float] (0-5)
pm.favorite         # bool
pm.reading_status   # str (unread, reading, read, abandoned)
pm.reading_progress # Optional[float] (0-100)
pm.date_started     # Optional[datetime]
pm.date_finished    # Optional[datetime]
pm.personal_tags    # Optional[List[str]]
pm.queue_position   # Optional[int]
```

## Services

### PersonalMetadataService

Manage reading status, ratings, and favorites.

```python
from ebk.services import PersonalMetadataService

pm_svc = PersonalMetadataService(lib.session)

# Ratings
pm_svc.set_rating(book_id, 4.5)
rating = pm_svc.get_rating(book_id)

# Favorites
pm_svc.set_favorite(book_id, True)
favorites = pm_svc.get_favorites()

# Reading status
pm_svc.set_reading_status(book_id, "reading")
pm_svc.set_reading_progress(book_id, 45.0)
currently_reading = pm_svc.get_by_status("reading")
```

### ExportService

Export library data in various formats.

```python
from ebk.services import ExportService

export_svc = ExportService(lib.session, lib.library_path)

# JSON export
json_str = export_svc.export_json(books, pretty=True)

# CSV export
csv_str = export_svc.export_csv(books)

# Goodreads CSV (for import into Goodreads)
goodreads_csv = export_svc.export_goodreads_csv(books)

# Calibre CSV
calibre_csv = export_svc.export_calibre_csv(books)

# HTML catalog
export_svc.export_html(books, Path("catalog.html"))

# OPDS catalog
export_svc.export_opds(books, Path("catalog.xml"))
```

### ViewService

Manage named views (saved queries).

```python
from ebk.views import ViewService

view_svc = ViewService(lib.session)

# Create a view
view_svc.create(
    name="favorites",
    definition={"favorite": True},
    description="All favorite books"
)

# List views
views = view_svc.list()

# Evaluate a view (get matching books)
books = view_svc.evaluate("favorites")

# Delete a view
view_svc.delete("favorites")
```

## Search

### Simple Search

```python
# Search across title, authors, subjects, description
results = lib.search("python programming")

# Returns list of Book objects
for book in results:
    print(f"{book.title} by {', '.join(a.name for a in book.authors)}")
```

### Advanced Search Syntax

The search parser supports field-specific queries:

```python
# Field-specific search
results = lib.search("title:Python")
results = lib.search("author:Knuth")
results = lib.search("subject:Algorithms")
results = lib.search("language:en")

# Comparisons
results = lib.search("rating:>=4")
results = lib.search("year:2020")

# Boolean operators
results = lib.search("Python AND Django")
results = lib.search("Python OR Ruby")
results = lib.search("Python NOT beginner")

# Phrases
results = lib.search('"machine learning"')

# Combined
results = lib.search('author:Knuth subject:Algorithms rating:>=4')
```

## Book Operations

### Merging Duplicate Books

```python
# Merge books 2 and 3 into book 1
merged_book, deleted_ids = lib.merge_books(
    primary_id=1,
    secondary_ids=[2, 3],
    delete_secondary_files=False  # Keep duplicate files
)
```

### Finding Similar Books

```python
from ebk.similarity import find_similar_books

similar = find_similar_books(
    lib.session,
    book_id=1,
    limit=10,
    mode="hybrid"  # or "text", "metadata"
)

for book, score in similar:
    print(f"{book.title}: {score:.2f}")
```

## Real-World Examples

### Building a Reading Dashboard

```python
from ebk.library_db import Library
from ebk.services import PersonalMetadataService

lib = Library.open(Path("~/library"))
pm_svc = PersonalMetadataService(lib.session)

# Get reading statistics
currently_reading = pm_svc.get_by_status("reading")
completed_this_year = lib.query().filter_by_status("read").all()
favorites = pm_svc.get_favorites()

print(f"Currently reading: {len(currently_reading)} books")
print(f"Completed: {len(completed_this_year)} books")
print(f"Favorites: {len(favorites)} books")

lib.close()
```

### Batch Tagging

```python
# Add tag to all Python books
python_books = lib.query().filter_by_subject("Python").all()

for book in python_books:
    lib.add_tag_to_book(book.id, "Programming/Python")

lib.session.commit()
```

### Export for Backup

```python
from ebk.services import ExportService

lib = Library.open(Path("~/library"))
export_svc = ExportService(lib.session, lib.library_path)

# Export all books to JSON
all_books = lib.get_all_books()
json_backup = export_svc.export_json(all_books, pretty=True)

with open("library_backup.json", "w") as f:
    f.write(json_backup)

lib.close()
```

## Best Practices

1. **Always close the library** when done to release database connections
2. **Use context managers** where possible for automatic cleanup
3. **Commit changes** after modifications: `lib.session.commit()`
4. **Use QueryBuilder** for complex queries instead of raw SQL
5. **Handle missing fields** gracefully (many fields are Optional)

## Further Reading

- [CLI Reference](cli.md) - Command-line interface
- [LLM Features](llm-features.md) - AI-powered metadata enrichment
- [Search & Query](search.md) - Advanced search syntax
- [Import/Export](import-export.md) - Data interchange formats
