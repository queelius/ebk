# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ebk is a Python-based eBook metadata management tool with:
- **SQLAlchemy + SQLite backend** with FTS5 full-text search
- **Fluent Query API** for programmatic library management
- **Typer CLI** with Rich colorized output
- **Virtual File System (VFS)** for Unix-like library navigation
- **REPL Shell** with piping, grep, find, and file management
- **Hash-based deduplication** using SHA256
- **Plugin architecture** for extensibility
- **AI-powered features** (optional): metadata enrichment via Ollama/OpenAI

## Development Commands

```bash
# Setup and dependencies
make setup              # Create venv and install all deps
make install-dev        # Install with dev dependencies only

# Testing
pytest tests/ -v                                    # All tests
pytest tests/test_search_parser.py -v               # Single file
pytest tests/test_search_parser.py::TestClass::test_method -v  # Single test
pytest --cov=ebk --cov-report=html                  # With coverage

# Code quality
make lint               # Run flake8, mypy, pylint
make format             # Run black, isort

# Release
./scripts/deploy-docs.sh    # Build and deploy mkdocs
python -m build             # Build package
twine upload dist/*         # Publish to PyPI
```

## CLI Usage

Commands use config default library path (`~/.config/ebk/config.json`) when path not specified:

```bash
ebk config --library-path ~/my-library   # Set default library

# These now work without specifying path
ebk list
ebk search "python programming"
ebk stats
ebk shell

# With pagination
ebk list -n 20 --offset 40               # Page 3 of 20 results
ebk search "python" --offset 20          # Next page of results
```

## Architecture

### Core Modules

| Module | Purpose |
|--------|---------|
| `library_db.py` | Main Library class, fluent query API entry point |
| `cli.py` | Typer CLI with `resolve_library_path()` for config fallback |
| `search_parser.py` | Advanced query parser (field:value, boolean, comparisons) |
| `config.py` | Configuration at `~/.config/ebk/config.json` |
| `db/models.py` | SQLAlchemy ORM: Book, Author, Subject, File, Cover, Tag |
| `db/session.py` | Session management, FTS5 setup |

### Virtual File System (vfs/)

Presents library as navigable filesystem:
```
/books/{id}/.metadata     # JSON metadata
/authors/{name}/          # Books by author
/tags/{hierarchy}/        # Hierarchical tags
/similar/{id}/            # Similar books
```

Key files: `base.py` (VFSNode base), `resolver.py` (path resolution), `nodes/` (node types)

### REPL Shell (repl/)

Unix-like shell with piping: `ls books/ | grep Python | head 10`

Key files: `shell.py` (LibraryShell), `find.py`, `grep.py`, `text_utils.py`

### Search Parser

Supports: `title:Python`, `author:Knuth`, `rating:>=4`, `"exact phrase"`, `AND/OR/NOT`

Parses to `ParsedQuery` → generates FTS5 query + SQL conditions

### Key Patterns

**Fluent Query API:**
```python
results = (lib.query()
    .filter_by_author("Knuth")
    .filter_by_language("en")
    .order_by("title")
    .limit(20).all())
```

**Config Resolution:** `resolve_library_path()` in cli.py handles config fallback for optional library_path arguments.

## Database Schema

Core tables: books, authors, subjects, files, covers, tags (hierarchical), personal_metadata (ratings/favorites), books_fts (FTS5 virtual table)

Library directory: `library.db`, `files/` (hash-prefixed storage), `covers/thumbnails/`

## Test Organization

Key test files in `/tests/`:
- `test_search_parser.py` (98% coverage)
- `test_vfs_resolver.py` (99% coverage)
- `test_library_api.py`, `test_database_library.py`
- `test_repl.py`, `test_services.py`

Fixtures in `conftest.py`: `temp_library`, `populated_library`

## Entry Points

- **CLI**: `ebk` command → `ebk.cli:app`
- **Python API**: `from ebk.library_db import Library`
- **Web Server**: `ebk serve` → FastAPI on port 8000
- **REPL Shell**: `ebk shell` → Interactive VFS shell
