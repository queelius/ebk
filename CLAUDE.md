# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ebk is a Python-based eBook metadata management tool with a Typer CLI and optional integrations. It provides:
- **SQLAlchemy + SQLite database backend** for robust storage and querying
- Fluent API for programmatic library management
- Rich CLI with colorized output
- Full-text search with FTS5 indexing
- Automatic text extraction and chunking for semantic search
- Hash-based file deduplication
- Import from multiple sources (Calibre, raw ebooks, metadata files)
- Cover extraction and thumbnail generation
- Plugin architecture for extensibility
- AI-powered knowledge graph and semantic search (optional)

## Key Commands

### Development Setup
```bash
# Create virtual environment and install all dependencies
make setup

# Alternative manual setup
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev,all]"
```

### Testing
```bash
# Run all tests
make test
# OR
python -m pytest tests/ -v

# Run specific test file
make test-file FILE=tests/test_library_api.py
# OR
python -m pytest tests/test_library_api.py -v

# Run with coverage
make test-coverage
# OR
python -m pytest tests/ -v --cov=ebk --cov-report=html --cov-report=term

# Test markers available
pytest -m unit       # Unit tests only
pytest -m integration # Integration tests only
pytest -m "not slow" # Skip slow tests
```

### Linting & Formatting
```bash
# Run all linters
make lint
# Runs: flake8, mypy, pylint

# Format code
make format
# Runs: black, isort

# Check formatting without applying
make format-check
```

### CLI Usage

```bash
# Initialize a new library
ebk db-init ~/my-library

# Import a single ebook with auto-metadata extraction
ebk db-import book.pdf ~/my-library

# Import from Calibre library
ebk db-import-calibre ~/Calibre/Library ~/my-library

# Search using full-text search (searches title, description, extracted text)
ebk db-search "python programming" ~/my-library

# List books with filtering
ebk db-list ~/my-library --author "Knuth" --limit 20

# Show library statistics
ebk db-stats ~/my-library

# For help on any command
ebk --help
ebk db-import --help
```

## Architecture Overview

### Core Structure
```
ebk/
├── library_db.py       # Database-backed Library class (SQLAlchemy)
├── cli.py             # Typer CLI implementation (entry point: ebk)
├── db/                # Database layer (SQLAlchemy + SQLite)
│   ├── models.py     # SQLAlchemy ORM models (Book, Author, File, etc.)
│   ├── session.py    # Session management and DB initialization
│   └── __init__.py   # Database module exports
├── services/          # Business logic services
│   ├── import_service.py    # Import books with deduplication
│   ├── text_extraction.py   # Extract text from ebooks
│   └── __init__.py          # Services exports
├── ai/               # AI-powered features (optional)
│   ├── knowledge_graph.py   # NetworkX-based concept graph
│   ├── semantic_search.py   # Vector embeddings for search
│   ├── reading_companion.py # Reading session tracking
│   └── question_generator.py # Active recall questions
├── plugins/           # Plugin system architecture
│   ├── base.py       # Plugin base classes
│   ├── registry.py   # Plugin registry management
│   └── hooks.py      # Hook system for events
├── exports/          # Export modules
│   ├── hugo.py      # Hugo static site export
│   └── zip.py       # ZIP archive export
├── extract_metadata.py # Metadata extraction from PDFs/EPUBs
├── ident.py         # Unique ID generation
└── decorators.py    # Function decorators for validation
```

### Integrations (Optional)
```
integrations/
├── streamlit-dashboard/ # Web UI (requires pip install ebk[streamlit])
├── mcp/                # MCP server for AI assistants
├── metadata/           # Metadata extractors (Google Books, etc.)
├── network/            # Network analysis and visualizations
└── llm/                # LLM integration for OpenAI-compatible APIs
```

### Key Design Patterns

1. **Fluent Query API**: The Library class supports method chaining for queries:
   ```python
   results = (lib.query()
       .filter_by_language("en")
       .filter_by_author("Knuth")
       .order_by("title")
       .limit(20)
       .all())
   ```

2. **Hash-based Deduplication**: Files are deduplicated using SHA256 hashes
   - Same file (same hash) = skipped
   - Same book, different format (different hash) = added as additional format
   - Hash-prefixed storage: `files/ab/abc123.pdf`

3. **Automatic Text Extraction**: Text is extracted from ebooks and indexed for FTS
   - PDF: PyMuPDF (primary) with pypdf fallback
   - EPUB: ebooklib with HTML parsing
   - Plaintext: Direct read with encoding detection
   - Chunks: 500-word overlapping chunks for semantic search

4. **SQLAlchemy ORM**: Normalized relational database with proper relationships
   - Many-to-many: Books ↔ Authors, Books ↔ Subjects
   - One-to-many: Book → Files, Book → Covers, Book → Chunks
   - FTS5 virtual table for full-text search

### Database Schema

Library directory structure:
```
my-library/
├── library.db              # SQLite database
├── files/                  # Hash-prefixed ebook storage
│   ├── ab/
│   │   └── abc123...pdf
│   └── cd/
│       └── cde456...epub
├── covers/                 # Cover images
│   ├── ab/
│   │   └── abc123.jpg
│   └── thumbnails/
│       └── abc123_thumb.jpg
└── vectors/                # Vector embeddings (future)
    └── embeddings.pkl
```

Core database tables:
- **books**: Core book metadata (title, language, publisher, etc.)
- **authors**: Author names with sort names
- **subjects**: Tags/subjects/categories
- **files**: Physical file records with hash, format, size
- **extracted_texts**: Full text extracted from files
- **text_chunks**: Overlapping chunks for semantic search
- **covers**: Cover images with dimensions
- **books_fts**: FTS5 virtual table for full-text search

## Common Development Tasks

### Adding Support for a New Ebook Format
1. Add text extraction method to `ebk/services/text_extraction.py`:
   ```python
   def _extract_newformat_text(self, file_path: Path) -> str:
       # Extract text from new format
       return text
   ```

2. Update `extract_full_text` method to handle new format:
   ```python
   elif file.format.lower() == 'newformat':
       text = self._extract_newformat_text(file_path)
   ```

3. Optionally add cover extraction to `ebk/services/import_service.py`:
   ```python
   def _extract_newformat_cover(self, file_path: Path, file_hash: str) -> Optional[Path]:
       # Extract cover from new format
       return cover_path
   ```

### Creating a Plugin
1. Create class inheriting from appropriate base in `ebk/plugins/base.py`
2. Register plugin:
   ```python
   from ebk.plugins import plugin_registry
   plugin_registry.register("my_plugin", MyPlugin())
   ```

### Working with the Library API
```python
from ebk.library_db import Library
from pathlib import Path

# Initialize or open library
lib = Library.open(Path("~/my-library"))

# Add a book with auto-metadata extraction
book = lib.add_book(
    Path("book.pdf"),
    metadata={"title": "My Book", "creators": ["Author Name"]},
    extract_text=True,
    extract_cover=True
)

# Query with fluent API
results = (lib.query()
    .filter_by_language("en")
    .filter_by_subject("Python")
    .filter_by_author("Knuth")
    .order_by("title", desc=False)
    .limit(20)
    .all())

# Full-text search
results = lib.search("machine learning", limit=50)

# Get statistics
stats = lib.stats()
print(f"Total books: {stats['total_books']}")

# Update reading status
lib.update_reading_status(book.id, "reading", progress=50, rating=4)

# Always close when done
lib.close()
```

## Testing Guidelines

- Unit tests: Test individual functions/methods in isolation
- Integration tests: Test interactions between components
- Use pytest fixtures for common test data
- Mock external dependencies (file I/O, network calls)
- Aim for >80% code coverage

## Dependencies

- **Python 3.10+** required
- Core: typer, rich, lxml, pypdf/PyMuPDF, ebooklib, Pillow, jinja2
- Optional: streamlit, pandas (web UI); networkx, matplotlib (visualizations)
- Dev: pytest, black, ruff, mypy, pre-commit

## Entry Points

- CLI: `ebk` command maps to `ebk.cli:app`
- Python API: `from ebk.library_db import Library`
- Web UI (optional): `streamlit run ebk/integrations/streamlit/app.py`