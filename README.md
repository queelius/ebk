Below is an **updated** `README.md` that reflects the current codebase—including the Typer-based CLI, advanced search options (regex & JMESPath), `import-zip`, future LLM integration notes, and other recent additions.

```markdown
# ebk

![ebk Logo](https://github.com/queelius/ebk/blob/main/logo.png?raw=true)

**ebk** is a lightweight and versatile tool for managing eBook metadata. It provides a rich Typer-based CLI (with colorized output courtesy of [Rich](https://github.com/Textualize/rich)), supports import/export of libraries from multiple sources (Calibre, raw ebooks, ZIP archives), enables advanced set-theoretic merges, and offers an interactive Streamlit web dashboard. 

> **Note**: We have future plans to integrate Large Language Model (LLM) features for automated tagging, summarization, and metadata generation—stay tuned!

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
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
  - [Launch Streamlit Dashboard](#launch-streamlit-dashboard)
- [Streamlit Dashboard Usage](#streamlit-dashboard-usage)
- [Library Management Class (Python API)](#library-management-class-python-api)
- [Future LLM Integration](#future-llm-integration)
- [Contributing](#contributing)
- [License](#license)
- [Known Issues & TODOs](#known-issues--todos)
- [Stay Updated](#stay-updated)
- [Support](#support)

---

## Features

- **Typer + Rich CLI**: A colorized, easy-to-use, and extensible command-line interface.
- **Multiple Import Paths**:
  - Calibre libraries → JSON-based ebk library
  - Raw eBook folders → Basic metadata inference (cover extraction, PDF metadata)
  - Existing ebk libraries in `.zip` format
- **Advanced Metadata**:
  - Set-theoretic merges (union, intersect, diff, symdiff)
  - Unique entry identification (hash-based)
  - Automatic cover image extraction
- **Flexible Exports**:
  - Export to ZIP
  - Hugo-compatible Markdown for static site integration
- **Streamlit Dashboard**:
  - Interactive web interface for browsing, filtering, and managing your eBook library
  - Search by title, author, subjects, language, etc.
  - Download eBooks from the dashboard
- **Regex & JMESPath Searching**: Perform advanced queries on your metadata (CLI + Streamlit).
- **(Planned) LLM Extensions**: Automatic summarization, tagging, or classification using large language models.

---

## Installation

1. **Clone the Repository**

   ```bash
   git clone https://github.com/queelius/ebk.git
   cd ebk
   ```

2. **(Optional) Create a Virtual Environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # (On Windows: venv\Scripts\activate)
   ```

3. **Install Dependencies & `ebk`**

   ```bash
   pip install -r requirements.txt
   pip install .
   ```

> **Note**: You need Python 3.7+.

---

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
- `dash`
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
  ebk export hugo /path/to/ebk_library /path/to/hugo_site
  ```
  This writes Hugo-compatible Markdown files (and copies covers/ebooks) into your Hugo `content` + `static` folders.

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

### Launch Streamlit Dashboard

```bash
ebk dash --port 8501
```

- By default, the dashboard runs at `http://localhost:8501`.

---

## Streamlit Dashboard Usage

1. **Prepare a ZIP Archive**  
   From any ebk library folder (containing `metadata.json`), compress the entire folder into a `.zip`. Or use:
   ```bash
   ebk export zip /path/to/lib /path/to/lib.zip
   ```

2. **Upload it** via the Streamlit interface (`ebk dash`).
3. **Browse & Filter** your library:
   - Advanced filtering (author, subject, language, year, etc.).
   - View cover images, descriptions, and download eBooks.
   - JMESPath-based advanced search in the “Advanced Search” tab.
4. **Enjoy** a modern, interactive interface for eBook exploration.

---

## Library Management Class (Python API)

For programmatic usage, `ebk` includes a simple `LibraryManager` class:

```python
from ebk.manager import LibraryManager

manager = LibraryManager("metadata.json")

# List all books
all_books = manager.list_books()

# Add a book
manager.add_book({
    "Title": "Example Book",
    "Author": "Alice",
    "Tags": "fiction"
})

# Delete or update
manager.delete_book("Old Title")
manager.update_book("Example Book", {"Tags": "fiction, fantasy"})
```

---

## Future LLM Integration

We plan to integrate optional **Large Language Model (LLM)** functionalities for:
- Automatic summarization of eBooks or chapters
- Generating or refining metadata
- Auto-tagging with relevant subjects or categories

Keep an eye on our [GitHub issues](https://github.com/queelius/ebk/issues) or the “Future Plans” section for announcements.

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

## Known Issues & TODOs

1. **Exporter Module**:
   - Switch from `os.system` to `shutil` for safer file operations
   - Expand supported eBook formats & metadata fields
2. **Merger Module**:
   - Resolve conflicts automatically or allow user-specified conflict resolution
   - Performance optimization for large libraries
3. **Consistent Entry Identification**:
   - Support multiple eBook files per entry seamlessly
   - Improve hash-based deduplication for large files
4. **LLM-Based Metadata** _(Planned)_:
   - Summaries or tags automatically generated via language models
   - Potential GPU/accelerator support for on-device inference

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
```

Feel free to adjust the wording or add/remove details as needed. This version incorporates:

- **Typer-based CLI** details (including advanced subcommands).
- **Regex & JMESPath** searching.
- **LLM** mention for future roadmap.
- **Import from ZIP** usage example.
- **Rich**-based fancy outputs in the CLI.
- References to known issues, performance ideas, and future expansions.