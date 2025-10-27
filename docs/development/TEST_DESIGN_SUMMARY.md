# VFS Shell Commands Test Design Summary

## Overview

I've designed a comprehensive test suite for the recently implemented VFS (Virtual File System) features in the ebk shell. The test file is located at:

**`/home/spinoza/github/beta/ebk/tests/test_vfs_shell_commands.py`**

## Test Coverage

The test suite contains **51 test cases** organized into the following test classes:

### 1. TestLnCommand (7 tests)
Tests for the `ln` command which links books to tags.

**Behaviors Tested:**
- Linking a book to a tag using direct book path (`/books/42`)
- Linking using symlink source from `/tags/` directory (symlink resolution)
- Automatic creation of tag hierarchy when linking
- Error handling for missing arguments
- Error handling for invalid/non-existent sources
- Error handling for non-tag destinations
- Idempotent behavior (linking same book to same tag twice)

**Key Test Cases:**
- `test_ln_book_to_tag` - Basic linking functionality
- `test_ln_symlink_to_tag` - Symlink resolution (`ln /tags/Work/42 /tags/Archive/`)
- `test_ln_creates_tag_hierarchy` - Auto-creates parent tags
- `test_ln_idempotent` - Safe to link multiple times

### 2. TestMkdirCommand (6 tests)
Tests for the `mkdir` command which creates tags.

**Behaviors Tested:**
- Creating simple root-level tags
- Creating nested tag hierarchies with auto-parent creation
- Restriction to `/tags/` directory only
- Error handling for missing arguments
- Error handling for empty tag paths
- Idempotent behavior for existing tags

**Key Test Cases:**
- `test_mkdir_simple_tag` - Create root tag (`/tags/NewTag/`)
- `test_mkdir_nested_tag` - Create nested hierarchy with auto-parents
- `test_mkdir_outside_tags_fails` - Only works in `/tags/`

### 3. TestEchoAndRedirection (9 tests)
Tests for the `echo` command and output redirection to VFS files.

**Behaviors Tested:**
- Basic echo functionality
- Writing to tag description files
- Writing to tag color files with hex validation
- Error handling for non-existent files
- Error handling for read-only files
- Overwriting existing content
- Writing empty strings to clear content

**Key Test Cases:**
- `test_redirect_to_tag_description` - `echo "text" > /tags/Work/description`
- `test_redirect_to_tag_color` - Auto-adds `#` prefix for hex colors
- `test_redirect_to_readonly_file` - Prevents writing to book metadata
- `test_redirect_overwrites_existing_content` - Redirection replaces content

### 4. TestFileWritability (6 tests)
Tests for file writability checks and write operations.

**Behaviors Tested:**
- Tag description files are writable
- Tag color files are writable
- Book metadata files are read-only
- `write_to_vfs_file()` method with writable files
- `write_to_vfs_file()` method with read-only files
- Error handling when writing to directories

**Key Test Cases:**
- `test_tag_description_is_writable` - Validates `is_writable()` method
- `test_book_title_is_readonly` - Book metadata cannot be modified
- `test_write_to_vfs_file_success` - Direct write method works

### 5. TestBookDeletion (7 tests)
Tests for book deletion with confirmation prompt.

**Behaviors Tested:**
- Deleting book with proper "DELETE" confirmation
- Cancelling deletion with wrong confirmation text
- Showing book details in warning prompt
- Case-sensitive confirmation (lowercase "delete" cancels)
- Error handling for non-existent books
- Deleting books with associated files
- Silent mode bypasses confirmation (for testing)

**Key Test Cases:**
- `test_delete_book_with_confirmation` - Requires typing "DELETE"
- `test_delete_book_cancelled` - Any other text cancels
- `test_delete_book_shows_details` - Shows title, authors, file count
- `test_delete_book_wrong_confirmation` - "delete" != "DELETE"

### 6. TestRmCommand (7 tests)
Tests for the `rm` command (remove tags, delete books).

**Behaviors Tested:**
- Removing a tag from a book (`rm /tags/Work/42`)
- Deleting empty tags (`rm /tags/EmptyTag/`)
- Requiring `-r` flag for tags with children
- Recursive tag deletion with `-r` flag
- Warning for non-existent tag removal
- Error handling for invalid paths
- Missing argument validation

**Key Test Cases:**
- `test_rm_tag_from_book` - Untags a book
- `test_rm_tag_with_children_requires_recursive` - Safety check
- `test_rm_tag_recursive` - `rm -r /tags/Parent/` deletes children

### 7. TestEdgeCases (6 tests)
Tests for edge cases and special scenarios.

**Behaviors Tested:**
- Tag paths with special characters (hyphens, numbers)
- Trailing slash variations in paths
- Whitespace handling in redirected content
- Adding multiple tags to same book sequentially
- Tag color validation for various hex formats
- Simultaneous operations maintaining consistency

**Key Test Cases:**
- `test_tag_color_validation` - Accepts `FF0000`, `#00FF00`, `ABC`
- `test_redirect_with_whitespace_in_content` - Strips whitespace
- `test_ln_book_to_multiple_tags_sequentially` - Book can have multiple tags

### 8. TestIntegrationScenarios (3 tests)
Tests for realistic multi-command workflows.

**Workflows Tested:**
- Organizing books with tag hierarchy (create→link→move→describe)
- Deleting a book that has multiple tags (tags persist)
- Reorganizing tag hierarchy (create new→move books→cleanup old)

**Key Test Cases:**
- `test_workflow_organize_books_with_tags` - Full organization flow
- `test_workflow_delete_book_from_tagged_collection` - Tags survive book deletion
- `test_workflow_reorganize_tag_hierarchy` - Refactoring tag structure

## Test Design Principles

### 1. Behavior-Focused Testing
Tests verify **what the system should do**, not **how it does it**:
- ✅ "When I link a book to a tag, the book should appear in that tag"
- ❌ "When I link a book, it should call `add_tag_to_book()` on the service"

### 2. Given-When-Then Structure
All tests follow AAA (Arrange-Act-Assert) pattern:
```python
def test_ln_book_to_tag(self, shell):
    # Given: A book exists in the library
    book = shell.library.query().first()

    # When: We link the book to a tag
    shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"])

    # Then: The book should have the tag
    tag_paths = [tag.path for tag in book.tags]
    assert "Work" in tag_paths
```

### 3. Resilient to Refactoring
Tests use:
- Public APIs only (shell commands, library methods)
- Mock only at boundaries (console output, user input)
- Assertions on observable outcomes (database state, displayed output)
- No testing of private methods or implementation details

### 4. Clear Failure Messages
- Descriptive test names explain the scenario
- Assertions include context when possible
- Failed tests should immediately show what broke

### 5. Edge Cases and Error Conditions
Every command tests:
- Happy path (normal usage)
- Missing/invalid arguments
- Non-existent resources
- Permission/write restrictions
- Idempotent behavior
- Special characters and formatting

## Current Test Results

**Status: 22 PASSING, 29 FAILING**

### Bugs Discovered by Tests

The failing tests have exposed **two bugs** in the implementation:

#### Bug 1: `vfs.resolve()` method doesn't exist
**Location:** `ebk/repl/shell.py` lines 1178, 869
**Issue:** Code calls `self.vfs.resolve(path)` but VFS has `get_node(path)`
**Affected commands:** `ln`, output redirection
**Fix:** Replace `vfs.resolve()` with `vfs.get_node()`

#### Bug 2: `tag_service.create_tag()` method doesn't exist
**Location:** `ebk/repl/shell.py` line 825 (mkdir command)
**Issue:** Code calls `tag_service.create_tag()` but service has `get_or_create_tag()`
**Affected commands:** `mkdir`
**Fix:** Replace `create_tag(tag_path)` with `get_or_create_tag(tag_path)`

### Passing Tests (22)
All tests for:
- ✅ `mkdir` argument validation and restrictions
- ✅ `echo` command basic functionality
- ✅ Book deletion workflow with confirmation
- ✅ `rm` command for removing tags from books
- ✅ Most book deletion scenarios

### Failing Tests (29)
Tests failing due to implementation bugs:
- ❌ All `ln` command tests (vfs.resolve bug)
- ❌ `mkdir` tag creation tests (create_tag bug)
- ❌ All output redirection tests (vfs.resolve bug)
- ❌ File writability tests (vfs.resolve bug)
- ❌ Some integration scenarios (depend on above commands)

## How to Use This Test Suite

### Running All Tests
```bash
python -m pytest tests/test_vfs_shell_commands.py -v
```

### Running Specific Test Class
```bash
python -m pytest tests/test_vfs_shell_commands.py::TestLnCommand -v
python -m pytest tests/test_vfs_shell_commands.py::TestBookDeletion -v
```

### Running Single Test
```bash
python -m pytest tests/test_vfs_shell_commands.py::TestEchoAndRedirection::test_redirect_to_tag_description -v
```

### Running with Coverage
```bash
python -m pytest tests/test_vfs_shell_commands.py --cov=ebk.repl.shell --cov=ebk.vfs --cov-report=html
```

### Current Coverage
- `ebk/repl/shell.py`: 24% (many commands tested, but many untested branches)
- `ebk/vfs/base.py`: 63% (good coverage of file node functionality)
- `ebk/vfs/nodes/tags.py`: 40% (tag VFS nodes partially tested)

## Fixtures

### `temp_library`
Creates a temporary library with automatic cleanup.

### `library_with_books`
Creates a library with:
- 3 test books
- Pre-created tags: "Work", "Archive", "Reading/Fiction"

### `shell`
Creates a `LibraryShell` instance with test library, auto-cleanup.

## Test Data Strategy

Tests use:
- **Builders:** Fixtures create consistent test data
- **Factories:** Dynamic creation of books/tags as needed
- **Isolation:** Each test gets fresh library (no shared state)
- **Realistic data:** Books have titles, authors, subjects like real data

## Mocking Strategy

Tests mock at architectural boundaries:
- ✅ Mock `console.print()` to capture output
- ✅ Mock `session.prompt()` for user input (confirmation dialogs)
- ❌ Don't mock database operations (use real DB with cleanup)
- ❌ Don't mock VFS operations (test real VFS behavior)

## Next Steps

### To Make All Tests Pass

1. **Fix `vfs.resolve()` bug:**
   ```python
   # In shell.py, replace:
   node = self.vfs.resolve(path)
   # With:
   node = self.vfs.get_node(path)
   ```

2. **Fix `create_tag()` bug:**
   ```python
   # In shell.py line 825, replace:
   tag = tag_service.create_tag(tag_path)
   # With:
   tag = tag_service.get_or_create_tag(tag_path)
   ```

### To Improve Coverage

Additional tests could be added for:
- `mv` command (currently not tested)
- Pipeline operations (combining commands with `|`)
- `grep` on VFS files
- `cat` on tag metadata files
- Error recovery and rollback scenarios
- Concurrent operations (if multi-threading is supported)

### To Add to Existing Test Files

Consider adding these VFS tests to:
- `tests/test_tag_vfs.py` - Add tests for writable tag files
- `tests/test_repl.py` - Add integration tests for combined commands

## File Locations

- **Test file:** `/home/spinoza/github/beta/ebk/tests/test_vfs_shell_commands.py`
- **Code under test:**
  - `/home/spinoza/github/beta/ebk/ebk/repl/shell.py`
  - `/home/spinoza/github/beta/ebk/ebk/vfs/base.py`
  - `/home/spinoza/github/beta/ebk/ebk/vfs/nodes/tags.py`
  - `/home/spinoza/github/beta/ebk/ebk/services/tag_service.py`

## Summary

This test suite provides comprehensive coverage of the VFS shell features with:
- **51 test cases** covering all major scenarios
- **Focus on behavior** not implementation
- **Clear structure** using Given-When-Then
- **Resilient design** that enables refactoring
- **Bug discovery** - found 2 implementation bugs
- **22 passing tests** demonstrating working functionality
- **29 failing tests** ready to pass once bugs are fixed

The tests are production-ready and follow TDD best practices. Once the two implementation bugs are fixed, all tests should pass and provide a solid foundation for future development.
