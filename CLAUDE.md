# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ebk is a Python-based eBook metadata management tool with a Typer CLI and Streamlit web dashboard. It enables importing from various sources (Calibre, raw ebooks, ZIP archives), advanced merging operations, and exporting to different formats.

## Key Commands

### Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### Running Tests
```bash
# Run unit tests
python -m pytest tests/

# Run a specific test
python -m pytest tests/test_filters.py
```

### CLI Entry Point
The main CLI is accessible via `ebk` command after installation, which maps to `ebk.cli:app` (using Typer framework).

## Architecture Overview

### Core Structure
- **ebk/cli.py**: Main CLI interface using Typer, handles all commands (import-*, export, merge, search, etc.)
- **ebk/manager.py**: Simple LibraryManager class for programmatic library manipulation
- **ebk/imports/**: Import modules for Calibre libraries, raw ebooks, and existing ebk archives
- **ebk/exports/**: Export modules for Hugo static sites and ZIP archives
- **ebk/merge.py**: Set-theoretic library merging operations (union, intersect, diff, symdiff)
- **integrations/**: External tool integrations (e.g., MCP server for AI assistants)

### Data Format
Libraries are stored as JSON with:
- `metadata.json`: Central metadata file containing all book entries
- Ebook files organized by unique IDs
- Cover images extracted and stored separately

### Key Concepts
1. **Unique Identification**: Each entry gets a hash-based unique ID for consistent deduplication
2. **Multiple Import Paths**: Supports Calibre metadata.opf, PDF metadata extraction, EPUB parsing
3. **Rich CLI**: Uses Rich library for colorized output and progress tracking
4. **Set Operations**: Libraries can be merged using mathematical set operations

### Dependencies
- Python 3.10+ required
- Key libraries: typer, rich, streamlit, pandas, lxml, PyPDF2, ebooklib
- Full list in requirements.txt

## Common Tasks

### Adding New Import Format
1. Create new module in `ebk/imports/`
2. Implement import function following pattern of existing importers
3. Add CLI command in `ebk/cli.py` using `@app.command()` decorator

### Modifying Streamlit Dashboard
1. Main app entry: `ebk/streamlit/app.py`
2. Display components: `ebk/streamlit/display.py`
3. Filtering logic: `ebk/streamlit/filters.py`

### Working with Metadata
- Metadata structure follows a flexible JSON schema
- Common fields: title, creators, subjects, language, identifiers, file_paths, cover_path
- Use `ebk/utils.py` for common operations (search, statistics, etc.)

### Integrations
- The `integrations/` directory contains optional add-ons and external tool interfaces
- **Streamlit Dashboard**: Web-based interface for browsing libraries (optional dependency)
- **MCP Server**: Allows AI assistants to interact with ebk via standardized protocol
- **Visualizations**: Network graph visualizations of library relationships
- ebk core remains lightweight with minimal dependencies