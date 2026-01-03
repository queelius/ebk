# API Reference

Complete API reference documentation for ebk developers.

## Core Modules

### ebk.library_db

The main `Library` class for all library operations.

```python
from ebk.library_db import Library
```

See [Python API Guide](../user-guide/api.md) for usage examples.

### ebk.db.models

SQLAlchemy ORM models:

- `Book` - Main book entity
- `Author` - Author model
- `Subject` - Subject/category model
- `Tag` - Hierarchical user tags
- `File` - Ebook file records
- `Cover` - Cover images
- `PersonalMetadata` - Reading status, ratings
- `Identifier` - ISBN, DOI, etc.
- `Annotation` - Notes and highlights

### ebk.services

Service layer modules:

- `ImportService` - Book import and metadata extraction
- `ExportService` - Export to JSON, CSV, HTML, OPDS
- `PersonalMetadataService` - Ratings, favorites, reading status
- `TextExtractionService` - Full-text extraction

### ebk.views

View DSL for saved queries:

- `ViewService` - Create, list, evaluate views
- View DSL parser and compiler

### ebk.similarity

Book similarity and recommendations:

- `find_similar_books()` - Find similar books
- TF-IDF and metadata-based similarity

### ebk.plugins

Plugin system:

- `Plugin` - Base plugin class
- `HookRegistry` - Event hooks
- `PluginRegistry` - Plugin discovery

## See Also

- [Python API Guide](../user-guide/api.md) - Detailed API usage
- [Architecture](architecture.md) - System architecture
- [Plugin System](PLUGIN_ARCHITECTURE.md) - Plugin development
