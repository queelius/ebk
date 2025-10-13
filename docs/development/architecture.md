# Architecture

ebk's architecture and design patterns.

## Overview

ebk is built around several key architectural principles:

1. **SQLAlchemy ORM** - Database-first design with normalized schema
2. **Service Layer** - Business logic separated from data access
3. **Provider Pattern** - Pluggable LLM and metadata providers
4. **Fluent API** - Method chaining for intuitive queries
5. **Configuration Management** - Centralized settings with CLI overrides

## Core Components

### Database Layer (`ebk/db/`)

**Models** (`models.py`):
- `Book` - Core book entity with metadata
- `Author` - Author information with sort names
- `Subject` - Tags/subjects/categories
- `File` - Physical file records with hash-based deduplication
- `ExtractedText` - Full text from ebooks
- `TextChunk` - Overlapping chunks for semantic search
- `Cover` - Cover images with thumbnails
- `BooksFTS` - FTS5 virtual table for full-text search

**Session Management** (`session.py`):
- Database initialization and schema creation
- FTS5 index setup
- Connection pooling

### Service Layer (`ebk/services/`)

**Import Service** (`import_service.py`):
- Book import with metadata extraction
- Hash-based file deduplication
- Cover extraction and thumbnail generation
- Text extraction coordination

**Text Extraction** (`text_extraction.py`):
- PDF extraction (PyMuPDF, pypdf fallback)
- EPUB extraction (ebooklib)
- Plaintext handling
- Chunking for semantic search

### AI/LLM Layer (`ebk/ai/`)

**LLM Providers** (`llm_providers/`):
- `BaseLLMProvider` - Abstract interface
- `OllamaProvider` - Local and remote Ollama
- Future: OpenAI, Anthropic, MCP providers

**Metadata Enrichment** (`metadata_enrichment.py`):
- Auto-tagging
- Categorization
- Description enhancement
- Difficulty assessment

**Knowledge Graph** (`knowledge_graph.py`):
- NetworkX-based concept graph
- Entity extraction
- Relationship mapping

**Semantic Search** (`semantic_search.py`):
- Vector embeddings
- Similarity search
- Query expansion

### Configuration (`ebk/config.py`)

Four configuration sections:
- `LLMConfig` - Provider, model, host, port, API key
- `ServerConfig` - Host, port, auto-open, page size
- `CLIConfig` - Verbosity, color, page size
- `LibraryConfig` - Default library path

Stored at: `~/.config/ebk/config.json`

### Web Server (`ebk/server.py`)

FastAPI-based REST API:
- Book CRUD operations
- Search and filtering
- Cover serving
- File downloads
- Reading status management

### CLI (`ebk/cli.py`)

Typer-based command-line interface:
- `db-*` commands for library management
- `serve` for web server
- `enrich` for AI metadata enrichment
- `config` for configuration management

## Design Patterns

### Fluent Query API

Method chaining for intuitive queries:

```python
results = (lib.query()
    .filter_by_language("en")
    .filter_by_author("Knuth")
    .order_by("title")
    .limit(20)
    .all())
```

### Hash-Based Deduplication

Files deduplicated using SHA256:
- Same file (same hash) → skipped
- Same book, different format → added as additional format
- Hash-prefixed storage: `files/ab/abc123.pdf`

### Provider Pattern

Swappable LLM backends:

```python
from ebk.ai.llm_providers.ollama import OllamaProvider

# Local Ollama
provider = OllamaProvider.local(model="llama3.2")

# Remote GPU server
provider = OllamaProvider.remote(
    host="192.168.0.225",
    model="llama3.2"
)

async with provider:
    response = await provider.complete("prompt")
```

### Configuration Hierarchy

CLI options > Config file > Defaults:

```python
# Load config with defaults
config = load_config()

# Override from CLI
if cli_host:
    config.server.host = cli_host
```

## Database Schema

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

## Key Technologies

- **SQLAlchemy** - ORM and database toolkit
- **SQLite** with **FTS5** - Database and full-text search
- **FastAPI** - Web framework for REST API
- **Typer** + **Rich** - CLI framework with colored output
- **httpx** - Async HTTP client for LLM providers
- **PyMuPDF** / **pypdf** - PDF text extraction
- **ebooklib** - EPUB parsing
- **Pillow** - Image processing for covers
- **NetworkX** - Graph algorithms for knowledge graph

## Extension Points

1. **LLM Providers** - Implement `BaseLLMProvider`
2. **Plugins** - Use plugin registry in `ebk/plugins/`
3. **Metadata Extractors** - Add to `integrations/metadata/`
4. **Export Formats** - Add to `ebk/exports/`

## See Also

- [Contributing Guide](contributing.md) - How to contribute
- [API Reference](api-reference.md) - Python API documentation
- Source code on [GitHub](https://github.com/queelius/ebk)
