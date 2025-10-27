# EBK Pythonic API Design

## Philosophy

The EBK Pythonic API should be:
- **Intuitive**: Follow Python conventions and idioms
- **Discoverable**: IDE autocomplete should guide users
- **Composable**: Small operations combine into complex workflows
- **Type-Safe**: Full type hints for better IDE support
- **Async-First**: I/O operations should be non-blocking
- **Contextual**: Use context managers for resources

## Core API Examples

### 1. Basic Operations

```python
from ebk import Library, Entry, Query
from ebk.models import Creator, ReadStatus

# Opening libraries
lib = Library.open("~/ebooks")                    # Existing library
lib = Library.create("~/new_ebooks")             # New library
lib = await Library.async_open("~/ebooks")       # Async variant

# Context manager for auto-save
with Library.open("~/ebooks") as lib:
    lib.add(Entry(title="Python Tricks", ...))
    # Auto-saves on exit

# Adding entries - multiple ways
lib.add(Entry(title="Book", creators=["Author"]))
lib.add(title="Book", creators=["Author"])       # Kwargs shortcut
lib.add_from_file("book.epub")                   # Auto-extract metadata
lib.add_from_url("https://...")                  # Download and add

# Batch operations
with lib.batch() as batch:
    for file in Path("~/new_books").glob("*.epub"):
        batch.add_from_file(file)
    # Commits all at once for performance
```

### 2. Query API (Enhanced Fluent Interface)

```python
# Simple queries
books = lib.where("language", "==", "en")
books = lib.where("year", ">", 2020)
books = lib.where("rating", ">=", 4.0)

# Complex queries with chaining
results = (lib
    .where("language", "in", ["en", "es"])
    .where_any("subjects", contains="Python")
    .where_not("read_status", "==", ReadStatus.READ)
    .order_by("rating", desc=True)
    .then_by("date", desc=True)
    .skip(10)
    .take(20)
    .execute())

# Lambda queries for complex logic
results = lib.filter(lambda e: 
    e.rating > 4 and 
    "Python" in e.title and 
    e.year >= 2020
)

# SQL-like syntax (alternative)
results = lib.query("""
    SELECT * FROM entries 
    WHERE language = 'en' 
    AND ANY(subjects, s -> s LIKE '%Python%')
    ORDER BY rating DESC
    LIMIT 20
""")

# Aggregations
stats = (lib
    .group_by("language")
    .aggregate(
        count="count()",
        avg_rating="avg(rating)",
        total_pages="sum(page_count)"
    ))
```

### 3. Entry API (Enhanced)

```python
# Entry creation with builders
entry = (Entry.builder()
    .title("Clean Code")
    .creator("Robert C. Martin", role="author")
    .creator("Timothy Moore", role="narrator")
    .subject("Programming")
    .subject("Software Engineering")
    .language("en")
    .isbn("978-0132350884")
    .build())

# Entry manipulation
entry.add_tag("must-read")
entry.remove_tag("unread")
entry.set_rating(5.0)
entry.mark_as_read()
entry.add_note("Great book on software craftsmanship")

# Relationships
entry.link_to(other_entry, relationship="sequel")
entry.set_series("Clean Code Series", position=1)

# Validation
errors = entry.validate()
if entry.is_valid():
    lib.add(entry)
```

### 4. Metadata Operations

```python
# Auto-enrich metadata using plugins
await lib.enrich_metadata(
    fetch_covers=True,
    extract_isbn=True,
    lookup_google_books=True,
    generate_tags=True
)

# Specific enrichment
entry = lib.get(unique_id)
await entry.fetch_metadata_from("google_books")
await entry.extract_cover()
await entry.generate_thumbnail()

# Bulk metadata operations
await lib.update_all_metadata(
    source="openlibrary",
    overwrite=False,  # Don't overwrite existing
    fields=["description", "subjects", "isbn"]
)
```

### 5. Plugin API

```python
from ebk.plugins import use_plugin, configure_plugin

# Configure plugins globally
configure_plugin("openai", api_key="sk-...")
configure_plugin("google_books", api_key="...")

# Use plugins explicitly
tagger = use_plugin("openai_tagger")
tags = await tagger.suggest_tags(entry)
entry.add_tags(tags)

# Or use them through the library
lib.use_plugin("openai_tagger")
await lib.auto_tag_all()

# Custom plugin
from ebk.plugins import TagSuggester

class MyTagger(TagSuggester):
    def suggest_tags(self, entry: Entry) -> List[str]:
        # Custom logic
        return ["tag1", "tag2"]

lib.register_plugin(MyTagger())
```

### 6. Import/Export API

```python
# Import with options
from ebk.importers import CalibreImporter, EPUBImporter

imported = await lib.import_from(
    "~/Calibre Library",
    importer=CalibreImporter(),
    merge_strategy="skip_duplicates",
    auto_tag=True,
    validate=True
)

# Progressive import with callbacks
def on_progress(current, total, entry):
    print(f"Importing {current}/{total}: {entry.title}")

await lib.import_directory(
    "~/ebooks",
    recursive=True,
    formats=["epub", "pdf", "mobi"],
    on_progress=on_progress,
    on_error="skip"  # or "stop" or callback
)

# Export with templates
from ebk.exporters import HugoExporter, JSONExporter

await lib.export_to(
    "~/website/content",
    exporter=HugoExporter(
        template="academic",
        group_by="year",
        create_indices=True
    )
)

# Streaming export for large libraries
async with lib.export_stream("huge_library.json") as stream:
    async for batch in stream.batches(size=100):
        await process_batch(batch)
```

### 7. Search and Similarity

```python
# Full-text search
results = await lib.search(
    "machine learning",
    fields=["title", "description", "content"],
    fuzzy=True,
    max_distance=2
)

# Semantic search (with embeddings)
lib.use_plugin("semantic_search")
similar = await lib.find_similar_to(
    entry,
    threshold=0.8,
    limit=10,
    method="embeddings"  # or "tf-idf", "jaccard"
)

# Recommendations
recs = await lib.recommend_for_user(
    based_on=["read_history", "ratings"],
    algorithm="collaborative",  # or "content", "hybrid"
    limit=20
)

# Duplicate detection
duplicates = lib.find_duplicates(
    strategy="fuzzy_title",  # or "isbn", "content_hash"
    threshold=0.9
)
```

### 8. Async Operations

```python
import asyncio
from ebk import AsyncLibrary

async def process_library():
    async with AsyncLibrary("~/ebooks") as lib:
        # Concurrent operations
        tasks = [
            lib.fetch_cover(entry.id) 
            for entry in await lib.where("cover_path", "==", None)
        ]
        covers = await asyncio.gather(*tasks)
        
        # Async iteration
        async for entry in lib.iter_entries(batch_size=100):
            await process_entry(entry)
        
        # Async transactions
        async with lib.transaction() as tx:
            await tx.add_many(entries)
            await tx.remove_where(lambda e: e.year < 2000)
            # Commits on success, rollbacks on exception
```

### 9. Event System

```python
from ebk.events import on, emit

# Register event handlers
@on("entry.added")
async def on_entry_added(entry: Entry):
    print(f"New entry: {entry.title}")
    await generate_thumbnail(entry)

@on("entry.rating_changed")
def on_rating_changed(entry: Entry, old_rating: float, new_rating: float):
    if new_rating == 5.0:
        entry.add_tag("favorite")

# Custom events
emit("custom.event", data={"key": "value"})

# Event context
with lib.events_disabled():
    # Operations here don't trigger events
    lib.bulk_update(...)
```

### 10. Advanced Features

```python
# Virtual collections (views without copying)
fiction = lib.create_view(
    "fiction",
    filter=lambda e: "Fiction" in e.subjects
)

# Computed fields
lib.add_computed_field(
    "reading_time",
    lambda e: e.page_count / 250  # pages per hour
)

# Indexing for performance
lib.create_index("title")
lib.create_index("subjects", type="fulltext")

# Caching
lib.enable_cache(backend="redis", ttl=3600)

# Transactions
with lib.transaction() as tx:
    tx.add(entry1)
    tx.update(entry2)
    tx.delete(entry3)
    # All or nothing

# Migrations
from ebk.migrations import migrate

migrate(lib, from_version="1.0", to_version="2.0")

# Backup and restore
backup = lib.create_backup()
lib.restore_from(backup)

# Diff and merge
diff = lib1.diff(lib2)
merged = lib1.merge(lib2, strategy="union")
```

### 11. Integration with DataFrames

```python
import pandas as pd
import polars as pl

# Export to DataFrame
df = lib.to_pandas()
df = lib.to_polars()

# Query using DataFrame operations
df = lib.to_pandas()
python_books = df[df['subjects'].apply(lambda x: 'Python' in x)]

# Import from DataFrame
lib.from_pandas(df)
lib.from_polars(df)

# Use SQL via DuckDB
import duckdb
conn = duckdb.connect()
conn.register("books", lib.to_pandas())
result = conn.execute("""
    SELECT title, rating 
    FROM books 
    WHERE rating > 4 
    ORDER BY date DESC
""").fetchdf()
```

### 12. CLI Integration

```python
# Expose any function as CLI command
from ebk.cli import command

@command
def analyze_reading_patterns(lib_dir: str, output: str = "patterns.json"):
    """Analyze reading patterns in library."""
    lib = Library.open(lib_dir)
    patterns = lib.analyze_patterns()
    patterns.save(output)

# Auto-generates: ebk analyze-reading-patterns ~/ebooks --output patterns.json
```

## Type System

```python
from typing import TypedDict, Literal, Protocol
from pydantic import BaseModel, Field

# Type definitions
class EntryDict(TypedDict):
    unique_id: str
    title: str
    creators: List[str]
    # ... other fields

# Pydantic models for validation
class EntryModel(BaseModel):
    unique_id: str = Field(..., min_length=32, max_length=64)
    title: str = Field(..., min_length=1, max_length=500)
    creators: List[Creator] = Field(default_factory=list)
    rating: Optional[float] = Field(None, ge=0, le=5)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

# Protocols for duck typing
class Searchable(Protocol):
    def search(self, query: str) -> List[Entry]: ...

class Taggable(Protocol):
    def add_tag(self, tag: str) -> None: ...
    def remove_tag(self, tag: str) -> None: ...
```

## Error Handling

```python
from ebk.exceptions import (
    LibraryNotFoundError,
    EntryNotFoundError, 
    ValidationError,
    DuplicateEntryError,
    PluginError
)

# Specific exceptions
try:
    lib = Library.open("~/ebooks")
except LibraryNotFoundError as e:
    print(f"Library not found: {e.path}")

# Validation errors with details
try:
    entry.validate()
except ValidationError as e:
    for error in e.errors:
        print(f"{error.field}: {error.message}")

# Async error handling
async def safe_import(path):
    try:
        await lib.import_from(path)
    except ImportError as e:
        await lib.log_error(e)
        return None
```

## Performance Patterns

```python
# Lazy loading
lib = Library.open("~/ebooks", lazy=True)
# Metadata loaded on demand

# Prefetching
entries = lib.where("year", ">", 2020).prefetch("content", "cover")

# Chunking
for chunk in lib.chunks(size=100):
    process_chunk(chunk)

# Parallel processing
from concurrent.futures import ProcessPoolExecutor

with ProcessPoolExecutor() as executor:
    results = executor.map(process_entry, lib.entries)

# Streaming
async for entry in lib.stream():
    await process(entry)
```

## Testing Utilities

```python
from ebk.testing import LibraryFactory, EntryFactory

# Test fixtures
def test_search():
    lib = LibraryFactory.create(size=100)
    entry = EntryFactory.create(title="Test Book")
    lib.add(entry)
    
    results = lib.search("Test")
    assert len(results) == 1

# Mocking
from ebk.testing import mock_plugin

with mock_plugin("openai_tagger") as mock:
    mock.suggest_tags.return_value = ["tag1", "tag2"]
    tags = lib.auto_tag(entry)
    assert tags == ["tag1", "tag2"]
```

This Pythonic API design provides a comprehensive, intuitive interface for working with EBK libraries programmatically, serving as the foundation for all other interfaces (CLI, Web, API).