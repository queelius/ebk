# CLI Reference

Complete reference for all ebk commands.

## Global Options

```bash
ebk --help              # Show help
ebk --verbose           # Enable verbose output
ebk --version           # Show version
```

## Library Management Commands

### init

Initialize a new library:

```bash
ebk init <library-path>
```

Creates a new ebk library with database and directory structure.

### import

Import ebook files:

```bash
ebk import <file> <library-path>
ebk import <file1> <file2> ... <library-path>
ebk import ~/books/*.pdf <library-path>
```

Options:
- `--extract-text` - Extract text for FTS (default: true)
- `--extract-cover` - Extract cover image (default: true)
- `--recursive` - Import directories recursively

### import-calibre

Import from Calibre library:

```bash
ebk import-calibre <calibre-library> --output <ebk-library>
```

Options:
- `--output` - Output library path (required)
- `--formats` - File formats to import (default: all)

### list

List books in library:

```bash
ebk list <library-path>
```

Options:
- `--author <name>` - Filter by author
- `--language <code>` - Filter by language (e.g., en, de)
- `--format <format>` - Filter by file format (pdf, epub, mobi)
- `--rating <number>` - Filter by minimum rating (0-5)
- `--tag <tag>` - Filter by personal tag
- `--limit <number>` - Limit results (default: 50)
- `--sort-by <field>` - Sort by field (title, author, date, rating)
- `--format json` - Output as JSON

### search

Full-text search:

```bash
ebk search <query> <library-path>
```

Searches across:
- Book title
- Description
- Extracted text content

Options:
- `--fields <field1,field2>` - Limit search to specific fields
- `--language <code>` - Filter by language
- `--author <name>` - Filter by author
- `--limit <number>` - Limit results

### stats

Show library statistics:

```bash
ebk stats <library-path>
```

Options:
- `--format json` - Output as JSON

Displays:
- Total books, authors, subjects
- File formats and counts
- Languages
- Storage size

## Reading Management

### rate

Rate a book:

```bash
ebk rate <library-path> <book-id> <rating>
```

Rating: 0-5 (0 = unrated)

### favorite

Toggle favorite status:

```bash
ebk favorite <library-path> <book-id>
```

### tag

Manage personal tags:

```bash
# Add tags
ebk tag <library-path> <book-id> --add "tag1" "tag2"

# Remove tags
ebk tag <library-path> <book-id> --remove "tag1"

# List tags
ebk tag <library-path> <book-id> --list
```

### purge

Remove books from library:

```bash
ebk purge <library-path> [options]
```

Options:
- `--rating <n>` - Remove books with rating <= n
- `--unread` - Remove unread books
- `--format <fmt>` - Remove specific format
- `--confirm` - Skip confirmation prompt

**Warning:** This permanently removes books!

## Web Server

### serve

Start web server:

```bash
ebk serve <library-path>
```

Options:
- `--host <host>` - Bind address (default: from config)
- `--port <port>` - Port number (default: from config)
- `--auto-open` - Open browser automatically

## AI-Powered Features

### enrich

Enrich metadata using LLM:

```bash
ebk enrich <library-path>
```

Options:
- `--generate-tags` - Generate descriptive tags
- `--categorize` - Assign hierarchical categories
- `--enhance-descriptions` - Improve descriptions
- `--assess-difficulty` - Determine reading level
- `--book-id <id>` - Enrich specific book
- `--host <host>` - LLM server host
- `--model <model>` - LLM model name
- `--dry-run` - Preview changes without saving
- `--batch-size <n>` - Process n books at a time

## Configuration

### config

Manage configuration:

```bash
# Initialize
ebk config init

# View all
ebk config show

# View section
ebk config show --section llm

# Edit
ebk config edit

# Set value
ebk config set <key> <value>

# Get value
ebk config get <key>
```

Configuration keys:
- `llm.provider` - LLM provider (ollama, openai)
- `llm.model` - Model name
- `llm.host` - Server host
- `llm.port` - Server port
- `llm.temperature` - Sampling temperature
- `server.host` - Web server host
- `server.port` - Web server port
- `server.auto_open_browser` - Auto-open browser
- `server.page_size` - Results per page
- `cli.verbose` - Verbose output
- `cli.color` - Colored output
- `library.default_path` - Default library path

## Export and Utilities

### export

Export library:

```bash
# Export to ZIP
ebk export zip <library-path> <output.zip>

# Export to JSON
ebk export json <library-path> <output.json>
```

### vlib

Manage virtual libraries (filtered views):

```bash
# Create virtual library
ebk vlib create <library-path> <name> [filters]

# List virtual libraries
ebk vlib list <library-path>

# Delete virtual library
ebk vlib delete <library-path> <name>
```

### note

Manage book notes and annotations:

```bash
# Add note
ebk note add <library-path> <book-id> "<note text>"

# List notes
ebk note list <library-path> <book-id>

# Delete note
ebk note delete <library-path> <note-id>
```

### view

View book content:

```bash
ebk view <library-path> <book-id>
```

Opens the book in the default application for its format.

### about

Show information about ebk:

```bash
ebk about
```

Displays version, installation path, and configuration location.

## Examples

### Import and Organize

```bash
# Create library
ebk init ~/my-library

# Import Calibre collection
ebk import-calibre ~/Calibre/Library --output ~/my-library

# Import additional files
ebk import ~/Downloads/*.pdf ~/my-library

# Generate tags
ebk enrich ~/my-library --generate-tags
```

### Search and Filter

```bash
# Search for Python books
ebk search "Python programming" ~/my-library

# List highly rated books
ebk list ~/my-library --rating 4

# Find books by Knuth
ebk list ~/my-library --author Knuth
```

### Web Interface Workflow

```bash
# Configure server
ebk config set server.port 8000
ebk config set server.auto_open_browser true

# Start server
ebk serve ~/my-library

# Browse at http://localhost:8000
```

### Batch Processing

```bash
# Import multiple directories
find ~/Downloads -name "*.pdf" -exec ebk import {} ~/my-library \;

# Enrich all books
ebk enrich ~/my-library --generate-tags --categorize --batch-size 10

# Export for backup
ebk export zip ~/my-library ~/backup-$(date +%Y%m%d).zip
```

## See Also

- [Configuration Guide](../getting-started/configuration.md) - Configure defaults
- [LLM Features](llm-features.md) - AI-powered enrichment
- [Web Server](server.md) - Web interface details
- [Python API](api.md) - Programmatic access
