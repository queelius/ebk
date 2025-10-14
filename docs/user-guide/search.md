# Search & Query

ebk provides powerful search capabilities with field-specific queries, boolean logic, and full-text search powered by SQLite FTS5.

## Quick Start

```bash
# Simple full-text search
ebk search "machine learning" ~/my-library

# Field-specific search
ebk search "title:Python rating:>=4" ~/my-library

# Multiple criteria
ebk search "author:Knuth format:pdf" ~/my-library
```

## Advanced Search Syntax

### Field-Specific Searches

Search within specific fields using `field:value` syntax:

| Field | Description | Example |
|-------|-------------|---------|
| `title:` | Search in book titles | `title:Python` |
| `author:` | Search by author name | `author:Knuth` |
| `tag:` or `subject:` | Search subjects/tags | `tag:programming` |
| `description:` | Search in book descriptions | `description:algorithms` |
| `text:` | Search in extracted text | `text:recursion` |
| `series:` | Search by series name | `series:TAOCP` |

**Examples:**

```bash
# Books with "intelligence" in the title
ebk search "title:intelligence" ~/my-library

# Books by Donald Knuth
ebk search "author:Knuth" ~/my-library

# Books tagged with "programming"
ebk search "tag:programming" ~/my-library

# Search book descriptions for "algorithm"
ebk search "description:algorithm" ~/my-library
```

### Filter Fields

Apply exact filters using the same syntax:

| Filter | Description | Example |
|--------|-------------|---------|
| `language:` | Filter by language code | `language:en` |
| `format:` | Filter by file format | `format:pdf` |
| `rating:` | Filter by rating (with operators) | `rating:>=4` |
| `favorite:` | Filter favorites only | `favorite:true` |
| `status:` | Filter by reading status | `status:reading` |

**Examples:**

```bash
# English books only
ebk search "python language:en" ~/my-library

# PDF files only
ebk search "algorithms format:pdf" ~/my-library

# Books rated 4 stars or higher
ebk search "title:learning rating:>=4" ~/my-library

# Favorite books
ebk search "programming favorite:true" ~/my-library
```

### Rating Comparisons

The `rating:` filter supports comparison operators:

```bash
rating:5           # Exactly 5 stars
rating:>=4         # 4 stars or higher
rating:>3          # Greater than 3 stars
rating:<4          # Less than 4 stars
rating:3-5         # Between 3 and 5 stars (range)
```

**Examples:**

```bash
# Highly rated Python books
ebk search "title:Python rating:>=4" ~/my-library

# Books rated between 3 and 4 stars
ebk search "rating:3-4" ~/my-library
```

### Boolean Operators

Combine search terms with boolean logic:

| Operator | Behavior | Example |
|----------|----------|---------|
| (space) | Implicit AND | `python programming` |
| `OR` | Explicit OR | `python OR java` |
| `NOT` | Exclude term | `programming NOT java` |
| `-` prefix | Exclude (shorthand) | `programming -java` |

**Examples:**

```bash
# Books about both Python AND machine learning
ebk search "python machine learning" ~/my-library

# Books about Python OR JavaScript
ebk search "python OR javascript" ~/my-library

# Programming books excluding Java
ebk search "programming NOT java" ~/my-library

# Same as above, using shorthand
ebk search "programming -java" ~/my-library
```

### Phrase Searches

Use quotes for exact phrase matching:

```bash
# Exact phrase
ebk search '"machine learning"' ~/my-library

# Phrase in specific field
ebk search 'title:"deep learning"' ~/my-library

# Phrase with filters
ebk search '"artificial intelligence" language:en format:pdf' ~/my-library
```

### Combined Queries

Mix field searches, filters, and boolean logic:

```bash
# Python books, 4+ stars, PDF format
ebk search "title:Python rating:>=4 format:pdf" ~/my-library

# Books by Knuth in his TAOCP series
ebk search "author:Knuth series:TAOCP" ~/my-library

# Favorite programming books (not Java)
ebk search "tag:programming favorite:true NOT java" ~/my-library

# Machine learning books in English, highly rated
ebk search '"machine learning" language:en rating:>=4' ~/my-library
```

## Full-Text Search (FTS5)

ebk uses SQLite FTS5 for fast full-text indexing across:

- **Book titles**
- **Descriptions**
- **Extracted text** from PDFs, EPUBs, and plaintext files

The FTS5 engine provides:

- **Porter stemming**: Searches for "running" also match "run", "runs", etc.
- **Unicode support**: Full support for international characters
- **Ranking**: Results ordered by relevance
- **Fast performance**: Indexed searches even on large libraries

## Search in Different Contexts

### CLI Search

```bash
# Basic search
ebk search "query" ~/my-library

# Limit results
ebk search "query" ~/my-library --limit 20
```

### Web Server Search

The web server (`ebk serve`) provides advanced search via REST API:

```bash
# Start server
ebk serve ~/my-library

# Search via API
curl "http://localhost:8000/api/search?q=title:Python+rating:>=4"
```

The web UI includes a search bar with the same advanced syntax.

### Python API

```python
from ebk.library_db import Library
from pathlib import Path

lib = Library.open(Path("~/my-library"))

# Simple search
results = lib.search("machine learning", limit=50)

# Advanced search
results = lib.search("title:Python rating:>=4 format:pdf", limit=50)

for book in results:
    print(f"{book.title} by {', '.join(a.name for a in book.authors)}")

lib.close()
```

## Search Limitations

**HTML Export**: The exported HTML files use **client-side JavaScript filtering**, not the advanced search parser. For advanced search features, use:

- CLI: `ebk search`
- Web server: `ebk serve`
- Python API: `Library.search()`

## Tips and Best Practices

1. **Start broad, refine**: Begin with simple queries, then add filters
2. **Use field searches**: More precise than full-text when you know what field to search
3. **Combine filters**: Multiple filters are ANDed together by default
4. **Quote phrases**: Always quote multi-word phrases for exact matching
5. **Test queries**: Use `--limit 5` when testing complex queries

## See Also

- [CLI Reference](cli.md) - Full command documentation
- [Server](server.md) - Web server search API
