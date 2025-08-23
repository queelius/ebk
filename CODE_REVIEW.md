# EBK Code Review Report

## 1. CRITICAL BUGS & INCOMPLETE FEATURES

### 1.1 Missing Methods
- **`where_title_contains` method is missing from QueryBuilder** 
  - Used by CLI commands (rate, comment, mark) but not implemented
  - Will cause AttributeError when trying to search by title
  - **Fix**: Add method to QueryBuilder class

### 1.2 Incomplete Personal Metadata Integration
- Personal metadata CLI commands will fail due to missing `where_title_contains`
- Web exports don't display personal metadata (ratings, read status, etc.)
- No way to export/import personal metadata separately

### 1.3 Import Issues
- Missing `Optional` import in several files that use it
- Circular import potential between library.py and personal.py

## 2. ERROR HANDLING ISSUES

### 2.1 Overly Broad Exception Handlers
- `multi_facet_export.py`: Bare `except:` on line ~90 (catches everything including KeyboardInterrupt)
- `jinja_export.py`: Bare `except:` that silently swallows errors
- **Risk**: Hiding real errors, making debugging difficult

### 2.2 Inconsistent Error Handling
- CLI commands have 16+ identical FileNotFoundError handlers
- Should be refactored to a decorator or common function
- Error messages not always helpful to users

### 2.3 Missing Validation
- No validation on file paths (could lead to path traversal)
- No size limits on metadata fields (potential memory issues)
- No validation of unique_id format consistency

## 3. DESIGN & ARCHITECTURE ISSUES

### 3.1 Code Duplication
- CLI error handling repeated 16+ times
- Entry finding logic duplicated across multiple CLI commands
- Similar export logic across different export modules

### 3.2 Tight Coupling
- Library class directly instantiates PersonalMetadata
- Export modules have duplicated sanitization logic
- CLI commands directly manipulate library internals

### 3.3 Missing Abstractions
- No base class for exporters (hugo, zip, symlink_dag, multi_facet)
- No interface for import modules
- Query builder could benefit from a more fluent pattern

## 4. PERFORMANCE ISSUES

### 4.1 Memory Usage
- Loading entire library into memory (could be problematic for large libraries)
- Deep copying entire entry list for queries
- No lazy loading of entry data

### 4.2 Inefficient Operations
- Linear search for entries by ID (O(n) for each lookup)
- No indexing for common queries
- Multiple passes over data in query execution

## 5. SECURITY CONCERNS

### 5.1 Path Traversal Risk
- User-provided paths not validated
- Symlink creation could potentially link to sensitive files
- No sandboxing of file operations

### 5.2 HTML/JavaScript Injection
- User metadata directly inserted into HTML templates
- Need proper escaping in Jinja templates
- JSON data not properly sanitized

### 5.3 Resource Exhaustion
- No limits on:
  - Number of entries
  - Size of metadata fields
  - Depth of tag hierarchies
  - Number of symlinks created

## 6. MISSING FEATURES

### 6.1 Core Functionality
- No bulk operations for personal metadata
- No undo/redo for operations
- No conflict resolution for merges
- No incremental updates (always full save)

### 6.2 User Experience
- No progress bars for long operations (except imports)
- No dry-run mode for dangerous operations
- No backup before modifications
- No configuration file validation

### 6.3 Data Management
- No data migration for schema changes
- No versioning of metadata format
- No integrity checks for library consistency
- No cleanup of orphaned files

## 7. TESTING & DOCUMENTATION

### 7.1 Missing Tests
- No tests for personal metadata functionality
- No tests for export modules
- No integration tests for CLI commands
- No performance benchmarks

### 7.2 Missing Type Hints
- Many functions lack return type annotations
- No type hints for complex data structures
- Would benefit from TypedDict for entry structure

### 7.3 Documentation Gaps
- No API documentation for Library class
- No examples for personal metadata
- No migration guide from old versions
- No troubleshooting guide

## 8. REFACTORING OPPORTUNITIES

### 8.1 Extract Common Patterns
```python
# Decorator for CLI error handling
def handle_library_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except FileNotFoundError as e:
            console.print(f"[red]Library not found: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}")
            console.print(f"[red]Operation failed: {e}[/red]")
            raise typer.Exit(1)
    return wrapper
```

### 8.2 Create Base Classes
```python
class BaseExporter(ABC):
    @abstractmethod
    def export(self, library_path: Path, output_path: Path, **options):
        pass
    
    def _sanitize_filename(self, name: str) -> str:
        # Common implementation
        pass
```

### 8.3 Improve Query Builder
```python
class QueryBuilder:
    def where_title_contains(self, pattern: str) -> 'QueryBuilder':
        """Filter by title containing pattern."""
        return self.where_lambda(
            lambda e: pattern.lower() in e.get('title', '').lower()
        )
    
    def where_author_is(self, author: str) -> 'QueryBuilder':
        """Filter by author."""
        return self.where_lambda(
            lambda e: author in e.get('creators', [])
        )
```

## 9. IMMEDIATE PRIORITIES

1. **Fix where_title_contains** - Blocking personal metadata CLI
2. **Add error handling decorator** - Reduce code duplication
3. **Sanitize HTML output** - Security issue
4. **Add progress indicators** - UX improvement
5. **Create exporter base class** - Better architecture
6. **Add library indexing** - Performance improvement
7. **Implement validation** - Data integrity
8. **Add integration tests** - Quality assurance

## 10. LONG-TERM IMPROVEMENTS

1. **Database backend option** - For large libraries
2. **Async operations** - Better performance
3. **Plugin system** - Extensibility
4. **REST API** - Remote access
5. **Incremental updates** - Efficiency
6. **Version control integration** - Collaboration
7. **Full-text search** - Better discovery
8. **Machine learning features** - Smart recommendations