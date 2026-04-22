# book-memex

> Renamed from `ebk` (previous name). The `ebk` CLI entrypoint is still available
> as a deprecation shim and will be removed in the release after v1.

**book-memex** is a powerful eBook metadata management tool with a SQLAlchemy + SQLite database backend. It provides a comprehensive fluent API for programmatic use, a rich Typer-based CLI (with colorized output courtesy of [Rich](https://github.com/Textualize/rich)), full-text search with FTS5 indexing, automatic text extraction and chunking for semantic search, hash-based file deduplication, and optional AI-powered features including knowledge graphs and semantic search.


---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
  - [Database Commands](#database-commands)
  - [Web Server](#web-server)
  - [AI-Powered Features](#ai-powered-features)
  - [Configuration Management](#configuration-management)
  - [Legacy Commands](#legacy-commands)
- [Python API](#python-api)
- [Integrations](#integrations)
- [Architecture](#architecture)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Documentation](#documentation)
- [Stay Updated](#stay-updated)
- [Support](#support)

---

## Features

- **SQLAlchemy + SQLite Backend**: Robust database with normalized schema, proper relationships, and FTS5 full-text search
- **Fluent Python API**: Comprehensive programmatic interface with method chaining and query builders
- **Typer + Rich CLI**: A colorized, easy-to-use command-line interface
- **Automatic Text Extraction**: Extract and index text from PDFs, EPUBs, and plaintext files
  - PyMuPDF (primary) with pypdf fallback for PDFs
  - ebooklib with HTML parsing for EPUBs
  - Automatic chunking (500-word overlapping chunks) for semantic search
- **Hash-based Deduplication**: SHA256-based file deduplication
  - Same file (same hash) = skipped
  - Same book, different format = added as additional format
  - Hash-prefixed directory storage for scalability
- **Advanced Search**: Powerful search with field-specific queries and boolean logic
  - Field searches: `title:Python`, `author:Knuth`, `tag:programming`
  - Boolean operators: `AND` (implicit), `OR`, `NOT`/`-prefix`
  - Comparison filters: `rating:>=4`, `rating:3-5`
  - Exact filters: `language:en`, `format:pdf`, `favorite:true`
  - Phrase searches: `"machine learning"`
  - Fast FTS5-powered full-text search across titles, descriptions, and extracted text
- **Import from Multiple Sources**:
  - Calibre libraries (reads metadata.opf files)
  - Individual ebook files with auto-metadata extraction
  - Batch import with progress tracking
- **Cover Extraction**: Automatic cover extraction and thumbnail generation
  - PDFs: First page rendered as image
  - EPUBs: Cover from metadata or naming patterns
- **Web Server Interface**:
  - FastAPI-based REST API for library management
  - URL-based navigation with filters, pagination, and sorting
  - Clickable covers and file formats to open books
  - Book details modal with comprehensive metadata display
- **Flexible Exports**:
  - **HTML Export**: Self-contained interactive catalog with pagination (50 books/page)
    - Client-side search and filtering
    - URL state tracking for bookmarkable pages
    - Optional file copying with `--copy` flag (includes covers)
  - Export to ZIP archives
  - Hugo-compatible Markdown with multiple organization options
  - Jinja2 template support for customizable export formats
- **Integrations** (optional):
  - **Streamlit Dashboard**: Interactive web interface
  - **MCP Server**: AI assistant integration
  - **Visualizations**: Network graphs for analysis

---

## Installation

### Basic Installation

```bash
pip install book-memex
```

### From Source

```bash
git clone https://github.com/queelius/ebk.git
cd ebk
pip install .
```

### With Optional Features

```bash
# With Streamlit dashboard
pip install book-memex[streamlit]

# With visualization tools
pip install book-memex[viz]

# With all optional features
pip install book-memex[all]

# For development
pip install book-memex[dev]
```

> **Note**: Requires Python 3.10+

---

## Quick Start

### 1. Initialize Configuration

```bash
# Create default configuration file at ~/.config/ebk/config.json
book-memex config init

# View current configuration
book-memex config show

# Set default library path
book-memex config set library.default_path ~/my-library
```

### 2. Create and Populate Library

```bash
# Initialize a new library
book-memex init ~/my-library

# Import a single ebook with auto-metadata extraction
book-memex import book.pdf ~/my-library

# Import from Calibre library
book-memex import-calibre ~/Calibre/Library --output ~/my-library

# Search using full-text search
book-memex search "python programming" ~/my-library

# List books with filtering
book-memex list ~/my-library --author "Knuth" --limit 20

# Get statistics
book-memex stats ~/my-library
```

### 3. Launch Web Interface

```bash
# Start web server (uses config defaults)
book-memex serve ~/my-library

# Custom port and host
book-memex serve ~/my-library --port 8080 --host 127.0.0.1

# Auto-open browser
book-memex config set server.auto_open_browser true
book-memex serve ~/my-library
```

---

## Configuration

book-memex uses a centralized configuration system stored at `~/.config/ebk/config.json` (path preserved from the `ebk` era so existing configs keep working). This configuration file manages settings for the web server, CLI defaults, and library preferences.

### Configuration File Structure

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 8000,
    "auto_open_browser": false,
    "page_size": 50
  },
  "cli": {
    "verbose": false,
    "color": true,
    "page_size": 50
  },
  "library": {
    "default_path": null
  }
}
```

### Configuration Management

```bash
# Initialize configuration (creates default config file)
book-memex config init

# View current configuration
book-memex config show

# Edit configuration in your default editor
book-memex config edit

# Set specific values
book-memex config set server.port 8080
book-memex config set library.default_path ~/my-library

# Get specific value
book-memex config get server.port
```

### CLI Overrides

All commands support CLI arguments that override configuration defaults:

```bash
# These override config settings
book-memex serve ~/library --port 9000 --host 127.0.0.1
```

## CLI Usage

book-memex uses [Typer](https://typer.tiangolo.com/) with [Rich](https://github.com/Textualize/rich) for a beautiful, colorized CLI experience.

### General CLI Structure

```bash
book-memex --help                 # See all available commands
book-memex <command> --help       # See specific command usage
book-memex --verbose <command>    # Enable verbose output
```

### Database Commands

Core library management with SQLAlchemy + SQLite backend:

```bash
# Initialize library
book-memex init ~/my-library

# Import books
book-memex import book.pdf ~/my-library
book-memex import ~/books/*.epub ~/my-library
book-memex import-calibre ~/Calibre/Library --output ~/my-library

# Search with advanced syntax
book-memex search "machine learning" ~/my-library              # Plain full-text search
book-memex search "title:Python rating:>=4" ~/my-library       # Field-specific with filters
book-memex search "author:Knuth format:pdf" ~/my-library       # Multiple criteria
book-memex search "tag:programming NOT java" ~/my-library      # Boolean operators
book-memex search '"deep learning" language:en' ~/my-library   # Phrase search with filter

# List and filter
book-memex list ~/my-library
book-memex list ~/my-library --author "Knuth" --language en --limit 20
book-memex list ~/my-library --format pdf --rating 4

# Statistics
book-memex stats ~/my-library
book-memex stats ~/my-library --format json

# Manage reading status
book-memex rate ~/my-library <book-id> 5
book-memex favorite ~/my-library <book-id>
book-memex tag ~/my-library <book-id> --add "must-read" "technical"

# Remove books
book-memex purge ~/my-library --rating 1 --confirm
```

### Web Server

Launch FastAPI-based web interface:

```bash
# Start server (uses config defaults)
book-memex serve ~/my-library

# Custom host and port
book-memex serve ~/my-library --host 127.0.0.1 --port 8080

# Auto-open browser
book-memex serve ~/my-library --auto-open

# Configure defaults in config
book-memex config set server.port 8080
book-memex config set server.auto_open_browser true
```

### Configuration Management

Manage global configuration:

```bash
# Initialize configuration
book-memex config init

# View configuration
book-memex config show

# Edit in default editor
book-memex config edit

# Set values
book-memex config set server.port 8080
book-memex config set library.default_path ~/books

# Get values
book-memex config get server.port
```

### Export and Advanced Features

```bash
# Export library
book-memex export html ~/my-library ~/library.html                    # Self-contained HTML with pagination
book-memex export html ~/my-library ~/site/lib.html --copy --base-url /library  # Copy files + covers
book-memex export zip ~/my-library ~/backup.zip
book-memex export json ~/my-library ~/metadata.json

# Virtual libraries (filtered views)
book-memex vlib create ~/my-library "python-books" --subject Python
book-memex vlib list ~/my-library

# Notes and annotations
book-memex note add ~/my-library <book-id> "Great chapter on algorithms"
book-memex note list ~/my-library <book-id>
```

---

## Documentation

Comprehensive documentation is available at: **[https://queelius.github.io/ebk/](https://queelius.github.io/ebk/)**

### Documentation Contents

- **Getting Started**
  - [Installation](https://queelius.github.io/ebk/getting-started/installation/)
  - [Quick Start](https://queelius.github.io/ebk/getting-started/quickstart/)
  - [Configuration Guide](https://queelius.github.io/ebk/getting-started/configuration/)

- **User Guide**
  - [CLI Reference](https://queelius.github.io/ebk/user-guide/cli/)
  - [Python API](https://queelius.github.io/ebk/user-guide/api/)
  - [LLM Features](https://queelius.github.io/ebk/user-guide/llm-features/)
  - [Web Server](https://queelius.github.io/ebk/user-guide/server/)
  - [Import/Export](https://queelius.github.io/ebk/user-guide/import-export/)
  - [Search & Query](https://queelius.github.io/ebk/user-guide/search/)

- **Advanced Topics**
  - [Hugo Export](https://queelius.github.io/ebk/advanced/hugo-export/)
  - [Symlink DAG](https://queelius.github.io/ebk/advanced/symlink-dag/)
  - [Recommendations](https://queelius.github.io/ebk/advanced/recommendations/)
  - [Batch Operations](https://queelius.github.io/ebk/advanced/batch-operations/)

- **Development**
  - [Architecture](https://queelius.github.io/ebk/development/architecture/)
  - [Contributing](https://queelius.github.io/ebk/development/contributing/)
  - [API Reference](https://queelius.github.io/ebk/development/api-reference/)

---


## Python API

book-memex provides a comprehensive SQLAlchemy-based API for programmatic library management:

```python
from pathlib import Path
from book_memex.library_db import Library

# Open or create a library
lib = Library.open(Path("~/my-library"))

# Import books with automatic metadata extraction
book = lib.add_book(
    Path("book.pdf"),
    metadata={"title": "My Book", "creators": ["Author Name"]},
    extract_text=True,
    extract_cover=True
)

# Fluent query interface
results = (lib.query()
    .filter_by_language("en")
    .filter_by_author("Knuth")
    .filter_by_subject("Algorithms")
    .order_by("title", desc=False)
    .limit(20)
    .all())

# Full-text search (FTS5)
results = lib.search("machine learning", limit=50)

# Get book by ID
book = lib.get_book(42)
print(f"{book.title} by {', '.join([a.name for a in book.authors])}")

# Update reading status
lib.update_reading_status(book.id, "reading", progress=50, rating=4)

# Add tags
lib.add_tags(book.id, ["must-read", "technical"])

# Get statistics
stats = lib.stats()
print(f"Total books: {stats['total_books']}")
print(f"Total authors: {stats['total_authors']}")
print(f"Languages: {', '.join(stats['languages'])}")

# Query with filters
from book_memex.db.models import Book, Author
from sqlalchemy import and_

books = lib.session.query(Book).join(Book.authors).filter(
    and_(
        Author.name.like("%Knuth%"),
        Book.language == "en"
    )
).all()

# Always close when done
lib.close()

# Or use context manager
with Library.open(Path("~/my-library")) as lib:
    results = lib.search("Python programming")
    for book in results:
        print(book.title)
```

See the [CLAUDE.md](CLAUDE.md) file for architectural details and [API documentation](https://queelius.github.io/ebk/user-guide/api/) for complete reference.

---

## Contributing

Contributions are welcome! Here's how to get involved:

1. **Fork the Repo**
2. **Create a Branch** for your feature or fix
3. **Commit & Push** your changes
4. **Open a Pull Request** describing the changes

We appreciate code contributions, bug reports, and doc improvements alike.

---

## License

Distributed under the [MIT License](https://github.com/queelius/ebk/blob/main/LICENSE).

---

## Integrations

book-memex follows a modular architecture where the core library remains lightweight, with optional integrations available:

### Streamlit Dashboard
```bash
pip install book-memex[streamlit]
streamlit run book_memex/integrations/streamlit/app.py
```

### MCP Server (AI Assistants)
```bash
pip install book-memex[mcp]
# Configure your AI assistant to use the MCP server
```

### Visualizations
```bash
pip install book-memex[viz]
# Visualization tools will be available as a separate script
# Documentation coming soon in integrations/viz/
```

See the [Integrations Guide](integrations/README.md) for detailed setup instructions.

---

## Architecture

book-memex is designed with a clean, layered architecture:

1. **Core Library** (`book_memex.library_db`): Fluent API for all operations
2. **CLI** (`book_memex.cli`): Typer-based commands using the fluent API
3. **Import/Export** (`book_memex.services`, `book_memex.exports`): Modular format support
4. **Integrations** (`integrations/`): Optional add-ons (web UI, AI, viz)

This design ensures the core remains lightweight while supporting powerful extensions.

---

## Development

```bash
# Clone the repository
git clone https://github.com/queelius/ebk.git
cd ebk

# Create virtual environment
make venv

# Install in development mode
make setup

# Run tests
make test

# Check coverage
make coverage
```

---

## Stay Updated

- **GitHub**: [https://github.com/queelius/ebk](https://github.com/queelius/ebk)
- **Website**: [https://metafunctor.com](https://metafunctor.com)

---

## Support

- **Issues**: [Open an Issue](https://github.com/queelius/ebk/issues) on GitHub
- **Contact**: <lex@metafunctor.com>

---

Happy eBook managing!
