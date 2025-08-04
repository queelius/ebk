# ebk

![ebk Logo](https://github.com/queelius/ebk/blob/main/logo.png?raw=true)

**ebk** is a lightweight and versatile tool for managing eBook metadata. It provides a comprehensive fluent API for programmatic use, a rich Typer-based CLI (with colorized output courtesy of [Rich](https://github.com/Textualize/rich)), supports import/export of libraries from multiple sources (Calibre, raw ebooks, ZIP archives), enables advanced set-theoretic merges, and offers flexible export options including Hugo static sites and symlink-based navigation. 


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
- [Known Issues & TODOs](#known-issues--todos)
- [Stay Updated](#stay-updated)
- [Support](#support)

---

## Features

- **Fluent Python API**: Comprehensive programmatic interface with method chaining, query builders, and batch operations
- **Typer + Rich CLI**: A colorized, easy-to-use, and extensible command-line interface built on top of the fluent API
- **Multiple Import Paths**:
  - Calibre libraries → JSON-based ebk library
  - Raw eBook folders → Basic metadata inference (cover extraction, PDF metadata)
  - Existing ebk libraries in `.zip` format
- **Advanced Metadata Management**:
  - Set-theoretic merges (union, intersect, diff, symdiff)
  - Unique entry identification (hash-based)
  - Automatic cover image extraction
  - Transaction support for atomic operations
- **Flexible Exports**:
  - Export to ZIP archives
  - Hugo-compatible Markdown with multiple organization options (by year, language, subject, creator)
  - Jinja2 template support for customizable export formats
  - Symlink-based DAG navigation for hierarchical tag browsing
- **Integrations** (optional):
  - **Streamlit Dashboard**: Interactive web interface for browsing and filtering
  - **MCP Server**: AI assistant integration via Model Context Protocol
  - **Visualizations**: Network graphs for co-authorship and subject analysis
- **Advanced Search & Query**:
  - Regex pattern matching across any field
  - JMESPath queries for complex filtering
  - Fluent query builder with operators (>, <, contains, regex)
- **Smart Recommendations**: Find similar books based on metadata similarity
- **Batch Operations**: Efficiently process multiple entries at once

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
# Import a Calibre library
ebk import-calibre ~/Calibre/Library --output-dir ~/my-ebk-library

# Search for books
ebk search "Python" ~/my-ebk-library

# Get statistics
ebk stats ~/my-ebk-library

# Export to Hugo site
ebk export hugo ~/my-ebk-library ~/my-hugo-site --jinja --organize-by subject

# Find similar books
ebk similar ~/my-ebk-library book_id_here

# Launch web interface (requires pip install ebk[streamlit])
streamlit run -m ebk.integrations.streamlit.app -- ~/my-ebk-library
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
- `import-zip`
- `import-calibre`
- `import-ebooks`
- `export`
- `merge`
- `search`
- `stats`
- `list`
- `add`
- `remove`
- `remove-index`
- `update-index`
- `update-id`
- `export-dag`
- `recommend`
- `similar`
- …and more!

---

### Importing Libraries

#### Import from Zip (`import-zip`)

Load an existing ebk library archive (which has a `metadata.json` plus eBook/cover files) into a folder:

```bash
ebk import-zip /path/to/ebk_library.zip --output-dir /path/to/output
```

- If `--output-dir` is omitted, the default will be derived from the zip filename.  
- This unpacks the ZIP while retaining the `metadata.json` structure.

#### Import Calibre Library (`import-calibre`)

Convert your [Calibre](https://calibre-ebook.com/) library into an ebk JSON library:

```bash
ebk import-calibre /path/to/calibre/library --output-dir /path/to/output
```

- Extracts metadata from `metadata.opf` files (if present) or from PDF/EPUB fallback.
- Copies ebook files + covers into the output directory, producing a consolidated `metadata.json`.

#### Import Raw Ebooks (`import-ebooks`)

Import a folder of eBooks (PDF, EPUB, etc.) by inferring minimal metadata:

```bash
ebk import-ebooks /path/to/raw/ebooks --output-dir /path/to/output
```

- Uses PyPDF2 for PDF metadata and attempts a best-effort cover extraction (first page → thumbnail).
- Creates `metadata.json` and copies files + covers to `/path/to/output`.

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

ebk provides a comprehensive fluent API for programmatic library management:

```python
from ebk import Library

# Create or open a library
lib = Library.create("/path/to/library")
lib = Library.open("/existing/library")

# Add books with method chaining
lib.add_entry(
    title="Example Book",
    creators=["Alice", "Bob"],
    subjects=["Fiction", "Adventure"],
    language="en"
).save()

# Powerful queries
results = (lib.query()
    .where("language", "en")
    .where("date", "2020", ">=")
    .where("subjects", "Python", "contains")
    .order_by("title")
    .take(10)
    .execute())

# Simple search
python_books = lib.search("Python")

# Filter and export
(lib.filter(lambda e: e.get("rating", 0) >= 4)
    .tag_all("recommended")
    .export_to_hugo("/path/to/site", organize_by="subject"))

# Find similar books
similar = lib.find_similar("book_id_123", threshold=0.7)

# Get recommendations
recommended = lib.recommend(based_on=["book_id_1", "book_id_2"])

# Export as navigable directory structure
lib.export_to_symlink_dag("/path/to/dag", tag_field="subjects")

# Statistics and analysis
stats = lib.stats()
analysis = lib.analyze_reading_patterns()
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
