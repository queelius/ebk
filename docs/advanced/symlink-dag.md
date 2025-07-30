# Symlink DAG Export Documentation

The symlink DAG (Directed Acyclic Graph) export feature creates a navigable directory structure that represents your library's tag hierarchy using symbolic links. This allows you to browse your ebook collection through tag categories using any file explorer or command line interface.

## Overview

The symlink DAG export transforms your flat library structure into a hierarchical directory tree where:
- Each tag becomes a directory
- Hierarchical tags (e.g., "Programming/Python/Web") create nested directories
- Books appear in all relevant tag directories via symbolic links
- The actual files are stored in a central `_books` directory

## Usage

### Command Line

```bash
# Basic export
ebk export-dag /path/to/library /path/to/output

# Use a different field for categorization (default: subjects)
ebk export-dag /path/to/library /path/to/output --tag-field creators

# Skip copying actual files (only create symlinks to metadata)
ebk export-dag /path/to/library /path/to/output --no-files

# Skip HTML index generation
ebk export-dag /path/to/library /path/to/output --no-index
```

### Python API

```python
from ebk import Library

lib = Library.open("/path/to/library")

# Basic export
lib.export_to_symlink_dag("/path/to/output")

# Custom options
lib.export_to_symlink_dag(
    "/path/to/output",
    tag_field="creators",  # Organize by authors instead of subjects
    include_files=False,   # Don't copy ebook files
    create_index=True      # Generate HTML indexes for web browsing
)

# Chain with other operations
(lib.filter(lambda e: e.get("language") == "en")
    .export_to_symlink_dag("/english-books-dag"))
```

## Directory Structure

### Example Library

Given a library with these books:
1. "Learn Python" - Tags: ["Programming", "Programming/Python", "Education"]
2. "Django Web Development" - Tags: ["Programming/Python/Web", "Web Development"]
3. "Machine Learning Basics" - Tags: ["Programming/Python", "AI/Machine Learning"]

### Generated Structure

```
output-directory/
├── README.md                      # Explains the structure
├── _books/                        # Actual files stored here
│   ├── book_id_1/
│   │   ├── metadata.json
│   │   ├── learn_python.pdf
│   │   └── cover.jpg
│   ├── book_id_2/
│   │   ├── metadata.json
│   │   └── django_web_dev.epub
│   └── book_id_3/
│       ├── metadata.json
│       └── ml_basics.pdf
├── Programming/
│   ├── index.html                 # Web index for this level
│   ├── Learn Python → ../../_books/book_id_1
│   ├── Python/
│   │   ├── index.html
│   │   ├── Learn Python → ../../../_books/book_id_1
│   │   ├── Machine Learning Basics → ../../../_books/book_id_3
│   │   └── Web/
│   │       ├── index.html
│   │       └── Django Web Development → ../../../../_books/book_id_2
├── Education/
│   ├── index.html
│   └── Learn Python → ../../_books/book_id_1
├── Web Development/
│   ├── index.html
│   └── Django Web Development → ../../_books/book_id_2
└── AI/
    ├── index.html
    └── Machine Learning/
        ├── index.html
        └── Machine Learning Basics → ../../../_books/book_id_3
```

## Features

### Hierarchical Tag Support

Tags containing "/" are treated as hierarchical:
- "Programming/Python/Web" creates three nested levels
- Books are accessible at each level of the hierarchy
- Allows natural drill-down navigation

### Multiple Tag Appearances

Books appear in multiple locations:
- A book tagged with ["Programming", "Education"] appears in both directories
- Symlinks ensure no file duplication
- Changes to files are reflected everywhere

### Web Navigation

When `create_index` is enabled:
- Each directory contains an `index.html` file
- Browse the structure in a web browser
- Navigate between parent/child categories
- Direct links to open book directories

### Readable Names

Symlinks use human-readable names:
- Format: "Title - First Author"
- Sanitized for filesystem compatibility
- Actual files stored by ID in `_books`

## Navigation Methods

### File Explorer
- Open the output directory in Finder, Windows Explorer, or any file manager
- Navigate through categories like regular folders
- Open books by following symlinks

### Command Line
```bash
# Navigate the structure
cd /path/to/output
cd Programming/Python
ls

# Find all Python books
find . -name "*.pdf" -path "*/Python/*"
```

### Web Browser
```bash
# Open in default browser
open /path/to/output/index.html  # macOS
xdg-open /path/to/output/index.html  # Linux
start /path/to/output/index.html  # Windows

# Or open file:// URL directly
```

## Platform Considerations

### Linux/macOS
- Symlinks work natively
- No special permissions required
- Full support for all features

### Windows
- Requires administrator privileges to create symlinks
- Or enable Developer Mode (Windows 10+)
- Alternative: Use WSL (Windows Subsystem for Linux)