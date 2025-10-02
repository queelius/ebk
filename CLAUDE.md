# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ebk is a Python-based eBook metadata management tool with a Typer CLI and optional integrations. It provides:
- Fluent API for programmatic library management
- Rich CLI with colorized output
- Import/export from multiple sources (Calibre, raw ebooks, ZIP archives)
- Set-theoretic library merging operations
- Plugin architecture for extensibility

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
# After installation, use the ebk command
ebk --help
ebk import-calibre ~/Calibre/Library --output-dir ~/my-library
ebk search "Python" ~/my-library
```

## Architecture Overview

### Core Structure
```
ebk/
├── library.py          # Core Library class with fluent API
├── library_enhanced.py # Enhanced Library with advanced features
├── cli.py             # Typer CLI implementation (entry point: ebk)
├── manager.py         # Simple LibraryManager for programmatic use
├── plugins/           # Plugin system architecture
│   ├── base.py       # Plugin base classes
│   ├── registry.py   # Plugin registry management
│   └── hooks.py      # Hook system for events
├── imports/          # Import modules
│   ├── calibre.py   # Calibre library import
│   ├── ebooks.py    # Raw ebook folder import
│   └── zip.py       # ZIP archive import
├── exports/          # Export modules
│   ├── hugo.py      # Hugo static site export
│   └── zip.py       # ZIP archive export
├── merge.py         # Set operations (union, intersect, diff, symdiff)
├── utils.py         # Common utilities (search, stats, etc.)
├── ident.py         # Unique ID generation
├── extract_metadata.py # Metadata extraction from PDFs/EPUBs
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

1. **Fluent API**: The Library class supports method chaining:
   ```python
   lib.add_entry(...).tag_all("fiction").filter(lambda e: e.get("rating") >= 4).save()
   ```

2. **Plugin Architecture**: Extensible via plugin classes inheriting from base types:
   - MetadataExtractor: Extract metadata from external sources
   - TagSuggester: Suggest tags based on content
   - ContentAnalyzer: Analyze book content
   - Validator: Validate library entries
   - Exporter: Custom export formats

3. **Unique Identification**: Each entry gets a hash-based ID from `ident.py` for deduplication

4. **Transaction Support**: Library operations can be wrapped in transactions for atomicity

### Data Format

Libraries are stored as directories containing:
- `metadata.json`: All book metadata entries
- Ebook files organized by unique IDs
- Cover images extracted separately

Metadata entry structure:
```json
{
  "unique_id": "hash_based_id",
  "title": "Book Title",
  "creators": ["Author Name"],
  "subjects": ["Subject1", "Subject2"],
  "language": "en",
  "identifiers": {"isbn": "1234567890"},
  "file_paths": ["path/to/book.pdf"],
  "cover_path": "path/to/cover.jpg"
}
```

## Common Development Tasks

### Adding a New Import Format
1. Create module in `ebk/imports/new_format.py`
2. Implement import function following existing patterns
3. Add CLI command in `ebk/cli.py`:
   ```python
   @app.command()
   def import_new_format(source: Path, output_dir: Path):
       # Implementation
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
from ebk import Library

# Open/create library
lib = Library.open("/path/to/library")

# Query with fluent API
results = (lib.query()
    .where("language", "en")
    .where("subjects", "Python", "contains")
    .order_by("title")
    .execute())
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
- Python API: `from ebk import Library`
- Web UI: `streamlit run ebk/integrations/streamlit/app.py`