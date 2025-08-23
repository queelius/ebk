# EBK Design Plan: BTK-Inspired Architecture

## Vision
Transform EBK from a simple ebook metadata manager into a comprehensive, extensible library management system that combines the best features of BTK's bookmark management with EBK's ebook-specific functionality.

## Core Principles

1. **Plugin-First Architecture**: Everything beyond core functionality should be a plugin
2. **Progressive Enhancement**: Start simple, enrich over time
3. **Unix Philosophy**: Core does one thing well, integrations extend functionality
4. **API-First Design**: Pythonic API as foundation, CLI/Web/MCP as clients
5. **Type Safety**: Use type hints and Pydantic models throughout

## Architecture Layers

### 1. Core Layer (ebk.core)
The minimal, essential functionality:
- Data models (Entry, Library, Metadata)
- Basic CRUD operations
- Import/Export interfaces
- Plugin registry and hooks

### 2. Plugin Layer (ebk.plugins)
Abstract base classes and implementations:
```python
# Base interfaces
class MetadataExtractor(ABC)     # Extract metadata from files/URLs
class TagSuggester(ABC)          # Auto-tag entries
class SimilarityFinder(ABC)      # Find similar entries
class ContentAnalyzer(ABC)       # Analyze content (readability, topics)
class Deduplicator(ABC)          # Deduplication strategies
class Validator(ABC)             # Validate entries (file exists, metadata)
```

### 3. API Layer (ebk.api)
Pythonic API for programmatic access:
```python
from ebk import Library, Entry, Query

# Fluent API (existing, to enhance)
lib = Library.open("~/ebooks")
results = (lib
    .where("language", "==", "en")
    .where_any("subjects", contains="Python")
    .order_by("rating", desc=True)
    .take(10)
    .execute())

# New: Async API for web operations
async with AsyncLibrary("~/ebooks") as lib:
    await lib.enrich_metadata(fetch_covers=True)
    await lib.validate_entries(check_files=True)
    
# New: Bulk operations
with lib.batch() as batch:
    batch.tag_all(lambda e: e.year < 2020, "vintage")
    batch.update_where(language="fr", add_tag="french")
    batch.commit()

# New: Plugin API
lib.use_plugin("openai_tagger", api_key="...")
lib.auto_tag(strategy="content_based")
```

### 4. Service Layer (ebk.services)
Higher-level services built on the API:
- REST API server (FastAPI)
- GraphQL server (optional)
- MCP server for AI assistants
- WebSocket server for real-time updates

### 5. Client Layer
Various clients consuming the API:
- CLI (typer/rich)
- Web UI (streamlit/gradio)
- Browser extensions
- Desktop app (future)

## Data Model Evolution

### Current Entry Model
```python
{
    "unique_id": "hash",
    "title": "string",
    "creators": ["list"],
    "subjects": ["list"],
    "language": "string",
    "date": "string",
    "file_paths": ["list"],
    "cover_path": "string"
}
```

### Enhanced Entry Model
```python
class Entry(BaseModel):
    # Core identity
    unique_id: str
    title: str
    creators: List[Creator]  # Enhanced with roles
    
    # Classification
    subjects: List[str]
    tags: List[str]          # User tags
    auto_tags: List[str]     # AI/plugin generated
    categories: List[str]    # Hierarchical
    
    # Metadata
    language: str
    date: datetime
    publisher: Optional[str]
    isbn: Optional[str]
    doi: Optional[str]
    
    # Files
    file_paths: List[FilePath]  # With format info
    cover_path: Optional[str]
    thumbnail_path: Optional[str]
    
    # Usage tracking
    added_date: datetime
    modified_date: datetime
    last_accessed: Optional[datetime]
    access_count: int = 0
    
    # Quality metrics
    rating: Optional[float]      # User rating
    quality_score: Optional[float]  # Auto-calculated
    completeness: float          # Metadata completeness
    validated: bool = False
    validation_errors: List[str] = []
    
    # Personal metadata
    read_status: ReadStatus     # unread/reading/read
    reading_progress: Optional[float]
    notes: Optional[str]
    bookmarks: List[Bookmark]
    highlights: List[Highlight]
    
    # Relationships
    series: Optional[str]
    series_position: Optional[int]
    related_ids: List[str]
    duplicate_ids: List[str]
    
    # Plugin metadata
    plugin_data: Dict[str, Any]  # Extensible
```

## Plugin Architecture Design

### Plugin Discovery
```python
# ebk/plugins/__init__.py
class PluginRegistry:
    def register(self, plugin_type: str, plugin: BasePlugin):
        """Register a plugin."""
    
    def get_plugins(self, plugin_type: str) -> List[BasePlugin]:
        """Get all plugins of a type."""
    
    def discover(self):
        """Auto-discover plugins from installed packages."""
        # Look for entry points: ebk.plugins.*
```

### Hook System
```python
# Lifecycle hooks
@hook("before_import")
def validate_import(entries: List[Entry]) -> List[Entry]:
    """Validate/modify entries before import."""

@hook("after_import")
def enrich_metadata(entries: List[Entry]):
    """Enrich metadata after import."""

@hook("before_export")
def prepare_export(entries: List[Entry], format: str):
    """Prepare entries for export."""

# Event hooks
@hook("entry_added")
@hook("entry_modified")
@hook("entry_deleted")
@hook("tags_suggested")
```

### Built-in Plugins

#### 1. OpenAI Plugin
```python
class OpenAITagger(TagSuggester):
    """Use GPT to suggest tags based on content."""
    
class OpenAISummarizer(ContentAnalyzer):
    """Generate summaries using GPT."""
```

#### 2. Google Books Plugin
```python
class GoogleBooksExtractor(MetadataExtractor):
    """Fetch metadata from Google Books API."""
```

#### 3. Calibre Plugin
```python
class CalibreIntegration:
    """Sync with Calibre libraries."""
```

#### 4. Academic Plugin
```python
class DOIResolver(MetadataExtractor):
    """Resolve DOI to full metadata."""
    
class CitationFormatter:
    """Format citations in various styles."""
```

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Design Pydantic models for all data types
- [ ] Implement plugin registry and discovery
- [ ] Create abstract base classes for plugins
- [ ] Set up hook system
- [ ] Write comprehensive tests

### Phase 2: Core Plugins (Week 3-4)
- [ ] Implement MetadataExtractor plugins
- [ ] Implement TagSuggester plugins
- [ ] Create SimilarityFinder implementations
- [ ] Add Deduplicator strategies
- [ ] Build Validator plugins

### Phase 3: API Layer (Week 5-6)
- [ ] Enhance existing fluent API
- [ ] Add async API for I/O operations
- [ ] Implement batch operations
- [ ] Create transaction support
- [ ] Add query optimization

### Phase 4: Service Layer (Week 7-8)
- [ ] Build FastAPI REST server
- [ ] Implement WebSocket support
- [ ] Update MCP server
- [ ] Add authentication/authorization
- [ ] Create API documentation

### Phase 5: Enhanced CLI (Week 9-10)
- [ ] Restructure with subparsers
- [ ] Add rich terminal output
- [ ] Implement progress bars
- [ ] Add interactive mode
- [ ] Create shell completion

### Phase 6: Web UI (Week 11-12)
- [ ] Modernize Streamlit app
- [ ] Add real-time updates
- [ ] Implement bulk operations UI
- [ ] Create plugin management UI
- [ ] Add data visualization

## Migration Strategy

### Backward Compatibility
- Keep existing CLI commands working
- Provide migration tool for old libraries
- Maintain JSON format compatibility
- Deprecate gradually with warnings

### Migration Tool
```bash
ebk migrate old-library --to v2 --output new-library
```

## Testing Strategy

### Test Levels
1. **Unit Tests**: Every plugin, model, function
2. **Integration Tests**: Plugin interactions, API calls
3. **System Tests**: End-to-end workflows
4. **Performance Tests**: Large library handling
5. **Plugin Tests**: Isolated plugin testing

### Test Data
- Small library (10 entries)
- Medium library (1,000 entries)
- Large library (100,000 entries)
- Various formats and languages
- Corrupted/incomplete data

## Documentation Plan

### User Documentation
- Getting Started Guide
- CLI Reference
- API Documentation
- Plugin Development Guide
- Migration Guide

### Developer Documentation
- Architecture Overview
- Contributing Guide
- Plugin API Reference
- Hook Documentation
- Code Style Guide

## Performance Considerations

### Optimization Areas
1. **Indexing**: Add SQLite FTS5 for search
2. **Caching**: Redis for frequently accessed data
3. **Lazy Loading**: Load metadata on demand
4. **Batch Processing**: Process in chunks
5. **Async I/O**: Non-blocking file operations

### Benchmarks
- Import 10,000 entries: < 10 seconds
- Search 100,000 entries: < 100ms
- Export 10,000 entries: < 5 seconds
- API response time: < 50ms p95

## Security Considerations

### Security Features
- Path traversal prevention
- HTML sanitization
- SQL injection prevention
- API rate limiting
- Authentication tokens
- Encrypted personal data

## Integration Ecosystem

### Planned Integrations
1. **Browser Extensions**: Save from web
2. **E-readers**: Sync with Kindle, Kobo
3. **Cloud Storage**: Google Drive, Dropbox
4. **Academic**: Zotero, Mendeley
5. **Social**: Goodreads, LibraryThing
6. **AI Assistants**: ChatGPT, Claude
7. **Note-taking**: Obsidian, Notion

## Success Metrics

### Technical Metrics
- Test coverage > 90%
- API latency < 50ms
- Plugin adoption > 10
- Zero security vulnerabilities

### User Metrics
- CLI commands < 3 seconds
- Web UI responsive < 100ms
- Import success rate > 99%
- User documentation complete

## Next Steps

1. **Immediate**: Create plugin architecture prototype
2. **Short-term**: Implement core plugins
3. **Medium-term**: Build API and service layers
4. **Long-term**: Develop integration ecosystem

## Questions to Resolve

1. Should we use SQLite for indexing or stay JSON-only?
2. Which plugin should we implement first as proof-of-concept?
3. Should the API be REST-only or include GraphQL?
4. How to handle plugin dependencies?
5. Versioning strategy for plugins?

---

This design plan combines BTK's excellent plugin architecture and API design with EBK's ebook-specific functionality, creating a powerful, extensible library management system.