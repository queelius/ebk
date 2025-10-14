# Import/Export

Guide to importing and exporting ebook libraries.

## Importing Books

### From Individual Files

```bash
# Import a single ebook
ebk import book.pdf ~/my-library

# Import multiple files with glob patterns
ebk import ~/books/*.epub ~/my-library

# Import with text extraction
ebk import book.pdf ~/my-library --extract-text
```

### From Calibre

```bash
# Import entire Calibre library
ebk import-calibre ~/Calibre/Library --output ~/my-library

# Import with filters
ebk import-calibre ~/Calibre/Library --output ~/my-library --language en
```

## Exporting Libraries

### HTML Export

Export your library as a self-contained HTML file with **pagination** and interactive features:

```bash
# Basic HTML export (50 books per page)
ebk export html ~/my-library ~/library.html

# Export for web deployment (copies files and covers)
ebk export html ~/my-library ~/site/library.html \
  --base-url /library \
  --copy

# Export with filters
ebk export html ~/my-library ~/library.html \
  --language en \
  --format pdf \
  --min-rating 4
```

**HTML Export Features:**

- **Pagination**: Automatically pages through books (50 per page)
- **URL State Tracking**: Bookmarkable pages with filters and page numbers in URL
- **Client-side Filtering**: Fast filtering by language, format, series, favorites, rating
- **Sorting**: Sort by title, author, rating, or date added
- **Search Bar**: Basic text search across titles, authors, and subjects
- **Responsive Design**: Works on desktop and mobile
- **Offline Capable**: Fully self-contained, no server required

**File Copying with `--copy`:**

The `--copy` flag copies both ebook files AND cover images to the output directory:

```bash
# Copies to: ~/site/library/ (based on --base-url)
ebk export html ~/my-library ~/site/library.html \
  --base-url /library \
  --copy
```

This creates:
```
~/site/
├── library.html           # HTML catalog
└── library/               # Copied files (based on --base-url)
    ├── files/            # Ebook files
    │   ├── ab/
    │   │   └── abc123.pdf
    │   └── cd/
    │       └── cde456.epub
    └── covers/           # Cover images
        ├── ab/
        │   └── abc123.jpg
        └── thumbnails/
            └── abc123_thumb.jpg
```

**Important**: HTML export uses **simple client-side filtering**, not advanced search syntax. For advanced search (field-specific queries, boolean logic), use:

- CLI: `ebk search "title:Python rating:>=4"`
- Web server: `ebk serve ~/my-library`
- Python API: `lib.search("title:Python rating:>=4")`

### JSON Export

```bash
# Export metadata to JSON
ebk export json ~/my-library ~/metadata.json

# Pretty-printed JSON
ebk export json ~/my-library ~/metadata.json --indent 2
```

### CSV Export

```bash
# Export to CSV format
ebk export csv ~/my-library ~/books.csv

# Export with specific columns
ebk export csv ~/my-library ~/books.csv --columns title,author,isbn
```

### ZIP Archive

```bash
# Create backup archive
ebk export zip ~/my-library ~/backup.zip

# Include covers in archive
ebk export zip ~/my-library ~/backup.zip --include-covers
```

## Import/Export Use Cases

### Backup and Migration

```bash
# Full backup
ebk export zip ~/my-library ~/backup-$(date +%Y%m%d).zip

# Restore to new location
ebk init ~/new-library
ebk import ~/backup.zip ~/new-library
```

### Web Deployment

```bash
# Export for Hugo static site
ebk export html ~/my-library ~/hugo/static/library.html \
  --base-url /library \
  --copy \
  --language en \
  --has-files

# Deploy to web server
rsync -av ~/hugo/ user@server:/var/www/site/
```

### Library Sharing

```bash
# Export filtered subset
ebk export html ~/my-library ~/shared.html \
  --subject "Computer Science" \
  --format pdf \
  --min-rating 4

# Share the single HTML file (no server needed)
```

### Data Analysis

```bash
# Export to JSON for analysis
ebk export json ~/my-library ~/data.json

# Use with jq, pandas, or other tools
cat ~/data.json | jq '.books[] | select(.rating >= 4) | .title'
```

## See Also

- [CLI Reference](cli.md) - Full import/export command options
- [Search & Query](search.md) - Filtering books before export
- [Server](server.md) - Web server for dynamic browsing
