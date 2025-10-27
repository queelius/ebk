# Hierarchical Tags - Phase 1 Implementation Summary

## Overview

Completed Phase 1 of hierarchical tagging system: Database schema and core tag support.

Tags provide user-defined organization separate from bibliographic subjects:
- **Subjects**: What the book is about (bibliographic metadata, controlled vocabulary, read-only)
- **Tags**: How you use/organize the book (user-defined, freeform, editable)

## What Was Implemented

### 1. Database Schema (`ebk/db/models.py`)

**Tag Model** (lines 168-222):
```python
class Tag(Base):
    """User-defined hierarchical tags for organizing books."""
    __tablename__ = 'tags'

    # Core fields
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)  # Name at this level
    path = Column(String(500), nullable=False, unique=True, index=True)  # Full path
    parent_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'))

    # Optional metadata
    description = Column(Text)
    color = Column(String(7))  # Hex color code
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    parent = relationship('Tag', remote_side=[id], backref='children')
    books = relationship('Book', secondary=book_tags, back_populates='tags')
```

**Key Features**:
- Path-based hierarchy (e.g., "Work/Project-2024")
- Self-referential parent/child relationships
- Helper properties: `depth`, `ancestors`, `full_path_parts`
- Indexed for efficient querying

**book_tags Association Table** (lines 42-48):
```python
book_tags = Table(
    'book_tags',
    Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)
)
```

**Book Model Update** (line 88):
- Added `tags` relationship for many-to-many association

### 2. Tag Service (`ebk/services/tag_service.py`)

Complete CRUD operations for hierarchical tags:

**Hierarchy Management**:
- `get_or_create_tag(path, description, color)` - Creates full hierarchy from path
- `get_tag(path)` - Get tag by path
- `get_all_tags()` - Get all tags ordered by path
- `get_root_tags()` - Get top-level tags (no parent)
- `get_children(tag)` - Get immediate children

**Tag Operations**:
- `delete_tag(path, delete_children)` - Delete with validation
- `rename_tag(old_path, new_path)` - Rename and update entire subtree

**Book-Tag Association**:
- `add_tag_to_book(book, tag_path)` - Add tag to book
- `remove_tag_from_book(book, tag_path)` - Remove tag from book

**Querying**:
- `get_books_with_tag(tag_path, include_subtags)` - Get books, optionally including descendants
- `get_tag_stats(tag_path)` - Get book_count, subtag_count, depth, created_at

### 3. Database Migration System (`ebk/db/migrations.py`)

**Migration Infrastructure**:
- `migrate_add_tags(library_path, dry_run)` - Add tags and book_tags tables
- `run_all_migrations(library_path, dry_run)` - Run all pending migrations
- `check_migrations(library_path)` - Check which migrations are needed
- Extensible architecture for future migrations

**Migration Features**:
- Detects if migration is needed
- Dry-run mode for checking without applying
- Transaction-based execution
- Error handling and logging

### 4. CLI Migration Command (`ebk/cli.py`)

**New Command**: `ebk migrate`

```bash
# Run all pending migrations
ebk migrate ~/my-library

# Check which migrations are needed without applying
ebk migrate ~/my-library --check
```

**Output**:
- Shows which migrations were applied
- Confirms if database is up-to-date
- Clear error messages if migration fails

### 5. Module Exports (`ebk/db/__init__.py`)

Added to public API:
- `Tag` model class
- `run_all_migrations` function
- `check_migrations` function

## Usage Examples

### Creating Tags

```python
from ebk.library_db import Library
from ebk.services.tag_service import TagService

lib = Library.open("~/my-library")
session = lib.session
tag_service = TagService(session)

# Create hierarchical tag (creates "Work" and "Work/Project-2024")
tag = tag_service.get_or_create_tag(
    "Work/Project-2024",
    description="Books for 2024 project",
    color="#FF5733"
)

# Add tag to book
book = session.query(Book).first()
tag_service.add_tag_to_book(book, "Work/Project-2024")

# Get all books with tag (including subtags)
books = tag_service.get_books_with_tag("Work", include_subtags=True)

lib.close()
```

### Running Migration

```bash
# For existing libraries, run migration to add tags support
$ ebk migrate ~/my-library
Running migrations on /home/user/my-library...
✓ Migrations completed successfully:
  • add_tags
```

## Database Schema

### Tags Table
```sql
CREATE TABLE tags (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL,           -- Name at this level
    path VARCHAR(500) NOT NULL UNIQUE,    -- Full hierarchical path
    parent_id INTEGER,                    -- Self-referential FK
    description TEXT,
    color VARCHAR(7),                     -- Hex color code
    created_at DATETIME NOT NULL,
    FOREIGN KEY(parent_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE INDEX idx_tag_path ON tags (path);
CREATE INDEX idx_tag_parent ON tags (parent_id);
CREATE INDEX ix_tags_name ON tags (name);
```

### book_tags Association Table
```sql
CREATE TABLE book_tags (
    book_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at DATETIME,
    PRIMARY KEY (book_id, tag_id),
    FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);
```

## Key Design Decisions

### Path-Based Storage
- Store full path in `path` column (e.g., "Work/Project-2024")
- Enables fast lookups by path
- Simplifies querying descendants using LIKE queries

### Automatic Hierarchy Creation
- `get_or_create_tag("Work/Project-2024")` automatically creates:
  1. "Work" (if doesn't exist)
  2. "Work/Project-2024" (if doesn't exist)
- Ensures referential integrity
- Prevents orphaned tags

### Cascade Deletion
- Deleting parent tag cascades to children (configurable)
- Deleting tag removes book-tag associations
- Prevents orphaned data

### Separation from Subjects
- Tags and Subjects serve different purposes:
  - **Subjects**: Bibliographic (what book is about)
  - **Tags**: Organizational (how you use it)
- Different tables, different workflows
- Can filter by both independently

## Testing

Migration system includes:
- Dry-run mode for safe checking
- Duplicate detection (won't re-run migrations)
- Transaction-based execution
- Clear error messages

## Next Steps (Phase 2)

Phase 1 is complete. Ready to proceed to Phase 2: VFS Read-Only Navigation

**Phase 2 Tasks**:
1. Create VFS nodes for `/tags/` hierarchy
2. Map tag hierarchy to directory structure
3. Show books under each tag as files
4. Implement `ls /tags/Work/` to show subtags and books
5. Support `cd /tags/Work/Project-2024`

**Phase 3 Tasks** (after Phase 2):
1. Implement tag write operations
2. `cp /books/42 /tags/Work/` → adds tag
3. `mv /books/42 /tags/Archive/` → moves tag
4. `rm /tags/Work/Project-2024` → removes tag

**Phase 4 Tasks** (final):
1. Add CLI commands for tag management
2. `ebk tag add <book-id> <tag-path>`
3. `ebk tag remove <book-id> <tag-path>`
4. `ebk tag list` / `ebk tag tree`
5. `ebk tag rename <old> <new>`

## Files Modified/Created

### Created:
1. `ebk/services/tag_service.py` - Tag CRUD operations (274 lines)
2. `ebk/db/migrations.py` - Migration system (145 lines)
3. `docs/tags-phase1-summary.md` - This document

### Modified:
1. `ebk/db/models.py` - Added Tag model and book_tags table
2. `ebk/db/__init__.py` - Exported Tag and migration functions
3. `ebk/cli.py` - Added `migrate` command

## Migration Path

For users with existing libraries:

1. **New libraries**: Tags table created automatically during `ebk init`
2. **Existing libraries**: Run `ebk migrate ~/my-library` to add tags support
3. **Check first**: Use `ebk migrate ~/my-library --check` to see if migration is needed

No data loss - migration only adds new tables, doesn't modify existing data.
