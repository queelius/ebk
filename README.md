# ebk

**ebk** is a powerful eBook metadata management tool with a SQLAlchemy + SQLite database backend. It provides a comprehensive fluent API for programmatic use, a rich Typer-based CLI (with colorized output courtesy of [Rich](https://github.com/Textualize/rich)), full-text search with FTS5 indexing, automatic text extraction and chunking for semantic search, hash-based file deduplication, and optional AI-powered features including knowledge graphs and semantic search. 


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
- **AI-Powered Features** (optional):
  - **LLM Provider Abstraction**: Support for multiple LLM backends (Ollama, OpenAI-compatible APIs)
  - **Metadata Enrichment**: Auto-generate tags, categories, and enhanced descriptions using LLMs
  - **Local & Remote LLM**: Connect to local Ollama or remote GPU servers
  - **Knowledge Graph**: NetworkX-based concept extraction and relationship mapping
  - **Semantic Search**: Vector embeddings for similarity search (with TF-IDF fallback)
  - **Reading Companion**: Track reading sessions with timestamps
  - **Question Generator**: Generate active recall questions
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
pip install ebk
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
pip install ebk[streamlit]

# With visualization tools
pip install ebk[viz]

# With all optional features
pip install ebk[all]

# For development
pip install ebk[dev]
```

> **Note**: Requires Python 3.10+

---

## Quick Start

### 1. Initialize Configuration

```bash
# Create default configuration file at ~/.config/ebk/config.json
ebk config init

# View current configuration
ebk config show

# Set default library path
ebk config set library.default_path ~/my-library
```

### 2. Create and Populate Library

```bash
# Initialize a new library
ebk init ~/my-library

# Import a single ebook with auto-metadata extraction
ebk import book.pdf ~/my-library

# Import from Calibre library
ebk import-calibre ~/Calibre/Library --output ~/my-library

# Search using full-text search
ebk search "python programming" ~/my-library

# List books with filtering
ebk list ~/my-library --author "Knuth" --limit 20

# Get statistics
ebk stats ~/my-library
```

### 3. Launch Web Interface

```bash
# Start web server (uses config defaults)
ebk serve ~/my-library

# Custom port and host
ebk serve ~/my-library --port 8080 --host 127.0.0.1

# Auto-open browser
ebk config set server.auto_open_browser true
ebk serve ~/my-library
```

### 4. AI-Powered Metadata Enrichment

```bash
# Configure LLM provider
ebk config set llm.provider ollama
ebk config set llm.model llama3.2
ebk config set llm.host localhost

# Enrich library metadata using LLM
ebk enrich ~/my-library

# Enrich with all features
ebk enrich ~/my-library --generate-tags --categorize --enhance-descriptions

# Use remote GPU server
ebk enrich ~/my-library --host 192.168.1.100
```

---

## Configuration

ebk uses a centralized configuration system stored at `~/.config/ebk/config.json`. This configuration file manages settings for LLM providers, web server, CLI defaults, and library preferences.

### Configuration File Structure

```json
{
  "llm": {
    "provider": "ollama",
    "model": "llama3.2",
    "host": "localhost",
    "port": 11434,
    "api_key": null,
    "temperature": 0.7,
    "max_tokens": null
  },
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
ebk config init

# View current configuration
ebk config show

# Edit configuration in your default editor
ebk config edit

# Set specific values
ebk config set llm.provider ollama
ebk config set llm.model mistral
ebk config set server.port 8080
ebk config set library.default_path ~/my-library

# Get specific value
ebk config get llm.model
```

### LLM Provider Configuration

Configure LLM providers for metadata enrichment:

```bash
# Local Ollama (default)
ebk config set llm.provider ollama
ebk config set llm.host localhost
ebk config set llm.port 11434
ebk config set llm.model llama3.2

# Remote GPU server
ebk config set llm.host 192.168.1.100

# OpenAI-compatible API (future)
ebk config set llm.provider openai
ebk config set llm.api_key sk-...
ebk config set llm.model gpt-4
```

### CLI Overrides

All commands support CLI arguments that override configuration defaults:

```bash
# These override config settings
ebk serve ~/library --port 9000 --host 127.0.0.1
ebk enrich ~/library --host 192.168.1.50 --model mistral
```

## CLI Usage

ebk uses [Typer](https://typer.tiangolo.com/) with [Rich](https://github.com/Textualize/rich) for a beautiful, colorized CLI experience.

### General CLI Structure

```bash
ebk --help                 # See all available commands
ebk <command> --help       # See specific command usage
ebk --verbose <command>    # Enable verbose output
```

### Database Commands

Core library management with SQLAlchemy + SQLite backend:

```bash
# Initialize library
ebk init ~/my-library

# Import books
ebk import book.pdf ~/my-library
ebk import ~/books/*.epub ~/my-library
ebk import-calibre ~/Calibre/Library --output ~/my-library

# Search with advanced syntax
ebk search "machine learning" ~/my-library              # Plain full-text search
ebk search "title:Python rating:>=4" ~/my-library       # Field-specific with filters
ebk search "author:Knuth format:pdf" ~/my-library       # Multiple criteria
ebk search "tag:programming NOT java" ~/my-library      # Boolean operators
ebk search '"deep learning" language:en' ~/my-library   # Phrase search with filter

# List and filter
ebk list ~/my-library
ebk list ~/my-library --author "Knuth" --language en --limit 20
ebk list ~/my-library --format pdf --rating 4

# Statistics
ebk stats ~/my-library
ebk stats ~/my-library --format json

# Manage reading status
ebk rate ~/my-library <book-id> 5
ebk favorite ~/my-library <book-id>
ebk tag ~/my-library <book-id> --add "must-read" "technical"

# Remove books
ebk purge ~/my-library --rating 1 --confirm
```

### Web Server

Launch FastAPI-based web interface:

```bash
# Start server (uses config defaults)
ebk serve ~/my-library

# Custom host and port
ebk serve ~/my-library --host 127.0.0.1 --port 8080

# Auto-open browser
ebk serve ~/my-library --auto-open

# Configure defaults in config
ebk config set server.port 8080
ebk config set server.auto_open_browser true
```

### AI-Powered Features

Enrich metadata using LLMs:

```bash
# Basic enrichment (uses config settings)
ebk enrich ~/my-library

# Full enrichment
ebk enrich ~/my-library \
  --generate-tags \
  --categorize \
  --enhance-descriptions \
  --assess-difficulty

# Enrich specific book
ebk enrich ~/my-library --book-id 42

# Use remote GPU server
ebk enrich ~/my-library --host 192.168.1.100 --model mistral

# Dry run (preview changes without saving)
ebk enrich ~/my-library --dry-run
```

### Configuration Management

Manage global configuration:

```bash
# Initialize configuration
ebk config init

# View configuration
ebk config show
ebk config show --section llm

# Edit in default editor
ebk config edit

# Set values
ebk config set llm.model llama3.2
ebk config set server.port 8080
ebk config set library.default_path ~/books

# Get values
ebk config get llm.model
```

### Export and Advanced Features

```bash
# Export library
ebk export html ~/my-library ~/library.html                    # Self-contained HTML with pagination
ebk export html ~/my-library ~/site/lib.html --copy --base-url /library  # Copy files + covers
ebk export zip ~/my-library ~/backup.zip
ebk export json ~/my-library ~/metadata.json

# Virtual libraries (filtered views)
ebk vlib create ~/my-library "python-books" --subject Python
ebk vlib list ~/my-library

# Notes and annotations
ebk note add ~/my-library <book-id> "Great chapter on algorithms"
ebk note list ~/my-library <book-id>
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

ebk provides a comprehensive SQLAlchemy-based API for programmatic library management:

```python
from pathlib import Path
from ebk.library_db import Library

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
from ebk.db.models import Book, Author
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

### AI-Powered Metadata Enrichment

```python
from ebk.ai.llm_providers.ollama import OllamaProvider
from ebk.ai.metadata_enrichment import MetadataEnrichmentService

# Initialize provider (local or remote)
provider = OllamaProvider.remote(
    host="192.168.1.100",
    model="llama3.2"
)

service = MetadataEnrichmentService(provider)

async with provider:
    # Generate tags
    tags = await service.generate_tags(
        title="Introduction to Algorithms",
        authors=["Cormen", "Leiserson"],
        description="Comprehensive algorithms textbook"
    )

    # Categorize
    categories = await service.categorize(
        title="Introduction to Algorithms",
        subjects=["Algorithms", "Data Structures"]
    )

    # Enhance description
    description = await service.enhance_description(
        title="Introduction to Algorithms",
        text_sample="Chapter 1: The Role of Algorithms..."
    )
```

See the [CLAUDE.md](CLAUDE.md) file for architectural details and [API documentation](https://queelius.github.io/ebk/user-guide/api/) for complete reference.

---

## Contributing

Contributions are welcome! Here’s how to get involved:

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

ebk follows a modular architecture where the core library remains lightweight, with optional integrations available:

### Streamlit Dashboard
```bash
pip install ebk[streamlit]
streamlit run ebk/integrations/streamlit/app.py
```

### MCP Server (AI Assistants)
```bash
pip install ebk[mcp]
# Configure your AI assistant to use the MCP server
```

### Visualizations
```bash
pip install ebk[viz]
# Visualization tools will be available as a separate script
# Documentation coming soon in integrations/viz/
```

See the [Integrations Guide](integrations/README.md) for detailed setup instructions.

---

## Architecture

ebk is designed with a clean, layered architecture:

1. **Core Library** (`ebk.library`): Fluent API for all operations
2. **CLI** (`ebk.cli`): Typer-based commands using the fluent API
3. **Import/Export** (`ebk.imports`, `ebk.exports`): Modular format support
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

Happy eBook managing! 📚✨
