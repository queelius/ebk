# Quick Start Guide

Get started with ebk in just a few minutes.

## 1. Create Your Library

```bash
# Initialize a new library
ebk init ~/my-library
```

This creates:
- `library.db` - SQLite database with FTS5 full-text search
- `files/` - Hash-prefixed ebook storage
- `covers/` - Cover images and thumbnails

## 2. Import Books

### Single File

```bash
ebk import add book.pdf ~/my-library
ebk import add ~/Downloads/book.epub ~/my-library
```

### Batch Import

```bash
# Import all ebooks from a folder
ebk import folder ~/Downloads/ebooks ~/my-library

# With specific extensions
ebk import folder ~/Downloads ~/my-library --extensions pdf,epub
```

### From Calibre

```bash
ebk import calibre ~/Calibre/Library ~/my-library
```

### From OPDS Feed

```bash
ebk import opds "https://example.com/opds/catalog.xml" ~/my-library
```

### By ISBN

```bash
ebk import isbn 978-0201633610 ~/my-library
```

## 3. Browse Your Library

### List Books

```bash
# List all books
ebk list ~/my-library

# With filters
ebk list ~/my-library --author "Knuth" --language en
ebk list ~/my-library --limit 20 --offset 40  # Page 3
```

### Search

```bash
# Full-text search
ebk search "machine learning" ~/my-library

# Field-specific search
ebk search "author:Knuth" ~/my-library
ebk search "title:Python language:en" ~/my-library
ebk search "rating:>=4 subject:Algorithms" ~/my-library
```

### View Details

```bash
ebk book info 42 ~/my-library
```

### Statistics

```bash
ebk stats ~/my-library
```

## 4. Organize with Tags

### Add Tags

```bash
# Hierarchical tags
ebk tag list ~/my-library
ebk tag tree ~/my-library

# Tag a book (use the shell for this)
ebk shell ~/my-library
ebk:/$ ln /books/42 /tags/Work/Projects
```

### Create Views

Views are named, composable library subsets:

```bash
# Create a view of favorite Python books
ebk view create python-favorites ~/my-library \
    --subject Python \
    --favorite

# List views
ebk view list ~/my-library

# Show books in a view
ebk view show python-favorites ~/my-library
```

## 5. Track Your Reading

```bash
# Rate a book (0-5 stars)
ebk book rate 42 ~/my-library --rating 5

# Mark as favorite
ebk book favorite 42 ~/my-library

# Set reading status
ebk book status 42 ~/my-library --set reading

# Track progress
ebk book progress 42 ~/my-library --set 45.5
```

## 6. Interactive Shell

Navigate your library like a Unix filesystem:

```bash
ebk shell ~/my-library

# Inside the shell:
ebk:/$ ls
authors/  books/  subjects/  tags/  similar/

ebk:/$ cd books/
ebk:/books$ ls | head 10

ebk:/books$ cd 42/
ebk:/books/42$ ls
.metadata  .files  .covers  .similar

ebk:/books/42$ cat .metadata
{title: "Introduction to Algorithms", ...}

ebk:/$ find author:Knuth rating:>=4
ebk:/$ find subject:Python | wc
```

## 7. Export Your Library

```bash
# JSON (complete metadata)
ebk export json ~/my-library ~/backup.json

# CSV
ebk export csv ~/my-library ~/catalog.csv

# Goodreads (for import into Goodreads)
ebk export goodreads ~/my-library ~/goodreads.csv

# Calibre (for import into Calibre)
ebk export calibre ~/my-library ~/calibre.csv

# HTML catalog
ebk export html ~/my-library ~/catalog.html

# OPDS feed (for e-reader apps)
ebk export opds ~/my-library ~/opds/catalog.xml
```

## 8. Web Interface

```bash
ebk serve ~/my-library
# Open http://localhost:8000
```

## 9. Configuration (Optional)

Set defaults to avoid repeating the library path:

```bash
# Initialize config file
ebk config init

# Set default library
ebk config set library.default_path ~/my-library

# Now these work without specifying path:
ebk list
ebk search "Python"
ebk stats
```

## Python API

```python
from pathlib import Path
from ebk.library_db import Library

lib = Library.open(Path("~/my-library"))

# Search
results = lib.search("Python programming")

# Fluent query
books = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_language("en")
    .order_by("title")
    .limit(10)
    .all())

# Personal metadata
from ebk.services import PersonalMetadataService
pm = PersonalMetadataService(lib.session)
pm.set_rating(42, 5.0)
pm.set_reading_status(42, "reading")

lib.close()
```

## Quick Reference

| Task | Command |
|------|---------|
| Create library | `ebk init ~/library` |
| Import file | `ebk import add book.pdf ~/library` |
| Import folder | `ebk import folder ~/books ~/library` |
| List books | `ebk list ~/library` |
| Search | `ebk search "query" ~/library` |
| Book info | `ebk book info 42 ~/library` |
| Rate book | `ebk book rate 42 ~/library --rating 5` |
| Set status | `ebk book status 42 ~/library --set reading` |
| Export | `ebk export json ~/library ~/out.json` |
| Web UI | `ebk serve ~/library` |
| Shell | `ebk shell ~/library` |

## Next Steps

- [Configuration](configuration.md) - Customize defaults
- [CLI Reference](../user-guide/cli.md) - Complete command documentation
- [Python API](../user-guide/api.md) - Programmatic access
- [Search Syntax](../user-guide/search.md) - Advanced queries
- [Import/Export](../user-guide/import-export.md) - Data formats
