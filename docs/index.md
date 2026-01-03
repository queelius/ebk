# ebk - eBook Library Manager

**ebk** is a personal ebook library manager designed for readers who want full control over their digital book collection. Unlike cloud-based services, ebk stores everything locally in a SQLite database, giving you complete ownership of your library metadata, reading history, and organizational structure.

## Why ebk?

- **Local-first**: Your library lives on your machine. No accounts, no cloud sync, no vendor lock-in.
- **Programmable**: A fluent Python API makes automation and scripting natural.
- **Unix-inspired**: An interactive shell with VFS navigation, piping, and familiar commands.
- **Extensible**: Views DSL, hierarchical tags, and export formats for any workflow.

## Core Features

### Library Management

- **SQLite + FTS5 Backend** - Fast full-text search across titles, authors, descriptions, and extracted text
- **Hash-based Deduplication** - Same file = skipped; same book, different format = added
- **Automatic Metadata Extraction** - From EPUBs, PDFs, and Calibre libraries
- **Cover Extraction** - Automatic thumbnail generation

### Organization

- **Hierarchical Tags** - Nest tags like `Work/Projects/2024` for flexible organization
- **Views** - Named, composable library subsets with their own metadata overrides
- **Personal Metadata** - Ratings (0-5 stars), favorites, reading status, progress tracking
- **Reading Queue** - Prioritized list of books to read next

### Interactive Shell

Navigate your library like a filesystem:

```bash
ebk shell ~/library
ebk:/$ cd books/
ebk:/books$ ls | grep Python | head 5
ebk:/books$ cd 42/.metadata
ebk:/books/42/.metadata$ cat
ebk:/$ find author:Knuth rating:>=4
```

### Import & Export

**Import from:**
- Individual ebook files (EPUB, PDF, MOBI, etc.)
- Calibre libraries
- OPDS catalog feeds
- URLs (direct download)
- ISBN lookup (Google Books, Open Library)

**Export to:**
- JSON, CSV (generic)
- Goodreads CSV (for import into Goodreads)
- Calibre CSV (for import into Calibre)
- HTML (self-contained catalog with pagination)
- OPDS (for e-reader apps)

### Book Operations

- **Merge** - Combine duplicate entries, preserving all metadata and files
- **Bulk Edit** - Update multiple books at once (language, tags, rating, etc.)
- **Similar Books** - Find related books using TF-IDF and metadata similarity

### AI-Powered Features (Optional)

Connect to Ollama for LLM-powered metadata enrichment:

- Auto-generate tags and categories
- Enhance descriptions
- Assess reading difficulty

## Quick Example

```python
from pathlib import Path
from ebk.library_db import Library

lib = Library.open(Path("~/ebooks"))

# Fluent query builder
python_books = (lib.query()
    .filter_by_subject("Python")
    .filter_by_language("en")
    .filter_by_rating(4.0)
    .order_by("title")
    .limit(20)
    .all())

# Full-text search
results = lib.search("machine learning algorithms")

# Personal metadata
from ebk.services import PersonalMetadataService
pm = PersonalMetadataService(lib.session)
pm.set_rating(book_id=42, rating=5.0)
pm.set_reading_status(book_id=42, status="reading")

lib.close()
```

## CLI Overview

```bash
# Library management
ebk init ~/library              # Create new library
ebk import add book.pdf         # Import single file
ebk import calibre ~/Calibre    # Import from Calibre
ebk search "python programming" # Full-text search
ebk list --author Knuth         # Filter and list

# Personal tracking
ebk book rate 42 --rating 5
ebk book status 42 --set reading
ebk book favorite 42

# Organization
ebk tag list
ebk view create favorites --favorite
ebk view show favorites

# Export
ebk export goodreads ~/library ~/goodreads.csv
ebk export html ~/library ~/catalog.html

# Interactive shell
ebk shell ~/library

# Web interface
ebk serve ~/library
```

## Getting Started

1. **[Installation](getting-started/installation.md)** - Install ebk and optional features
2. **[Quick Start](getting-started/quickstart.md)** - Create your first library
3. **[Configuration](getting-started/configuration.md)** - Customize defaults

## Documentation

- **[CLI Reference](user-guide/cli.md)** - Complete command documentation
- **[Python API](user-guide/api.md)** - Programmatic library access
- **[Search Syntax](user-guide/search.md)** - Advanced query language
- **[Import/Export](user-guide/import-export.md)** - Data interchange
- **[LLM Features](user-guide/llm-features.md)** - AI-powered enrichment

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     CLI (Typer + Rich)                  │
├─────────────────────────────────────────────────────────┤
│  Interactive Shell (REPL)  │  Web Server (FastAPI)      │
├─────────────────────────────────────────────────────────┤
│                    Services Layer                       │
│  ImportService │ ExportService │ PersonalMetadataService│
├─────────────────────────────────────────────────────────┤
│                    Core Library                         │
│  Library │ QueryBuilder │ ViewService │ Similarity      │
├─────────────────────────────────────────────────────────┤
│                SQLAlchemy ORM + SQLite + FTS5           │
│  Book │ Author │ Subject │ Tag │ File │ Cover │ etc.   │
└─────────────────────────────────────────────────────────┘
```

## Support

- [GitHub Issues](https://github.com/queelius/ebk/issues) - Bug reports and feature requests
- [GitHub Discussions](https://github.com/queelius/ebk/discussions) - Questions and ideas
- [Contact](mailto:lex@metafunctor.com) - Direct inquiries
