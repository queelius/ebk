# VFS Shell Tests - Quick Reference

## Test File Location
`/home/spinoza/github/beta/ebk/tests/test_vfs_shell_commands.py`

## Test Classes and Coverage

| Test Class | Tests | Feature Coverage | Status |
|------------|-------|------------------|--------|
| `TestLnCommand` | 7 | Link books to tags, symlink resolution | 🟡 Blocked by vfs.resolve bug |
| `TestMkdirCommand` | 6 | Create tags via mkdir | 🟡 Partial (validation ✅, creation ❌) |
| `TestEchoAndRedirection` | 9 | Echo command and `>` redirection | 🟡 Blocked by vfs.resolve bug |
| `TestFileWritability` | 6 | Writable vs read-only files | 🟡 Blocked by vfs.resolve bug |
| `TestBookDeletion` | 7 | Delete books with confirmation | ✅ Fully passing |
| `TestRmCommand` | 7 | Remove tags, delete books/tags | ✅ Mostly passing |
| `TestEdgeCases` | 6 | Special chars, whitespace, etc. | 🟡 Blocked by bugs |
| `TestIntegrationScenarios` | 3 | Multi-command workflows | 🟡 Blocked by bugs |
| **TOTAL** | **51** | **All VFS features** | **22 passing, 29 blocked** |

## Feature Coverage Map

### ✅ Fully Tested and Working
- [x] Book deletion with "DELETE" confirmation
- [x] Case-sensitive confirmation validation
- [x] Removing tags from books (`rm /tags/Work/42`)
- [x] Deleting empty tags
- [x] Recursive tag deletion with `-r` flag
- [x] Mkdir argument validation
- [x] Mkdir path restrictions (only /tags/)
- [x] Echo command basic functionality
- [x] Book title read-only validation

### 🟡 Tested but Blocked by Implementation Bugs
- [ ] Linking books to tags (`ln /books/42 /tags/Work/`)
- [ ] Symlink resolution (`ln /tags/Work/42 /tags/Archive/`)
- [ ] Creating tags with mkdir
- [ ] Output redirection (`echo "text" > file`)
- [ ] Writing to tag description/color files
- [ ] File writability checks
- [ ] Tag hierarchy auto-creation

### 🔴 Not Yet Tested
- [ ] `mv` command (move between tags)
- [ ] Pipeline operations with `|`
- [ ] `grep` on VFS files
- [ ] `cat` on tag metadata files
- [ ] Tab completion for VFS paths
- [ ] Bash command passthrough (`!command`)

## Test Pattern Examples

### Basic Command Test
```python
def test_ln_book_to_tag(self, shell):
    # Given: A book exists
    book = shell.library.query().first()

    # When: We link it to a tag
    shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"])

    # Then: Book should have the tag
    assert "Work" in [tag.path for tag in book.tags]
```

### Error Handling Test
```python
def test_ln_invalid_source(self, shell):
    # When: We try to link non-existent book
    with patch.object(shell.console, "print") as mock_print:
        shell.cmd_ln(["/books/99999", "/tags/Work/"])

    # Then: Error message should be shown
    assert "not found" in str(mock_print.call_args_list).lower()
```

### User Input Test
```python
def test_delete_book_with_confirmation(self, shell):
    book = shell.library.query().first()

    # Mock user typing "DELETE"
    with patch.object(shell.session, "prompt", return_value="DELETE"):
        shell.cmd_rm([f"/books/{book.id}/"])

    # Book should be deleted
    assert shell.library.session.query(Book).filter_by(id=book.id).first() is None
```

### Integration Test
```python
def test_workflow_organize_books_with_tags(self, shell):
    # Create tag hierarchy
    shell.cmd_mkdir(["/tags/Reading/Queue/"], silent=True)
    shell.cmd_mkdir(["/tags/Reading/Completed/"], silent=True)

    # Add book to queue
    book = shell.library.query().first()
    shell.cmd_ln([f"/books/{book.id}", "/tags/Reading/Queue/"], silent=True)

    # Move to completed
    shell.cmd_mv([f"/tags/Reading/Queue/{book.id}", "/tags/Reading/Completed/"], silent=True)

    # Add description
    shell.execute('echo "Finished books" > /tags/Reading/Completed/description')

    # Verify
    assert len(tag_service.get_tag("Reading/Completed").books) == 1
```

## Running Tests

### Run all VFS tests
```bash
pytest tests/test_vfs_shell_commands.py -v
```

### Run specific feature
```bash
pytest tests/test_vfs_shell_commands.py::TestLnCommand -v
pytest tests/test_vfs_shell_commands.py::TestBookDeletion -v
```

### Run with coverage
```bash
pytest tests/test_vfs_shell_commands.py --cov=ebk.repl.shell --cov=ebk.vfs --cov-report=html
```

### Run only passing tests
```bash
pytest tests/test_vfs_shell_commands.py::TestBookDeletion -v
pytest tests/test_vfs_shell_commands.py::TestRmCommand -v
```

## Known Implementation Bugs (Discovered by Tests)

### Bug #1: vfs.resolve() doesn't exist
**File:** `ebk/repl/shell.py`
**Lines:** 1178, 869
**Fix:**
```python
# Replace:
node = self.vfs.resolve(path)
# With:
node = self.vfs.get_node(path)
```

### Bug #2: tag_service.create_tag() doesn't exist
**File:** `ebk/repl/shell.py`
**Line:** 825
**Fix:**
```python
# Replace:
tag = tag_service.create_tag(tag_path)
# With:
tag = tag_service.get_or_create_tag(tag_path)
```

## Test Fixtures

### `temp_library`
- Creates temporary library
- Auto-cleanup after test

### `library_with_books`
- 3 test books
- Tags: "Work", "Archive", "Reading/Fiction"
- Auto-cleanup

### `shell`
- LibraryShell instance
- Connected to test library
- Auto-cleanup

## Mocking Patterns

### Capture Console Output
```python
with patch.object(shell.console, "print") as mock_print:
    shell.cmd_ln(["/books/42", "/tags/Work/"])
    assert "✓ Added tag" in str(mock_print.call_args_list)
```

### Mock User Input
```python
with patch.object(shell.session, "prompt", return_value="DELETE"):
    shell.cmd_rm(["/books/42/"])
```

### Silent Mode (No Output)
```python
shell.cmd_ln(["/books/42", "/tags/Work/"], silent=True)
```

## Coverage Targets

| Module | Current | Target | Gap |
|--------|---------|--------|-----|
| `ebk/repl/shell.py` | 24% | 70%+ | Need tests for grep, find, cat, ls |
| `ebk/vfs/base.py` | 63% | 80%+ | Need edge case tests |
| `ebk/vfs/nodes/tags.py` | 40% | 80%+ | Need TagNode tests |

## Test Metrics

- **Total Tests:** 51
- **Passing:** 22 (43%)
- **Blocked by bugs:** 29 (57%)
- **Test Lines:** ~700
- **Code Coverage:** 34% overall
- **Time to Run:** ~26 seconds

## Priority Test Additions

1. **High Priority** (Critical features)
   - [ ] `mv` command tests
   - [ ] Pipeline operations
   - [ ] grep on VFS files

2. **Medium Priority** (Common operations)
   - [ ] cat on tag files
   - [ ] ls with filters
   - [ ] cd path resolution

3. **Low Priority** (Nice to have)
   - [ ] Tab completion
   - [ ] History navigation
   - [ ] Bash passthrough

## Test Maintenance

### When Adding New VFS Features
1. Add test class to `test_vfs_shell_commands.py`
2. Follow Given-When-Then structure
3. Test happy path + error cases
4. Add integration scenario if multi-step
5. Update this reference guide

### When Fixing Bugs
1. Write failing test first (TDD)
2. Fix implementation
3. Verify test passes
4. Check coverage increased

### When Refactoring
1. Run tests first (should all pass)
2. Make changes
3. Run tests again (should still pass)
4. If tests fail, refactor broke behavior
