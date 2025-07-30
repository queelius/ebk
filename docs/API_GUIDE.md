# ebk Fluent API Guide

The ebk library provides a comprehensive, fluent API for programmatic ebook library management.

## Quick Start

```python
from ebk import Library

# Open or create a library
lib = Library.open("/path/to/library")
# or
lib = Library.create("/path/to/new/library")

# Add books
lib.add_entry(
    title="The Python Book",
    creators=["John Doe", "Jane Smith"],
    subjects=["Programming", "Python"],
    language="en",
    date="2023-01-15"
).save()

# Search and query
python_books = lib.search("Python")
recent_books = lib.query().where("date", "2023", ">=").execute()
```

## Core Concepts

### Library

The `Library` class is the main entry point for all operations:

```python
from ebk import Library

# Create from different sources
lib = Library.create("/path/to/library")
lib = Library.from_calibre("/calibre/library", "/output/path")
lib = Library.from_ebooks("/ebooks/folder", "/output/path")

# Basic operations
print(f"Library has {len(lib)} entries")

# Iterate over entries
for entry in lib:
    print(f"{entry.title} by {', '.join(entry.creators)}")
```

### Entry

Individual books are represented as `Entry` objects with fluent methods:

```python
# Get an entry
entry = lib[0]  # By index
entry = lib.find("unique-id-here")  # By ID

# Access properties
print(entry.title)
print(entry.creators)
print(entry.subjects)

# Modify with chaining
entry.set("publisher", "Tech Press") \
     .add_creator("Co Author") \
     .add_subject("Advanced Topics") \
     .save()

# Update multiple fields
entry.update(
    edition="2nd",
    pages=450,
    isbn="978-1234567890"
)
```

### QueryBuilder

The query builder provides powerful, chainable search capabilities:

```python
# Simple queries
english_books = lib.query().where("language", "en").execute()

# Complex queries with operators
results = (lib.query()
    .where("language", "en")
    .where("date", "2020", ">=")
    .where("subjects", "Python", "contains")
    .order_by("title")
    .take(10)
    .execute())

# Custom filters
results = lib.query().where_lambda(
    lambda e: len(e.get("creators", [])) > 1 and e.get("pages", 0) > 300
).execute()

# Search across multiple fields
results = lib.query().where_any(
    ["title", "description", "subjects"], 
    "machine learning"
).execute()

# Count and existence
count = lib.query().where("language", "en").count()
has_french = lib.query().where("language", "fr").exists()
first_match = lib.query().where("publisher", "O'Reilly").first()
```

## Common Operations

### Adding Books

```python
# Single entry
entry = lib.add_entry(
    title="Deep Learning",
    creators=["Ian Goodfellow", "Yoshua Bengio"],
    subjects=["AI", "Machine Learning", "Neural Networks"],
    language="en",
    date="2016-11-18",
    isbn="9780262035613",
    publisher="MIT Press"
)

# Multiple entries
entries = [
    {"title": "Book 1", "creators": ["Author 1"]},
    {"title": "Book 2", "creators": ["Author 2"]}
]
lib.add_entries(entries).save()

# From files (requires actual file handling)
entry = lib.add_entry(
    title="My Book",
    creators=["Me"],
    file_paths=["book.pdf", "book.epub"],
    cover_path="cover.jpg"
)
```

### Searching and Filtering

```python
# Simple text search
results = lib.search("Python")
results = lib.search("Doe", fields=["creators"])

# Find specific entries
books = lib.find_by_title("Python Programming")
entry = lib.find("unique-id-123")

# Filter with predicates
filtered = lib.filter(lambda e: e.get("year", 0) > 2020)
python_books = lib.filter(lambda e: "Python" in e.get("subjects", []))

# Query builder for complex searches
query = (lib.query()
    .where("language", "en")
    .where("subjects", "Programming", "contains")
    .where_lambda(lambda e: e.get("pages", 0) > 200)
    .order_by("date", descending=True))

results = query.execute()
count = query.count()
first = query.first()
```

### Modifying Entries

```python
# Update single entry
entry = lib.find("some-id")
entry.title = "Updated Title"
entry.add_creator("New Author")
entry.add_subject("New Topic")
entry.save()

# Update multiple entries
lib.update_all(lambda e: e.set("reviewed", True))
lib.update_all(lambda e: e.add_subject("ebook") if e.get("format") == "pdf" else None)

# Batch tagging
lib.tag_all("to-read")
lib.filter(lambda e: e.get("year") == "2023").tag_all("recent")

# Remove entries
lib.remove("unique-id")
lib.remove_where(lambda e: e.get("language") == "unknown")
```

### Batch Operations

```python
# Queue multiple operations
(lib.batch()
    .add_entry(title="Book 1", creators=["Author 1"])
    .add_entry(title="Book 2", creators=["Author 2"])
    .update("some-id", publisher="New Publisher")
    .remove("old-id")
    .execute())
```

### Transactions

```python
# Automatic rollback on error
try:
    with lib.transaction() as txn_lib:
        txn_lib.add_entry(title="Book 1", creators=["Author"])
        txn_lib.remove("some-id")
        # If error occurs here, all changes are rolled back
        raise Exception("Something went wrong")
except:
    # Library remains unchanged
    pass
```

## Advanced Features

### Merging Libraries

```python
lib1 = Library.open("/library1")
lib2 = Library.open("/library2")

# Different merge operations
merged = lib1.union(lib2)        # All unique entries
merged = lib1.intersect(lib2)    # Common entries only
merged = lib1.difference(lib2)   # In lib1 but not lib2

# Generic merge
merged = lib1.merge(lib2, operation="symdiff")
```

### Statistics and Analysis

```python
# Get library statistics
stats = lib.stats()
print(f"Total books: {stats['total_entries']}")
print(f"Languages: {stats['languages']}")
print(f"Top authors: {list(stats['creators'].items())[:5]}")
print(f"Popular subjects: {list(stats['subjects'].items())[:10]}")

# Group entries
by_language = lib.group_by("language")
by_year = lib.group_by("year")
by_author = lib.group_by("creators")

# Find duplicates
duplicate_titles = lib.duplicates(by="title")
for title, entries in duplicate_titles:
    print(f"'{title}' has {len(entries)} copies")
```

### Exporting

```python
# Export to different formats
lib.export_to_zip("/path/to/library.zip")

lib.export_to_hugo(
    "/path/to/hugo/site",
    organize_by="year"  # or "language", "subject", "creator", "flat"
)

# Export as navigable symlink DAG
lib.export_to_symlink_dag(
    "/path/to/dag",
    tag_field="subjects",    # Field to use for hierarchy
    include_files=True,      # Copy actual ebook files
    create_index=True        # Generate HTML indexes
)

# Export as graph (co-authorship or subject networks)
lib.export_graph(
    "library.graphml",       # Supports .graphml, .gexf, .json
    graph_type="coauthor",   # or "subject"
    min_connections=2        # Filter edges with fewer connections
)

# Chain operations before export
(lib.filter(lambda e: e.get("language") == "en")
    .tag_all("english")
    .export_to_hugo("/hugo/site", organize_by="subject"))
```

### JMESPath Queries

```python
# Use JMESPath for complex queries
results = lib.query().jmespath(
    "[?language=='en' && contains(subjects, 'Python')]"
).execute()

results = lib.query().jmespath(
    "[?year > `2020`].{title: title, authors: creators}"
).execute()
```

### Finding Similar Books and Recommendations

```python
# Find books similar to a specific entry
similar = lib.find_similar("book_unique_id", threshold=0.7)
# or by Entry object
entry = lib.find("book_unique_id")
similar = lib.find_similar(entry, threshold=0.5)

# Get recommendations
# Random from highly-rated or popular books
recommended = lib.recommend(limit=10)

# Based on specific books (collaborative filtering style)
recommended = lib.recommend(
    based_on=["book_id_1", "book_id_2", "book_id_3"],
    limit=20
)

# Analyze reading patterns
analysis = lib.analyze_reading_patterns()
print(f"Subject diversity (entropy): {analysis['reading_diversity']['subject_entropy']}")
print(f"Top genres: {analysis['reading_diversity']['subject_concentration']}")
print(f"Books per author: {analysis['reading_diversity']['books_per_author']}")
```

## Real-World Examples

### Symlink DAG Navigation

```python
# Create a browsable view of your library organized by hierarchical tags
lib = Library.open("/my/ebook-library")

# Basic export with subject hierarchy
lib.export_to_symlink_dag("/my/browsable-library")

# Organize by authors instead of subjects
lib.export_to_symlink_dag(
    "/my/author-organized-library",
    tag_field="creators"
)

# Filter and export only programming books
(lib.filter(lambda e: "Programming" in e.get("subjects", []))
    .export_to_symlink_dag("/my/programming-books"))
```

This creates a structure like:
```
Programming/
  Python/
    Web/
      Django Web Development → ../../../_books/book_123
    Machine Learning/
      ML with Python → ../../../_books/book_456
```

### Building a Reading List

```python
# Create a reading list from multiple criteria
reading_list = Library.create("/my/reading-list")

# Add highly rated Python books from main library
python_books = (main_lib.query()
    .where("subjects", "Python", "contains")
    .where("rating", 4, ">=")
    .execute())

reading_list.add_entries(python_books)

# Add recent AI books
ai_books = (main_lib.query()
    .where("subjects", "Artificial Intelligence", "contains")
    .where("year", "2022", ">=")
    .execute())

reading_list.add_entries(ai_books)

# Tag and export
reading_list.tag_all("to-read") \
           .export_to_hugo("/my/website", organize_by="subject")
```

### Library Maintenance

```python
# Clean up library
lib = Library.open("/my/library")

# Remove entries without files
lib.remove_where(lambda e: not e.get("file_paths"))

# Fix common issues
lib.update_all(lambda e: 
    e.set("language", "en") if not e.get("language") else None
)

# Normalize subjects
def normalize_subjects(entry):
    subjects = entry.get("subjects", [])
    normalized = []
    for subject in subjects:
        # Normalize case and spacing
        normalized.append(subject.strip().title())
    entry.subjects = normalized

lib.update_all(normalize_subjects)

# Find and handle duplicates
for title, duplicates in lib.duplicates(by="title"):
    print(f"\nFound {len(duplicates)} copies of '{title}':")
    for i, dup in enumerate(duplicates):
        print(f"  {i+1}. ID: {dup.id}, Authors: {dup.creators}")
    # Optionally remove duplicates keeping the first
    for dup in duplicates[1:]:
        lib.remove(dup.id)

lib.save()
```

### Creating a Catalog Website

```python
# Generate a website with books organized by multiple criteria
lib = Library.open("/my/library")

# Create different views
base_path = Path("/my/hugo-site")

# By year for recent additions
(lib.filter(lambda e: e.get("year", 0) >= 2020)
    .export_to_hugo(base_path / "recent", organize_by="year"))

# By language
lib.export_to_hugo(base_path / "languages", organize_by="language")

# By subject for browsing
lib.export_to_hugo(base_path / "subjects", organize_by="subject")

# Featured collection
featured = lib.filter(lambda e: 
    e.get("rating", 0) >= 4.5 or "Award Winner" in e.get("subjects", [])
)
featured.export_to_hugo(base_path / "featured", organize_by="flat")
```

## Best Practices

1. **Always save changes**: Use `.save()` after modifications
2. **Use transactions** for multi-step operations that should be atomic
3. **Chain operations** for cleaner code
4. **Filter before export** to create focused collections
5. **Use batch operations** for better performance with many changes
6. **Handle missing fields** with `.get()` and defaults
7. **Use symlink DAG** for filesystem-based navigation of tag hierarchies
8. **Leverage similarity** for discovery and recommendations

## Performance Tips

- Use `query()` for read-only operations (doesn't modify library)
- Use `filter()` when you need a new library instance
- Batch operations are more efficient than individual updates
- For large libraries, use `.take()` and `.skip()` for pagination
- JMESPath queries can be faster for complex conditions