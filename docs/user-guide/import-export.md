# Import/Export

Complete guide to importing books and exporting library data.

## Importing Books

### From Individual Files

```bash
# Import a single ebook
ebk import add book.pdf ~/my-library
ebk import add ~/Downloads/book.epub ~/my-library

# Import with specific metadata
ebk import add book.pdf ~/my-library \
    --title "My Book" \
    --author "John Doe"
```

### Batch Import from Folder

```bash
# Import all ebooks from a folder
ebk import folder ~/Downloads/ebooks ~/my-library

# With specific extensions only
ebk import folder ~/Downloads ~/my-library --extensions pdf,epub,mobi

# Recursive (include subfolders)
ebk import folder ~/ebooks ~/my-library --recursive

# Resume interrupted import (skip already imported)
ebk import folder ~/ebooks ~/my-library --resume
```

### From Calibre Library

```bash
# Import entire Calibre library
ebk import calibre ~/Calibre/Library ~/my-library

# Limit import
ebk import calibre ~/Calibre/Library ~/my-library --limit 100
```

### From OPDS Catalog

Import from OPDS feeds (Gutenberg, Standard Ebooks, etc.):

```bash
# Import from OPDS feed
ebk import opds "https://standardebooks.org/opds" ~/my-library

# With limit
ebk import opds "https://example.com/opds/catalog.xml" ~/my-library --limit 50
```

### From URL

```bash
# Download and import from URL
ebk import url "https://example.com/book.pdf" ~/my-library
```

### By ISBN

Create a book entry by looking up ISBN from Google Books or Open Library:

```bash
# Lookup by ISBN
ebk import isbn 978-0201633610 ~/my-library

# With specific provider
ebk import isbn 978-0201633610 ~/my-library --provider google
ebk import isbn 978-0201633610 ~/my-library --provider openlibrary
```

## Exporting Library Data

### JSON Export

Complete metadata export in JSON format:

```bash
# Export all books
ebk export json ~/my-library ~/backup.json

# Pretty-printed
ebk export json ~/my-library ~/backup.json --pretty

# Export specific view
ebk export json ~/my-library ~/favorites.json --view favorites
```

### CSV Export

Spreadsheet-compatible format:

```bash
# Basic CSV export
ebk export csv ~/my-library ~/catalog.csv

# Export specific view
ebk export csv ~/my-library ~/python-books.csv --view python
```

### Goodreads Export

Export in Goodreads-compatible format for import into your Goodreads account:

```bash
ebk export goodreads ~/my-library ~/goodreads.csv
ebk export goodreads ~/my-library ~/favorites.csv --view favorites
```

The Goodreads CSV includes:
- Title, Author, Additional Authors
- ISBN/ISBN13
- My Rating (1-5 stars)
- Exclusive Shelf (read, currently-reading, to-read)
- Bookshelves (from tags)
- Date Read, Date Added
- Page count, Publisher, Year

Import at: https://www.goodreads.com/review/import

### Calibre Export

Export in Calibre-compatible format:

```bash
ebk export calibre ~/my-library ~/calibre.csv
ebk export calibre ~/my-library ~/subset.csv --view programming
```

The Calibre CSV includes:
- title, authors, author_sort
- publisher, pubdate
- languages, rating (0-10 scale)
- tags, series, series_index
- identifiers (ISBN, ASIN, etc.)
- comments/description

### HTML Export

Self-contained HTML catalog with pagination and client-side filtering:

```bash
# Basic export
ebk export html ~/my-library ~/catalog.html

# With file and cover copying for static hosting
ebk export html ~/my-library ~/site/catalog.html \
    --base-url /library \
    --copy-files \
    --copy-covers

# Export a specific view
ebk export html ~/my-library ~/favorites.html --view favorites

# With filters
ebk export html ~/my-library ~/english.html \
    --language en \
    --has-files
```

HTML export features:
- **Pagination**: 50 books per page
- **URL State**: Bookmarkable page/filter state
- **Client-side Filtering**: By language, format, series, favorites, rating
- **Sorting**: By title, author, rating, date
- **Search Bar**: Text search across metadata
- **Responsive**: Desktop and mobile support
- **Offline**: No server required

### OPDS Export

Create an OPDS catalog feed for e-reader apps (Foliate, KOReader, Moon+ Reader):

```bash
# Basic OPDS catalog
ebk export opds ~/my-library ~/opds/catalog.xml

# With file and cover copying
ebk export opds ~/my-library ~/opds/catalog.xml \
    --base-url https://example.com/opds \
    --copy-files \
    --copy-covers

# Export a view
ebk export opds ~/my-library ~/opds/favorites.xml --view favorites
```

## Backup and Restore

### Create Backup

```bash
# Database backup (tar.gz)
ebk backup ~/my-library ~/backups/
```

### Restore from Backup

```bash
# Restore to new location
ebk restore ~/backups/library-2024-01-01.tar.gz ~/restored-library

# Force overwrite existing
ebk restore ~/backups/backup.tar.gz ~/my-library --force
```

## Use Cases

### Migrating from Calibre

```bash
# 1. Import from Calibre
ebk import calibre ~/Calibre/Library ~/my-library

# 2. Verify import
ebk stats ~/my-library

# 3. Export to compare
ebk export json ~/my-library ~/imported.json
```

### Syncing with Goodreads

```bash
# Export your ebk ratings and status
ebk export goodreads ~/my-library ~/sync.csv

# Import at goodreads.com/review/import
```

### Publishing a Web Catalog

```bash
# 1. Create a view of books to share
ebk view create public ~/my-library \
    --has-files \
    --min-rating 3

# 2. Export for web hosting
ebk export html ~/my-library ~/public/catalog.html \
    --view public \
    --base-url /books \
    --copy-files \
    --copy-covers

# 3. Deploy
rsync -av ~/public/ user@server:/var/www/books/
```

### Creating an OPDS Server

```bash
# 1. Export OPDS catalog
ebk export opds ~/my-library ~/opds/catalog.xml \
    --base-url https://myserver.com/opds \
    --copy-files \
    --copy-covers

# 2. Serve with any static file server
cd ~/opds && python -m http.server 8080
```

### Data Analysis

```bash
# Export to JSON for analysis
ebk export json ~/my-library ~/data.json --pretty

# Query with jq
jq '.[] | select(.rating >= 4) | .title' ~/data.json

# Load into Python/pandas
python -c "
import json
import pandas as pd
with open('data.json') as f:
    books = json.load(f)
df = pd.DataFrame(books)
print(df.groupby('language').size())
"
```

## Python API

```python
from pathlib import Path
from ebk.library_db import Library
from ebk.services import ExportService

lib = Library.open(Path("~/my-library"))
export_svc = ExportService(lib.session, lib.library_path)

# Get books (all or filtered)
books = lib.get_all_books()
# or
books = lib.query().filter_by_language("en").all()

# Export to different formats
json_str = export_svc.export_json(books, pretty=True)
csv_str = export_svc.export_csv(books)
goodreads_csv = export_svc.export_goodreads_csv(books)
calibre_csv = export_svc.export_calibre_csv(books)

# Write to files
with open("backup.json", "w") as f:
    f.write(json_str)

lib.close()
```

## See Also

- [CLI Reference](cli.md) - Complete command options
- [Views](library-management.md#views) - Create named subsets for export
- [Search Syntax](search.md) - Filter before exporting
