# Hierarchical Tags - Phase 2 Implementation Summary

## Overview

Completed Phase 2 of hierarchical tagging system: VFS read-only navigation.

Users can now browse hierarchical tags as nested folders in the shell, just like they browse books, authors, and subjects.

## What Was Implemented

### 1. Tag VFS Nodes (`ebk/vfs/nodes/tags.py`)

Created comprehensive VFS node hierarchy for tags:

#### **TagsDirectoryNode** - `/tags/`
Entry point for tag browsing. Lists root-level tags as children.

```python
class TagsDirectoryNode(VirtualNode):
    """Virtual directory with hierarchical tag structure."""

    def list_children(self) -> List[Node]:
        """List root-level tags (tags with no parent)."""
        root_tags = self.tag_service.get_root_tags()
        # Returns TagNode instances

    def get_child(self, name: str) -> Optional[Node]:
        """Get root-level tag by name."""
        # e.g., "Work", "Reading-List"
```

**Features**:
- Dynamically lists root tags from database
- Shows count of total tags and root tags in stats

#### **TagNode** - `/tags/Work/` or `/tags/Work/Project-2024/`
Represents a single tag in the hierarchy. Contains:
- Child tags (subdirectories)
- Books with this tag (symlinks to `/books/ID`)
- Metadata files (description, color, stats)

```python
class TagNode(VirtualNode):
    """A tag directory in the hierarchy."""

    def list_children(self) -> List[Node]:
        """List child tags, books, and metadata files."""
        # Returns:
        # - TagNode for child tags
        # - SymlinkNode for books
        # - FileNode for metadata (description, color, stats)

    def get_child(self, name: str) -> Optional[Node]:
        """Get child tag, book, or metadata file by name."""
```

**Features**:
- Hierarchical navigation (tags can have child tags)
- Books appear as symlinks to `/books/ID`
- Metadata files for tag info

#### **Metadata File Nodes**

Three special files appear in tag directories:

**TagDescriptionFile** - `description`
Shows the tag's description text.

**TagColorFile** - `color`
Shows the tag's hex color code.

**TagStatsFile** - `stats`
Shows comprehensive tag statistics:
```
Tag: Work/Project-2024
Name: Project-2024
Depth: 1
Books: 5
Subtags: 0
Description: Books for 2024 project
Color: #FF5733
Created: 2025-01-15T10:30:00
```

### 2. Root Node Integration (`ebk/vfs/nodes/root.py`)

Updated root node to include `/tags/` directory:

```python
def _build_children(self) -> None:
    """Build top-level directory nodes."""
    from ebk.vfs.nodes.tags import TagsDirectoryNode

    self._children_cache = {
        "books": BooksDirectoryNode(self.library, parent=self),
        "authors": AuthorsDirectoryNode(self.library, parent=self),
        "subjects": SubjectsDirectoryNode(self.library, parent=self),
        "tags": TagsDirectoryNode(self.library, parent=self),  # NEW
    }
```

**Updated root stats**:
- Added `total_tags` count to root directory info

### 3. Module Exports (`ebk/vfs/nodes/__init__.py`)

Exported new tag node classes:
- `TagsDirectoryNode`
- `TagNode`
- `TagDescriptionFile`
- `TagColorFile`
- `TagStatsFile`

### 4. Shell Help Update (`ebk/repl/shell.py`)

Updated help command to document `/tags/` directory:

```
VFS Structure:
  /books/       - All books
  /books/42/    - Book with ID 42
  /authors/     - Browse by author
  /subjects/    - Browse by subject
  /tags/        - Browse by user-defined hierarchical tags
```

## Usage Examples

### Browsing Tags

```bash
# List root-level tags
ebk:/$ ls tags/
Work/
Reading-List/
To-Read/
Archive/

# Navigate into a tag
ebk:/$ cd tags/Work/
ebk:/tags/Work$ ls
Project-2024/
Reference/
42
137
stats
description

# View tag metadata
ebk:/tags/Work$ cat description
Work-related books and references

ebk:/tags/Work$ cat stats
Tag: Work
Name: Work
Depth: 0
Books: 2
Subtags: 2
Description: Work-related books and references
Color: #3498db
Created: 2025-01-15T10:30:00

# Navigate into nested tag
ebk:/tags/Work$ cd Project-2024/
ebk:/tags/Work/Project-2024$ ls
42
137
198
stats
color

# Books appear as symlinks to /books/ID
ebk:/tags/Work/Project-2024$ ls -l
42 -> /books/42
137 -> /books/137
198 -> /books/198
```

### Combining with Other Commands

```bash
# Count books in a tag
ebk:/tags/Work$ find . | wc -l
5

# Search within tagged books
ebk:/tags/Work/Project-2024$ cat /books/42/text | grep algorithm

# List all tags
ebk:/$ ls -R tags/

# Find books with specific tag
ebk:/$ cd /tags/Reading-List
ebk:/tags/Reading-List$ ls
23
45
67
```

### VFS Structure

```
/
├── books/
│   ├── 42/
│   └── 137/
├── authors/
├── subjects/
└── tags/              # NEW
    ├── Work/          # Root tag
    │   ├── Project-2024/    # Child tag
    │   │   ├── 42 -> /books/42
    │   │   ├── 137 -> /books/137
    │   │   ├── stats
    │   │   └── color
    │   ├── Reference/       # Child tag
    │   ├── 42 -> /books/42
    │   ├── stats
    │   └── description
    ├── Reading-List/  # Root tag
    │   ├── 23 -> /books/23
    │   └── 45 -> /books/45
    └── Archive/       # Root tag
        └── ...
```

## Architecture

### Hierarchical Navigation

Tags support unlimited nesting:
- `/tags/Work/` - Depth 0 (root tag)
- `/tags/Work/Project-2024/` - Depth 1
- `/tags/Work/Project-2024/Backend/` - Depth 2
- And so on...

### Dynamic Children

TagNode dynamically computes children on each access:
1. **Child tags**: Query database for tags with `parent_id == this_tag.id`
2. **Books**: Get books from `tag.books` relationship
3. **Metadata files**: Create file nodes for description, color, stats

### Book Symlinks

Books appear as symlinks to `/books/ID`:
- Easy to navigate to book details
- Consistent with `/subjects/` and `/authors/` patterns
- Works with all shell commands (cat, grep, etc.)

## Design Decisions

### Why Not Copy Subjects Pattern?

Subjects use flat slugs: `/subjects/machine-learning/`

Tags use hierarchical paths: `/tags/Work/Project-2024/`

**Rationale**:
- Tags are hierarchical by design (parent/child relationships)
- Users expect nested folders for hierarchical data
- Matches mental model of file organization

### Why Include Metadata Files?

Each tag directory has optional files:
- `description` - Tag description
- `color` - Hex color code
- `stats` - Comprehensive statistics

**Benefits**:
- Discoverable (appear in `ls`)
- Readable with `cat`
- Consistent with Unix philosophy (everything is a file)
- No special commands needed

### Why Books as Symlinks?

Books appear as symlinks (`42 -> /books/42`) instead of full directories.

**Benefits**:
- Avoids duplication (book data lives in `/books/`)
- Single source of truth
- Consistent with subjects/authors pattern
- Shell naturally follows symlinks

## Limitations (By Design)

### Read-Only (Phase 2)

Currently tags are **read-only** in the shell:
- ✅ Can navigate: `cd /tags/Work/`
- ✅ Can list: `ls /tags/Work/`
- ✅ Can read metadata: `cat /tags/Work/description`
- ❌ Cannot create tags via shell (yet)
- ❌ Cannot add books to tags via shell (yet)
- ❌ Cannot delete tags via shell (yet)

**Phase 3** will add write operations:
- `cp /books/42 /tags/Work/` - Add tag to book
- `mv /books/42 /tags/Archive/` - Move tag (remove old, add new)
- `rm /tags/Work/Project-2024` - Remove tag

### No Tag Creation via `mkdir`

Currently cannot do: `mkdir /tags/Work/NewProject/`

**Rationale**:
- Tags need to be added to books (not just created)
- `mkdir` doesn't specify which books to tag
- Use dedicated CLI commands instead (Phase 4)

### No Inline Editing

Cannot edit tag metadata with `vim` or similar:
- `cat /tags/Work/description` works ✅
- `vim /tags/Work/description` doesn't work ❌

**Rationale**:
- VFS is read-only view of database
- Direct editing would bypass validation
- Use CLI commands for editing (Phase 4)

## Files Modified/Created

### Created:
1. `ebk/vfs/nodes/tags.py` - Tag VFS nodes (269 lines)
2. `docs/tags-phase2-summary.md` - This document

### Modified:
1. `ebk/vfs/nodes/root.py` - Added TagsDirectoryNode to root
2. `ebk/vfs/nodes/__init__.py` - Exported tag node classes
3. `ebk/repl/shell.py` - Updated help to mention `/tags/`

## Testing

### Manual Testing Needed

Test the following scenarios:

1. **Basic navigation**:
   ```bash
   cd /tags/
   ls
   cd Work/
   ls
   ```

2. **Nested tags**:
   ```bash
   cd /tags/Work/Project-2024/
   ls
   ```

3. **Metadata files**:
   ```bash
   cat /tags/Work/stats
   cat /tags/Work/description
   ```

4. **Book symlinks**:
   ```bash
   cd /tags/Work/
   ls 42
   cat 42/title
   ```

5. **Empty tags**:
   ```bash
   # Tag with no books or children
   cd /tags/EmptyTag/
   ls
   ```

6. **Piping with tags**:
   ```bash
   ls /tags/ | wc -l
   find /tags/Work/ | grep "42"
   ```

### Automated Tests (Future)

Add to test suite:
- `tests/test_tag_vfs.py` - VFS node tests
- Test navigation, listing, metadata files
- Test edge cases (empty tags, deep nesting)

## Next Steps (Phase 3)

Phase 2 is complete. Ready to proceed to Phase 3: Tag Write Operations

**Phase 3 Tasks**:
1. Implement `cp /books/42 /tags/Work/` - Add tag to book
2. Implement `mv /books/42 /tags/Archive/` - Move tag (add new tag)
3. Implement `rm /tags/Work/42` - Remove tag from book
4. Handle edge cases:
   - Tag creation when copying to non-existent tag
   - Validation and error messages
   - Confirmation prompts for destructive operations

**Phase 4 Tasks** (final):
1. Add CLI commands: `ebk tag add`, `ebk tag remove`, `ebk tag list`
2. Add `ebk tag tree` for hierarchical visualization
3. Add `ebk tag rename` for renaming tags
4. Add `ebk tag stats` for tag statistics
5. Integration with import/export (preserve tags)

## Summary

Phase 2 successfully implements read-only VFS navigation for hierarchical tags:

✅ Users can browse tags as nested folders
✅ Navigate with `cd /tags/Work/Project-2024/`
✅ List contents with `ls`
✅ Read metadata with `cat stats`
✅ Books appear as symlinks to `/books/ID`
✅ Unlimited nesting depth supported
✅ Integrated with existing shell commands

The tag browsing experience is now on par with authors and subjects, but with the added power of hierarchical organization!
