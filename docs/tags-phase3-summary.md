# Hierarchical Tags - Phase 3 Implementation Summary

## Overview

Completed Phase 3 of hierarchical tagging system: Tag write operations in shell.

Users can now manage tags directly through the shell using familiar Unix commands (`cp`, `mv`, `rm`), making tag management intuitive and integrated with the VFS.

## What Was Implemented

### New Shell Commands (`ebk/repl/shell.py`)

#### 1. **cp** - Add Tag to Book

Copy command adds a tag to a book without removing existing tags.

**Signature**:
```python
def cmd_cp(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]
```

**Usage**:
```bash
cp /books/42 /tags/Work/
cp /books/42 /tags/Work/Project-2024/
cp /tags/Archive/42 /tags/Reading-List/  # Can copy from one tag to another
```

**Behavior**:
- Extracts book ID from source path (handles `/books/42` or `/tags/Work/42`)
- Extracts tag path from destination (`/tags/Work/` → `Work`)
- Calls `tag_service.add_tag_to_book(book, tag_path)`
- Creates tag hierarchy automatically if doesn't exist
- Shows success message with book title

**Error Handling**:
- Source not found
- Invalid source (must be a book)
- Invalid destination (must be `/tags/...`)
- Book not found in database
- Database errors

#### 2. **mv** - Move Book Between Tags

Move command removes one tag and adds another (atomic operation).

**Signature**:
```python
def cmd_mv(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]
```

**Usage**:
```bash
mv /tags/Work/42 /tags/Archive/
mv /tags/Work/Project-2024/42 /tags/Work/Reference/
```

**Behavior**:
- Requires both source and destination to be tag paths
- Extracts source tag path and book ID from source
- Removes old tag from book
- Adds new tag to book
- Shows warning if book didn't have source tag
- Shows success message

**Error Handling**:
- Source must be tag path with book ID
- Destination must be tag path
- Invalid book ID
- Book not found
- Database errors

#### 3. **rm** - Remove Tag or Delete Tag

Remove command has dual behavior:
- **Remove tag from book**: `rm /tags/Work/42`
- **Delete tag entirely**: `rm /tags/Work/` (with `-r` for children)

**Signature**:
```python
def cmd_rm(self, args: List[str], stdin: Optional[str] = None, silent: bool = False) -> Optional[str]
```

**Usage**:
```bash
# Remove tag from specific book
rm /tags/Work/42

# Delete tag (only if no children)
rm /tags/OldTag/

# Delete tag and all children recursively
rm -r /tags/OldProject/
```

**Behavior**:
- Parses `-r` flag for recursive deletion
- Determines if path is book (ends with number) or tag (directory)
- **If book**: Removes tag from that specific book
- **If tag**: Deletes the tag itself
  - Checks for children if no `-r` flag
  - Cascades deletion if `-r` flag set

**Error Handling**:
- Path must be tag path
- Tag with children requires `-r` flag
- Tag not found
- Book not found
- Database errors
- Helpful hints for common mistakes

### Command Registration

Added to command registry in `__init__`:
```python
self.commands = {
    # ... existing commands ...
    "cp": self.cmd_cp,
    "mv": self.cmd_mv,
    "rm": self.cmd_rm,
    # ...
}
```

### Help Documentation

Updated help command to document new commands:
```
cp <src> <dest>    Add tag to book (cp /books/42 /tags/Work/)
mv <src> <dest>    Move book between tags
rm [-r] <path>     Remove tag from book or delete tag
```

## Usage Examples

### Adding Tags to Books

```bash
# Add "Work" tag to book 42
ebk:/$ cp /books/42 /tags/Work/
✓ Added tag 'Work' to book 42
  Book: The Art of Computer Programming

# Add nested tag (creates hierarchy automatically)
ebk:/$ cp /books/42 /tags/Work/Project-2024/
✓ Added tag 'Work/Project-2024' to book 42
  Book: The Art of Computer Programming

# Copy from one tag to another
ebk:/tags/Work$ cp 42 /tags/Reading-List/
✓ Added tag 'Reading-List' to book 42
  Book: The Art of Computer Programming
```

### Moving Books Between Tags

```bash
# Move book from Work to Archive
ebk:/$ mv /tags/Work/42 /tags/Archive/
✓ Moved book 42 from 'Work' to 'Archive'
  Book: The Art of Computer Programming

# Move between nested tags
ebk:/$ mv /tags/Work/Project-2024/42 /tags/Work/Completed/
✓ Moved book 42 from 'Work/Project-2024' to 'Work/Completed'
  Book: The Art of Computer Programming

# Warning if book didn't have source tag
ebk:/$ mv /tags/NonExistent/42 /tags/Work/
Warning: Book didn't have tag 'NonExistent'
✓ Moved book 42 from 'NonExistent' to 'Work'
```

### Removing Tags

```bash
# Remove tag from specific book
ebk:/$ rm /tags/Work/42
✓ Removed tag 'Work' from book 42
  Book: The Art of Computer Programming

# Book didn't have that tag
ebk:/$ rm /tags/Work/99
Book 99 didn't have tag 'Work'

# Delete empty tag
ebk:/$ rm /tags/EmptyTag/
✓ Deleted tag 'EmptyTag'

# Try to delete tag with children (fails)
ebk:/$ rm /tags/Work/
Error: Tag 'Work' has 2 children. Use delete_children=True to delete them too.
Hint: Use 'rm -r /tags/Work/' to delete tag and its children

# Delete tag with children recursively
ebk:/$ rm -r /tags/OldProject/
✓ Deleted tag 'OldProject'
```

### Complex Workflows

```bash
# Find books and add tag to all matches
ebk:/$ find author:Knuth
42    The Art of Computer Programming, Vol. 1
137   The Art of Computer Programming, Vol. 2
ebk:/$ cp /books/42 /tags/Reference/
ebk:/$ cp /books/137 /tags/Reference/

# Reorganize tags
ebk:/$ mv /tags/To-Read/42 /tags/Reading-List/
ebk:/$ mv /tags/Reading-List/42 /tags/Currently-Reading/
ebk:/$ mv /tags/Currently-Reading/42 /tags/Finished/

# Clean up old tags
ebk:/$ rm -r /tags/2023-Projects/
```

## Design Decisions

### Why `cp` for Adding Tags?

In Unix, `cp` creates a copy without removing the original. For tags, this translates to:
- Book remains in original location (`/books/42`)
- Tag is "copied" to the book (book now has this tag)
- Book can have multiple tags (like being in multiple places)

**Alternative considered**: `ln` (link) command
- Rejected: More confusing metaphor for users
- `cp` is more familiar and intuitive

### Why `mv` for Changing Tags?

`mv` removes from one location and adds to another:
- Removes source tag
- Adds destination tag
- Atomic operation (both succeed or both fail)

**Use case**: Reorganizing tags, moving books between categories

### Why Dual Behavior for `rm`?

Unix `rm` removes files or directories. For tags:
- **File-like**: Book within tag → Remove tag from book
- **Directory-like**: Tag itself → Delete tag

**Path determines behavior**:
- `/tags/Work/42` (ends with number) → Remove tag from book
- `/tags/Work/` (directory) → Delete tag

**Recursive flag**:
- `-r` required to delete tag with children (safety measure)

### Why Auto-Create Tags in `cp`?

When copying to non-existent tag path:
```bash
cp /books/42 /tags/NewTag/SubTag/
```

**Behavior**: Creates `NewTag` and `NewTag/SubTag` automatically

**Rationale**:
- Matches `get_or_create_tag()` service method
- Reduces friction (no need to pre-create tags)
- Consistent with mkdir -p behavior
- User-friendly for workflow

### Error Messages and Hints

All commands provide:
- **Clear error messages**: What went wrong
- **Helpful hints**: How to fix it
- **Success confirmations**: What was done
- **Context**: Book title when available

Examples:
```bash
Error: Tag 'Work' has 2 children. Use delete_children=True to delete them too.
Hint: Use 'rm -r /tags/Work/' to delete tag and its children
```

## Implementation Details

### Path Parsing

All commands parse VFS paths to extract:
- Book ID (integer at end of path or after `/books/`)
- Tag path (everything after `/tags/`)

**Robust parsing**:
```python
# Extract book ID from various formats
path_parts = source_path.strip('/').split('/')

if path_parts[0] == 'books' and len(path_parts) >= 2:
    book_id = int(path_parts[1])  # /books/42
elif path_parts[0] == 'tags':
    book_id = int(path_parts[-1])  # /tags/Work/42
```

### Silent Mode Support

All commands support `silent` parameter:
- Used in pipelines to suppress intermediate output
- Consistent with other shell commands
- Returns `None` (no stdout for piping)

### Transaction Safety

Uses `TagService` which handles database sessions:
- Auto-commit on success
- Auto-rollback on error
- Session management via SQLAlchemy

## Testing

### Manual Testing Scenarios

1. **Add tags to books**:
   - From `/books/` path
   - From `/tags/` path
   - To existing tags
   - To new tags (auto-create)

2. **Move between tags**:
   - Simple move
   - Nested tag move
   - Non-existent source tag

3. **Remove tags**:
   - Remove from book
   - Delete empty tag
   - Delete tag with children (should fail)
   - Delete tag with `-r` flag

4. **Error cases**:
   - Invalid paths
   - Non-existent books
   - Non-existent tags
   - Wrong path types

### Automated Tests (Future)

Add to test suite:
- `tests/test_tag_shell_commands.py`
- Test each command with various path formats
- Test error conditions
- Test edge cases
- Test silent mode

## Limitations

### No `mkdir` for Tag Creation

Cannot create empty tags with `mkdir /tags/NewTag/`

**Rationale**:
- Tags should be created when adding to books
- Empty tags have no purpose
- Use CLI commands for batch tag creation (Phase 4)

### No Tag Renaming via `mv`

Cannot rename tags with `mv /tags/OldName/ /tags/NewName/`

**Rationale**:
- `mv` is for moving books between tags
- Renaming tags is complex (updates all children paths)
- Use `ebk tag rename` CLI command instead (Phase 4)

### No Batch Operations

Cannot do: `cp /books/* /tags/Work/`

**Rationale**:
- Shell doesn't support glob expansion in VFS paths
- Use loops or CLI commands for batch operations
- Keep shell commands simple

## Files Modified

### Modified:
1. `ebk/repl/shell.py` - Added cmd_cp, cmd_mv, cmd_rm methods (277 lines added)
2. `ebk/repl/shell.py` - Updated command registry
3. `ebk/repl/shell.py` - Updated help documentation

## Summary

Phase 3 successfully implements write operations for tags:

✅ `cp` command adds tags to books
✅ `mv` command moves books between tags
✅ `rm` command removes tags or deletes tags
✅ Auto-creates tag hierarchy when needed
✅ Clear error messages and helpful hints
✅ Integrated with VFS navigation
✅ Silent mode for piping support
✅ Documented in help system

Users can now fully manage tags through the shell using intuitive Unix-like commands!

## Next Steps (Phase 4 - Final)

Phase 3 is complete. Ready to proceed to Phase 4: CLI Commands for Tag Management

**Phase 4 Tasks**:
1. Add `ebk tag list` - List all tags or books with tag
2. Add `ebk tag tree` - Show hierarchical tag tree
3. Add `ebk tag add <book-id> <tag>` - Add tag to book (CLI)
4. Add `ebk tag remove <book-id> <tag>` - Remove tag from book (CLI)
5. Add `ebk tag rename <old> <new>` - Rename tag and update subtree
6. Add `ebk tag stats [tag]` - Show tag statistics
7. Add `ebk tag delete [-r] <tag>` - Delete tag (CLI version)
8. Integration with import/export (preserve tags in metadata)
