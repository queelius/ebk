# Quick Start Guide

This guide will help you get started with ebk in just a few minutes.

## 1. Initialize Configuration

First, set up your configuration:

```bash
# Create default configuration file
ebk config init

# View current configuration
ebk config show

# Set default library path (optional)
ebk config set library.default_path ~/my-ebooks
```

## 2. Create Your First Library

### Initialize a New Library

```bash
# Create new library
ebk init ~/my-ebooks
```

This creates a directory structure with:
- `library.db` - SQLite database
- `files/` - Ebook storage (hash-prefixed)
- `covers/` - Cover images and thumbnails

### From Calibre

If you have an existing Calibre library:

```bash
ebk import-calibre ~/Calibre/Library --output ~/my-ebooks
```

### From Raw eBooks

If you have a folder of PDF/EPUB files:

```bash
# Import single file
ebk import book.pdf ~/my-ebooks

# Import multiple files
ebk import ~/Downloads/*.pdf ~/my-ebooks

# Import directory
ebk import ~/Downloads/ebooks ~/my-ebooks --recursive
```

## 3. Basic Operations

### List Books

```bash
# List all books
ebk list ~/my-ebooks

# List with filters
ebk list ~/my-ebooks --author "Knuth" --language en
ebk list ~/my-ebooks --format pdf --rating 4

# Limit results
ebk list ~/my-ebooks --limit 20
```

### Search Books

```bash
# Full-text search (searches title, description, extracted text)
ebk search "Python programming" ~/my-ebooks

# Search specific fields
ebk search "machine learning" ~/my-ebooks --fields title,description

# Advanced filters
ebk search "algorithms" ~/my-ebooks --language en --author Knuth
```

### View Statistics

```bash
# Show library statistics
ebk stats ~/my-ebooks

# JSON output
ebk stats ~/my-ebooks --format json
```

## 4. Manage Reading Status

```bash
# Rate a book (0-5 stars)
ebk rate ~/my-ebooks <book-id> 5

# Mark as favorite
ebk favorite ~/my-ebooks <book-id>

# Add personal tags
ebk tag ~/my-ebooks <book-id> --add "must-read" "technical"

# Remove tags
ebk tag ~/my-ebooks <book-id> --remove "to-read"
```

## 5. Web Interface

Launch the web server to browse your library:

```bash
# Start server
ebk serve ~/my-ebooks

# Custom port
ebk serve ~/my-ebooks --port 8080

# Auto-open browser
ebk serve ~/my-ebooks --auto-open

# Configure defaults
ebk config set server.port 8000
ebk config set server.auto_open_browser true
```

Then open `http://localhost:8000` in your browser.

## 6. AI-Powered Features (Optional)

Enrich your library metadata using LLMs:

### Setup Ollama

```bash
# Install Ollama from https://ollama.com
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3.2
```

### Configure ebk

```bash
# Set up LLM provider
ebk config set llm.provider ollama
ebk config set llm.model llama3.2
ebk config set llm.host localhost
```

### Enrich Metadata

```bash
# Generate tags for all books
ebk enrich ~/my-ebooks --generate-tags

# Full enrichment
ebk enrich ~/my-ebooks \
  --generate-tags \
  --categorize \
  --enhance-descriptions

# Preview changes (dry run)
ebk enrich ~/my-ebooks --generate-tags --dry-run
```

## Using the Python API

```python
from pathlib import Path
from ebk.library_db import Library

# Open library
lib = Library.open(Path("~/my-ebooks"))

# Search for books
results = lib.search("Python programming")
for book in results:
    print(f"{book.title} by {', '.join([a.name for a in book.authors])}")

# Fluent query interface
results = (lib.query()
    .filter_by_language("en")
    .filter_by_author("Knuth")
    .order_by("title")
    .limit(10)
    .all())

# Update reading status
lib.update_reading_status(book_id=42, status="reading", rating=4)

# Add tags
lib.add_tags(book_id=42, tags=["must-read", "algorithms"])

# Get statistics
stats = lib.stats()
print(f"Total books: {stats['total_books']}")

# Always close
lib.close()
```

## Quick Reference Card

### Common Commands

```bash
# Initialize
ebk init ~/library

# Import
ebk import book.pdf ~/library
ebk import-calibre ~/Calibre ~/library

# Browse
ebk list ~/library
ebk search "query" ~/library
ebk stats ~/library

# Web interface
ebk serve ~/library

# AI enrichment
ebk enrich ~/library --generate-tags

# Configuration
ebk config show
ebk config set key value
```

### Library Structure

```
~/my-ebooks/
├── library.db           # SQLite database
├── files/               # Ebook files (hash-prefixed)
│   ├── ab/
│   │   └── abc123...pdf
│   └── cd/
│       └── cde456...epub
├── covers/              # Cover images
│   ├── ab/
│   │   └── abc123.jpg
│   └── thumbnails/
│       └── abc123_thumb.jpg
└── vectors/             # Vector embeddings (future)
```

## Next Steps

- [Configuration Guide](configuration.md) - Customize settings
- [LLM Features](../user-guide/llm-features.md) - AI-powered enrichment
- [Web Server](../user-guide/server.md) - Web interface details
- [CLI Reference](../user-guide/cli.md) - Complete command reference
- [Python API](../user-guide/api.md) - Programmatic access
- [Import/Export](../user-guide/import-export.md) - Data portability