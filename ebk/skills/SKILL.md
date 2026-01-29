---
name: ebk
description: Use this skill when working with ebk - an eBook metadata management CLI with SQLite storage, full-text search, hierarchical tags, and a virtual filesystem shell. Invoke for library management, book operations, imports/exports, or ebk shell navigation.
---

# ebk - eBook Metadata Management

A CLI tool for managing ebook libraries with SQLite storage, full-text search, and a virtual filesystem shell.

## Quick Reference

```bash
# Library management
ebk lib init ~/my-library
ebk lib migrate
ebk lib backup -o backup.tar.gz
ebk lib check

# Query and discovery
ebk query search "python programming"
ebk query list --author "Knuth"
ebk query stats
ebk query sql "SELECT title FROM books WHERE language='en'"

# Import books
ebk import add book.pdf
ebk import folder ~/Downloads/books/
ebk import calibre ~/Calibre\ Library/
ebk import isbn 978-0134685991

# Export library
ebk export json -o library.json
ebk export csv -o library.csv
ebk export opds -o catalog.xml --copy-files
ebk export goodreads -o goodreads.csv
ebk export calibre -o calibre.csv

# Book operations
ebk book info 42
ebk book read 42 --text
ebk book rate 42 --rating 5
ebk book tag 42 --add "Work/Project-2024"
ebk book purge ~/library --no-files --execute

# Interactive
ebk shell                    # VFS shell
ebk serve                    # Web server
```

## Command Groups

| Command | Purpose |
|---------|---------|
| `ebk lib` | Library management (init, migrate, backup, restore, check) |
| `ebk query` | Query and discovery (search, list, stats, sql) |
| `ebk import` | Import books (add, folder, calibre, isbn, opds, url) |
| `ebk export` | Export library (json, csv, html, opds, goodreads, calibre) |
| `ebk book` | Book operations (info, read, rate, favorite, tag, purge, merge) |
| `ebk note` | Manage annotations (add, list, extract, export) |
| `ebk tag` | Manage hierarchical tags (list, tree, add, remove, rename) |
| `ebk queue` | Reading queue (list, add, remove, move, next) |
| `ebk view` | Named library subsets (create, list, show, delete, edit) |
| `ebk skill` | Claude Code skill management |

## Search Syntax

ebk supports advanced query syntax:

```bash
# Field-specific search
ebk query search "title:Python author:Knuth"

# Boolean operators
ebk query search "python AND programming"
ebk query search "python OR ruby"
ebk query search "NOT java"

# Exact phrases
ebk query search '"machine learning"'

# Comparisons
ebk query search "rating:>=4"
ebk query search "pages:>500"
```

## VFS Shell

`ebk shell` provides filesystem-like navigation:

```
/                          # Root
/books/{id}/              # Book by ID
/books/{id}/title         # Title as text
/books/{id}/authors       # Authors list
/books/{id}/metadata      # Full JSON metadata
/books/{id}/files/        # Ebook files
/books/{id}/similar/      # Similar books
/authors/{name}/          # Browse by author
/subjects/{subject}/      # Browse by subject
/tags/{hierarchy}/        # Hierarchical tags
```

Shell commands: `ls`, `cd`, `cat`, `find`, `grep`, `ln`, `mv`, `rm`, `mkdir`

Supports piping: `ls /books/ | grep Python | head 10`

## Python API

```python
from ebk.library_db import Library

# Open library
lib = Library.open("~/my-library")

# Fluent query API
results = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_language("en")
    .order_by("title")
    .limit(20)
    .all())

# Search
books = lib.search("python programming", limit=10)

# Get book
book = lib.get_book(42)
print(book.title, book.authors)

lib.close()
```

## Configuration

Config file: `~/.config/ebk/config.json`

```bash
ebk config --library-path ~/my-library    # Set default library
ebk config --llm-provider ollama          # Set LLM provider
ebk config --show                         # Show current config
```

## Database Schema

Core tables: `books`, `authors`, `subjects`, `files`, `covers`, `tags`, `personal_metadata`, `annotations`, `books_fts` (FTS5)

Library directory structure:
```
library/
├── library.db          # SQLite database
├── files/              # Hash-prefixed ebook storage
└── covers/
    └── thumbnails/     # Cover images
```

## Views DSL

Views are named, composable library subsets:

```yaml
name: unread-python
description: Unread Python books
filter:
  reading_status: unread
  subjects:
    any: ["Python", "Programming"]
sort: added desc
limit: 50
```

```bash
ebk view create unread-python --filter "reading_status:unread" --filter "subject:Python"
ebk query list --view unread-python
```

## Tips

1. Use `ebk config --library-path` to set a default library
2. `ebk shell` for interactive exploration
3. `ebk query sql` for complex custom queries
4. `ebk export opds` for Android reader compatibility
5. Tags are hierarchical: `Work/Project-2024/Research`
