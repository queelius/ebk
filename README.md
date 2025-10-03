# ebk

![ebk Logo](https://github.com/queelius/ebk/blob/main/logo.png?raw=true)

**ebk** is a powerful eBook metadata management tool built on **SQLAlchemy + SQLite**. It provides a comprehensive fluent API for programmatic use, a rich Typer-based CLI (with colorized output courtesy of [Rich](https://github.com/Textualize/rich)), automatic text extraction with full-text search (FTS5), hash-based file deduplication, and optional AI-powered features including knowledge graphs and semantic search. 


---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [CLI Usage](#cli-usage)
  - [General CLI Structure](#general-cli-structure)
  - [Importing Libraries](#importing-libraries)
    - [Import from Zip (`import-zip`)](#import-from-zip-import-zip)
    - [Import Calibre Library (`import-calibre`)](#import-calibre-library-import-calibre)
    - [Import Raw Ebooks (`import-ebooks`)](#import-raw-ebooks-import-ebooks)
  - [Exporting Libraries](#exporting-libraries)
  - [Merging Libraries](#merging-libraries)
  - [Searching](#searching)
    - [Regex Search](#regex-search)
    - [JMESPath Search](#jmespath-search)
  - [Listing, Adding, Updating, and Removing Entries](#listing-adding-updating-and-removing-entries)
- [Python API](#python-api)
- [Integrations](#integrations)
- [Contributing](#contributing)
- [License](#license)
- [Roadmap & TODOs](ROADMAP.md)
- [Stay Updated](#stay-updated)
- [Support](#support)

---

## Features

- **SQLAlchemy + SQLite Backend**: Robust, normalized database with proper relationships and constraints
- **Full-Text Search (FTS5)**: Lightning-fast search across titles, descriptions, and extracted text content
- **Automatic Text Extraction**:
  - PDF support (PyMuPDF primary, pypdf fallback)
  - EPUB support (ebooklib with HTML parsing)
  - Plaintext files with encoding detection
  - 500-word overlapping chunks for semantic search
- **Hash-based Deduplication**: SHA256 file hashing prevents duplicates while supporting multiple formats per book
- **Fluent Query API**: Chainable query builder for filtering by author, subject, language, rating, reading status
- **Typer + Rich CLI**: Colorized, user-friendly command-line interface with progress tracking
- **Import from Multiple Sources**:
  - Calibre libraries (via metadata.opf files)
  - Individual ebook files with auto-metadata extraction
  - Batch import with progress tracking
- **Cover Management**:
  - Automatic extraction from PDFs (first page) and EPUBs (metadata)
  - Thumbnail generation
  - Hash-prefixed storage for organization
- **AI Features** (optional):
  - **Knowledge Graph**: NetworkX-based concept extraction and relationship mapping
  - **Semantic Search**: Vector embeddings with sentence-transformers (or TF-IDF fallback)
  - **Reading Companion**: Track reading sessions, annotations, and progress
  - **Question Generation**: Active recall questions based on content
- **Integrations** (optional):
  - **Streamlit Dashboard**: Interactive web interface
  - **MCP Server**: AI assistant integration via Model Context Protocol
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

```bash
# Initialize a new library
ebk db-init ~/my-library

# Import from Calibre library
ebk db-import-calibre ~/Calibre/Library ~/my-library

# Import a single ebook
ebk db-import book.pdf ~/my-library

# Search with full-text search (searches title, description, and extracted text)
ebk db-search "python programming" ~/my-library

# List books with filtering
ebk db-list ~/my-library --author "Knuth" --limit 20

# Show library statistics
ebk db-stats ~/my-library

# Get help
ebk --help
ebk db-import --help
```

---

## Configuration

ebk can be configured via environment variables or a configuration file at `~/.ebkrc`:

```ini
[export]
# Default Hugo export path
hugo_path = "/path/to/hugo/site"

[library]
# Default library location
default_path = "~/ebooks/library"

[import]
# Default formats to import
formats = ["pdf", "epub", "mobi", "azw3"]
```

## CLI Usage

ebk uses [Typer](https://typer.tiangolo.com/) under the hood, providing subcommands for imports, exports, merges, searches, listing, updates, etc. The CLI also leverages [Rich](https://github.com/Textualize/rich) for colorized/logging output.

### General CLI Structure

```
ebk --help
ebk <command> --help     # see specific usage, options
```

The primary commands include:
- `db-init` - Initialize new database-backed library
- `db-import` - Import single ebook file
- `db-import-calibre` - Import from Calibre library
- `db-search` - Full-text search across library
- `db-list` - List books with filtering
- `db-stats` - Show library statistics
- `export` - Export library to various formats
- `build-knowledge` - Build AI knowledge graph (optional)
- `ask` - Ask questions about your library (optional, AI)
- …and more!

---

### Database Commands

#### Initialize Library (`db-init`)

Create a new database-backed library:

```bash
ebk db-init ~/my-library
```

This creates a directory with a SQLite database (`library.db`) and subdirectories for files and covers.

#### Import Single Ebook (`db-import`)

Import an ebook file with automatic metadata extraction:

```bash
ebk db-import book.pdf ~/my-library
ebk db-import book.epub ~/my-library --title "Custom Title" --authors "Author Name"
```

Options:
- `--title`, `-t`: Override book title
- `--authors`, `-a`: Set authors (comma-separated)
- `--subjects`, `-s`: Set subjects/tags (comma-separated)
- `--language`, `-l`: Set language code
- `--no-text`: Skip text extraction
- `--no-cover`: Skip cover extraction

#### Import Calibre Library (`db-import-calibre`)

Import books from a [Calibre](https://calibre-ebook.com/) library:

```bash
ebk db-import-calibre /path/to/calibre/library ~/my-library
ebk db-import-calibre /path/to/calibre/library ~/my-library --limit 100
```

Reads Calibre's `metadata.opf` files and imports ebooks with full metadata extraction.

Options:
- `--limit`: Limit number of books to import (useful for testing)

#### Search and Query (`db-search`, `db-list`)

Full-text search across all books:

```bash
# Search across title, description, and extracted text
ebk db-search "python programming" ~/my-library

# Limit results
ebk db-search "machine learning" ~/my-library --limit 10
```

List books with filters:

```bash
# List all books
ebk db-list ~/my-library

# Filter by author
ebk db-list ~/my-library --author "Knuth"

# Filter by subject/tag
ebk db-list ~/my-library --subject "Computer Science"

# Filter by language
ebk db-list ~/my-library --language "en"

# Combine filters with pagination
ebk db-list ~/my-library --author "Knuth" --language "en" --limit 20 --offset 0
```

#### Library Statistics (`db-stats`)

View library statistics:

```bash
ebk db-stats ~/my-library
```

Shows:
- Total books, authors, subjects, files
- Books read and currently reading
- Language distribution
- Format distribution

---

### Exporting Libraries

Available formats:
- **Hugo**:  
  ```bash
  # Basic export
  ebk export hugo /path/to/ebk_library /path/to/hugo_site
  
  # With Jinja templates and organization
  ebk export hugo /path/to/ebk_library /path/to/hugo_site --jinja --organize-by subject
  ```
  This writes Hugo-compatible Markdown files (and copies covers/ebooks) into your Hugo `content` + `static` folders. See [Hugo Export Documentation](docs/HUGO_EXPORT.md) for advanced options.

- **Zip**:  
  ```bash
  ebk export zip /path/to/ebk_library /path/to/export.zip
  ```
  Creates a `.zip` archive containing the entire library.

---

### Merging Libraries

Use set-theoretic operations to combine multiple ebk libraries:

```bash
ebk merge <operation> /path/to/merged_dir [libs...]
```

Where `<operation>` can be:
- `union`: Combine all unique entries
- `intersect`: Keep only entries common to all libraries
- `diff`: Keep entries present in the first library but not others
- `symdiff`: Entries in exactly one library (exclusive-or)

**Example**:

```bash
ebk merge union /path/to/merged_lib /path/to/lib1 /path/to/lib2
```

---

### Searching

#### Regex Search

```bash
ebk search <regex> /path/to/ebk_library
```

By default, it searches the `title` field. You can specify additional fields:

```bash
ebk search "Python" /path/to/lib --regex-fields title creators
```

#### JMESPath Search

For more powerful, structured searches:

```bash
ebk search "[?language=='en']" /path/to/lib --jmespath
```

JMESPath expressions allow you to filter, project fields, etc. If you want to see these results as JSON:

```bash
ebk search "[?language=='en']" /path/to/lib --jmespath --json
```

---

### Advanced Features

#### Symlink DAG Export
```bash
ebk export-dag /path/to/library /path/to/output
```
Creates a navigable directory structure where tags become folders and books appear via symlinks. See [Symlink DAG Documentation](docs/SYMLINK_DAG_EXPORT.md).

#### Find Similar Books
```bash
ebk similar /path/to/library book_unique_id --threshold 0.7
```

#### Get Recommendations
```bash
# Random recommendations
ebk recommend /path/to/library

# Based on specific books
ebk recommend /path/to/library --based-on book_id_1 --based-on book_id_2
```

### Listing, Adding, Updating, and Removing Entries

- **List**:
  ```bash
  ebk list /path/to/lib
  ```
  Prints all ebooks with indexes, clickable file links (via Rich).

- **Add**:
  ```bash
  ebk add /path/to/lib --title "My Book" --creators "Alice" --ebooks "/path/to/book.pdf"
  ```
  or
  ```bash
  ebk add /path/to/lib --json /path/to/new_entries.json
  ```
  to bulk-add entries from a JSON file.

- **Update**:
  - By index:  
    ```bash
    ebk update-index /path/to/lib 12 --title "New Title"
    ```
  - By unique ID:  
    ```bash
    ebk update-id /path/to/lib <unique_id> --cover /path/to/new_cover.jpg
    ```

- **Remove**:
  - By regex in `title`, `creators`, or `identifiers`:
    ```bash
    ebk remove /path/to/lib "SomeRegex" --apply-to title creators
    ```
  - By index:
    ```bash
    ebk remove-index /path/to/lib 3 4 5
    ```
  - By unique ID:
    ```bash
    ebk remove-id /path/to/lib <unique_id>
    ```

- **Stats**:
  ```bash
  ebk stats /path/to/lib --keywords python data "machine learning"
  ```
  Returns aggregated statistics (common languages, top creators, subject frequency, etc.).

---


## Python API

ebk provides a fluent API for programmatic library management using SQLAlchemy:

```python
from ebk.library_db import Library
from pathlib import Path

# Initialize or open a library
lib = Library.open(Path("~/my-library"))

# Add a book with auto-metadata extraction
book = lib.add_book(
    Path("book.pdf"),
    metadata={
        "title": "Example Book",
        "creators": ["Alice", "Bob"],
        "subjects": ["Fiction", "Adventure"],
        "language": "en"
    },
    extract_text=True,    # Extract full text for FTS
    extract_cover=True    # Extract cover image
)

# Powerful fluent queries
results = (lib.query()
    .filter_by_language("en")
    .filter_by_subject("Python")
    .filter_by_author("Knuth")
    .filter_by_rating(min_rating=4)
    .order_by("title", desc=False)
    .limit(20)
    .all())

# Full-text search (searches across title, description, extracted text)
python_books = lib.search("machine learning", limit=50)

# Get book by ID or unique ID
book = lib.get_book(123)
book = lib.get_book_by_unique_id("isbn_1234567890")

# Update reading status
lib.update_reading_status(book.id, "reading", progress=50, rating=4)

# Get library statistics
stats = lib.stats()
print(f"Total books: {stats['total_books']}")
print(f"Languages: {stats['languages']}")
print(f"Formats: {stats['formats']}")

# Always close when done
lib.close()
```

### Database Access

Direct database access for advanced queries:

```python
from ebk.db import Book, Author, get_session, init_db
from pathlib import Path

# Initialize database
init_db(Path("~/my-library"))
session = get_session()

# SQLAlchemy queries
from sqlalchemy import func

# Get most prolific authors
authors = (session.query(Author, func.count(Book.id))
    .join(Book.authors)
    .group_by(Author.id)
    .order_by(func.count(Book.id).desc())
    .limit(10)
    .all())

session.close()
```

See the [CLAUDE.md](CLAUDE.md) file for architectural details and development guidelines.

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
