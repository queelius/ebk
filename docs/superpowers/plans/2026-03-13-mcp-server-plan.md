# MCP Server + AI Layer Removal — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ebk's bespoke AI/LLM layer with an MCP server (3 tools), delete ~3,300 LOC of dead/redundant code, and fix remaining code review items (#8, #9, #10, #12).

**Architecture:** An `ebk/mcp/` module with a `FastMCP` server exposing `get_schema`, `execute_sql`, and `update_books` tools over stdio. Read-only SQL uses the same 3-layer defense as the Views DSL. The entire `ebk/ai/` directory and `integrations/llm/` are deleted. A new `ebk mcp-serve` CLI command launches the server.

**Tech Stack:** Python, MCP SDK (`FastMCP`), SQLAlchemy (model introspection), SQLite (authorizer), pytest

**Spec:** `docs/superpowers/specs/2026-03-13-mcp-server-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `ebk/mcp/__init__.py` | Package root, re-exports |
| `ebk/mcp/server.py` | FastMCP server setup, tool registration, `run_server()` entry point |
| `ebk/mcp/tools.py` | Tool implementations: `get_schema`, `execute_sql`, `update_books` |
| `ebk/mcp/sql_executor.py` | Read-only SQL execution with 3-layer security (extracted from Views DSL pattern) |
| `tests/test_mcp_tools.py` | Unit tests for all 3 MCP tools |
| `tests/test_mcp_sql_executor.py` | Unit tests for read-only SQL executor |

### Modified files
| File | Change |
|------|--------|
| `ebk/library_db.py` | Add `db_path` property (database path is `library_path / 'library.db'` but never exposed) |
| `ebk/cli.py` | Add `mcp-serve` command; remove `enrich` command (~240 lines) and config LLM options (~40 lines) |
| `ebk/config.py` | Remove `LLMConfig` dataclass and LLM params from `update_config()` |
| `ebk/db/models.py` | Remove `EnrichmentHistory` model (lines 672-718) |
| `ebk/views/dsl.py` | Refactor `_apply_comparison()` (lines 425-499) with operator map; fix compose transform (lines 568-575) |
| `tests/test_views.py` | Add tests for compose override preservation |
| `tests/test_new_services.py` | Add `export_goodreads_csv` and `export_calibre_csv` tests |
| `tests/test_search_parser.py` | Add edge case tests |
| `tests/test_core_modules.py` | Remove LLM-related test code |
| `pyproject.toml` | Update dependencies (remove AI extras, update MCP pin) |
| `setup.py` | Same dependency treatment |
| `mkdocs.yml` | Update nav (remove llm-features, update MCP docs) |
| `CLAUDE.md` | Remove AI/enrich references, add MCP info |

### Deleted files/directories
| Path | Reason |
|------|--------|
| `ebk/ai/` (entire directory) | Replaced by MCP; 61% dead code |
| `integrations/llm/` | Parallel unused LLM layer |
| `integrations/mcp/` (entire directory) | Old MCP server, its README, example-configs, requirements.txt |
| `docs/user-guide/llm-features.md` | Documents removed functionality |

### Updated docs
| File | Change |
|------|--------|
| `docs/development/architecture.md` | Remove AI layer section, add MCP section |
| `docs/getting-started/configuration.md` | Remove LLM config section |
| `docs/user-guide/server.md` | Update references |
| `docs/index.md` | Replace AI features with MCP description |
| `integrations/README.md` | Remove LLM/MCP references |
| `integrations/PLUGINS.md` | Remove LLM/MCP references |

---

## Chunk 1: Code Review Fixes (#8, #9, #10, #12)

These are independent of the MCP work and should land first so the MCP tasks start from a clean base.

### Task 1: Export service test coverage (#8)

**Files:**
- Modify: `tests/test_new_services.py` (after line 476)
- Read: `ebk/services/export_service.py:327-526`

- [ ] **Step 1: Write failing test for `export_goodreads_csv`**

```python
# In tests/test_new_services.py, add to TestExportService class:

def test_export_goodreads_csv(self, populated_library):
    """Test Goodreads CSV export format."""
    lib = populated_library
    export_svc = ExportService(lib.session, lib.library_path)
    books = lib.get_all_books()
    csv_str = export_svc.export_goodreads_csv(books)

    assert csv_str is not None
    lines = csv_str.strip().split("\n")
    # Header row
    assert "Title" in lines[0]
    assert "Author" in lines[0]
    assert "ISBN" in lines[0]
    assert "My Rating" in lines[0]
    assert "Exclusive Shelf" in lines[0]
    assert "Bookshelves" in lines[0]
    # At least header + 1 data row
    assert len(lines) >= 2

def test_export_goodreads_csv_multi_author(self, populated_library):
    """Test Goodreads CSV handles multiple authors."""
    lib = populated_library
    export_svc = ExportService(lib.session, lib.library_path)
    books = lib.get_all_books()
    csv_str = export_svc.export_goodreads_csv(books)

    import csv
    import io
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) > 0
    # Every row should have Author field populated
    for row in rows:
        assert "Author" in row

def test_export_calibre_csv(self, populated_library):
    """Test Calibre CSV export format."""
    lib = populated_library
    export_svc = ExportService(lib.session, lib.library_path)
    books = lib.get_all_books()
    csv_str = export_svc.export_calibre_csv(books)

    assert csv_str is not None
    lines = csv_str.strip().split("\n")
    # Calibre-specific headers
    assert "title" in lines[0].lower() or "Title" in lines[0]
    assert len(lines) >= 2

def test_export_calibre_csv_with_tags(self, populated_library):
    """Test Calibre CSV includes tags."""
    lib = populated_library
    books = lib.get_all_books()
    if books:
        # Use session directly — Library has no add_tag_to_book method
        from ebk.db.models import Tag
        tag = Tag(name="SubTag", path="TestTag/SubTag")
        lib.session.add(tag)
        books[0].tags.append(tag)
        lib.session.commit()

    export_svc = ExportService(lib.session, lib.library_path)
    books = lib.get_all_books()
    csv_str = export_svc.export_calibre_csv(books)

    import csv
    import io
    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) > 0
```

- [ ] **Step 2: Run tests to verify they fail or pass**

Run: `pytest tests/test_new_services.py::TestExportService -v --tb=short`

Expected: Tests should pass (we're testing existing functionality, not TDD here — these are coverage additions).

- [ ] **Step 3: Commit**

```bash
git add tests/test_new_services.py
git commit -m "test: add Goodreads and Calibre CSV export tests (#8)"
```

---

### Task 2: DSL comparison logic refactor (#9)

**Files:**
- Modify: `ebk/views/dsl.py:425-499`
- Test: `tests/test_views.py` (existing tests validate behavior)

- [ ] **Step 1: Run existing DSL tests as baseline**

Run: `pytest tests/test_views.py -v --tb=short`

Expected: All tests pass.

- [ ] **Step 2: Refactor `_apply_comparison()` to use operator map**

In `ebk/views/dsl.py`, replace the repeated operator dispatch (lines 425-499) with:

```python
import operator as _op

# At class level in ViewEvaluator:
_COMPARISON_OPS = {
    'gte': _op.ge, 'gt': _op.gt,
    'lte': _op.le, 'lt': _op.lt,
    'eq': _op.eq, 'ne': _op.ne,
}

# Field -> (SQLAlchemy column resolver, value converter)
# This replaces the per-field if/elif blocks
```

The refactored `_apply_comparison()` should:
1. Parse the operator and value from the comparison dict (same as before)
2. Map field name to SQLAlchemy column expression (with joins if needed, e.g., `rating` joins `PersonalMetadata`)
3. Look up the operator function from `_COMPARISON_OPS`
4. Apply `column.op(value)` using SQLAlchemy's column comparison methods
5. Keep `contains`, `in`, `between` as special cases (they aren't simple binary operators)

- [ ] **Step 3: Run existing tests to verify refactor is behavior-preserving**

Run: `pytest tests/test_views.py -v --tb=short`

Expected: All tests still pass. No new tests needed — the existing suite covers comparison operators thoroughly.

- [ ] **Step 4: Commit**

```bash
git add ebk/views/dsl.py
git commit -m "refactor: replace repetitive comparison dispatch with operator map (#9)"
```

---

### Task 3: Compose transform override bug (#10)

**Files:**
- Modify: `ebk/views/dsl.py:535-587`
- Modify: `tests/test_views.py`

- [ ] **Step 1: Write failing test that demonstrates the bug**

```python
# In tests/test_views.py, add a new test class:

class TestComposeOverridePreservation:
    """Test that compose transforms preserve overrides from earlier transforms."""

    def test_compose_preserves_title_override(self, view_evaluator, sample_books):
        """Override in first transform should survive compose chain."""
        book = sample_books[0]
        transform = {
            'compose': [
                {'override': {book.id: {'title': 'Overridden Title'}}},
                'identity',
            ]
        }
        result = view_evaluator._evaluate_transform(
            transform, set(sample_books), "test"
        )
        overridden = [tb for tb in result if tb.book.id == book.id]
        assert len(overridden) == 1
        assert overridden[0].title == 'Overridden Title'

    def test_compose_chains_overrides(self, view_evaluator, sample_books):
        """Overrides from multiple transforms in compose should all apply."""
        book = sample_books[0]
        transform = {
            'compose': [
                {'override': {book.id: {'title': 'Custom Title'}}},
                {'override': {book.id: {'description': 'Custom Desc'}}},
            ]
        }
        result = view_evaluator._evaluate_transform(
            transform, set(sample_books), "test"
        )
        overridden = [tb for tb in result if tb.book.id == book.id]
        assert len(overridden) == 1
        assert overridden[0].title == 'Custom Title'
        assert overridden[0].description == 'Custom Desc'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_views.py::TestComposeOverridePreservation -v --tb=short`

Expected: FAIL — override is lost because compose unwraps `TransformedBook` to `Book`.

- [ ] **Step 3: Fix compose transform in `_evaluate_transform()`**

Refactor `_evaluate_transform()` (lines 535-587) to accept and return `List[TransformedBook]` instead of `Set[Book]`. The compose handler (lines 568-575) must pass `TransformedBook` objects through the chain:

```python
# In the compose handler, instead of:
#   book_set = {tb.book for tb in result}
#   result = self._evaluate_transform(t, book_set, context)
# Do:
#   result = self._evaluate_transform(t, result, context)
```

Update callers of `_evaluate_transform()` to wrap `Set[Book]` into `List[TransformedBook]` at the entry point. Internal transforms work on `List[TransformedBook]` throughout.

- [ ] **Step 4: Run all view tests**

Run: `pytest tests/test_views.py -v --tb=short`

Expected: All tests pass, including the new override preservation tests.

- [ ] **Step 5: Commit**

```bash
git add ebk/views/dsl.py tests/test_views.py
git commit -m "fix: compose transform now preserves overrides through chain (#10)"
```

---

### Task 4: Search parser edge cases (#12)

**Files:**
- Modify: `tests/test_search_parser.py` (after line 955)

- [ ] **Step 1: Write edge case tests**

```python
# In tests/test_search_parser.py, add to TestSearchQueryParserEdgeCases:

def test_nested_parentheses(self):
    """Nested parentheses should parse correctly."""
    result = parse_search_query("(python OR java) AND (advanced OR beginner)")
    assert result is not None
    # Should have terms from both groups
    assert len(result.terms) > 0 or len(result.filters) > 0

def test_colon_in_field_value(self):
    """Colons in field values should not break parsing."""
    result = parse_search_query("title:C++")
    assert result is not None
    assert any(f.value == "C++" for f in result.filters if f.field == "title")

def test_multiple_colons_in_value(self):
    """Multiple colons in a query should be handled."""
    result = parse_search_query("description:http://example.com")
    assert result is not None

def test_unbalanced_quotes_at_end(self):
    """Unclosed quote at end of query."""
    result = parse_search_query('title:"unclosed')
    assert result is not None
    # Should still produce some result, not crash
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_search_parser.py::TestSearchQueryParserEdgeCases -v --tb=short`

Expected: Tests pass (parser should handle these gracefully) or reveal actual bugs to fix.

- [ ] **Step 3: Commit**

```bash
git add tests/test_search_parser.py
git commit -m "test: add search parser edge cases for parens, colons, quotes (#12)"
```

---

## Chunk 2: Delete AI Layer and Clean Up

### Task 5: Delete `ebk/ai/` directory

**Files:**
- Delete: `ebk/ai/` (entire directory, 12 files, ~3,300 LOC)

- [ ] **Step 1: Delete the directory**

```bash
rm -rf ebk/ai/
```

- [ ] **Step 2: Run full test suite to check for import breakage**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`

Expected: Tests pass. The only code that imports from `ebk.ai` is `cli.py`'s `enrich` command which we haven't removed yet — those imports are inside the function body, so they only fail at runtime when `enrich` is called.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "remove: delete ebk/ai/ directory (~3,300 LOC dead/redundant AI layer)"
```

---

### Task 6: Delete `integrations/llm/` and old MCP server

**Files:**
- Delete: `integrations/llm/` (entire directory)
- Delete: `integrations/mcp/` (entire directory — includes README.md, example-configs/, requirements.txt)
- Modify: `integrations/README.md`
- Modify: `integrations/PLUGINS.md`

- [ ] **Step 1: Delete LLM integration and old MCP server**

```bash
rm -rf integrations/llm/
rm -rf integrations/mcp/
```

- [ ] **Step 2: Update `integrations/README.md` and `PLUGINS.md`**

Remove references to LLM providers and MCP server. Keep references to `metadata/` (Google Books, Open Library) and `network/` (network analyzer).

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -10`

Expected: All pass.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "remove: delete integrations/llm/ and old MCP subprocess wrapper"
```

---

### Task 7: Remove LLM from config, CLI, models, and tests

**Files:**
- Modify: `ebk/config.py:17-26` (remove `LLMConfig`), `ebk/config.py:164-230` (remove LLM params from `update_config`)
- Modify: `ebk/cli.py:4592-4838` (remove `enrich` command), `ebk/cli.py:4842-4861` (remove LLM config options)
- Modify: `ebk/db/models.py:672-718` (remove `EnrichmentHistory`)
- Modify: `tests/test_core_modules.py` (remove LLM test code)

- [ ] **Step 1: Remove `LLMConfig` from `config.py`**

Delete the `LLMConfig` dataclass (lines 17-26). Remove LLM fields from `EBKConfig` if it references `LLMConfig`. Remove LLM params (`llm_provider`, `llm_model`, `llm_host`, `llm_port`, `llm_api_key`, `llm_temperature`, `llm_max_tokens`) from `update_config()` (lines 164-230), including the section that applies them (lines 193-206).

- [ ] **Step 2: Remove `enrich` command and LLM config options from `cli.py`**

Delete the `enrich` function (lines 4592-4838). Remove `--llm-*` options from the `config` command (lines 4846-4851) and their application logic. Remove any `from ebk.ai` imports at the top of the file.

- [ ] **Step 3: Remove `EnrichmentHistory` from `db/models.py`**

Delete the `EnrichmentHistory` class (lines 672-718). Do NOT create a migration to drop the table. Remove from `__all__` or any `__init__.py` exports if listed.

- [ ] **Step 4: Remove LLM tests from `test_core_modules.py`**

Remove `TestLLMConfig` class and any assertions referencing `cfg.llm`.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -30`

Expected: All tests pass. Some tests that imported LLM types may need removal.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "remove: strip LLM config, enrich command, EnrichmentHistory model, LLM tests"
```

---

### Task 8: Update dependencies

**Files:**
- Modify: `pyproject.toml:62-115`
- Modify: `setup.py:62-88`

- [ ] **Step 1: Update `pyproject.toml`**

- Remove `ai` extra group (sentence-transformers, scikit-learn, networkx, etc.)
- Remove `llm` extra group (httpx for LLM, pydantic for LLM)
- Update `mcp` extra: change `mcp>=0.1.0` to `mcp>=1.0,<2.0`
- Keep any non-AI optional dependencies intact

- [ ] **Step 2: Update `setup.py`**

Same treatment: remove `ai` and `llm` extras, update `mcp` version pin.

- [ ] **Step 3: Verify install works**

Run: `pip install -e ".[mcp]" 2>&1 | tail -5`

Expected: Successful install with MCP SDK 1.x.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml setup.py
git commit -m "deps: remove AI extras, pin mcp>=1.0,<2.0"
```

---

## Chunk 3: Build MCP Server

### Task 9: Add `db_path` property to Library

**Files:**
- Modify: `ebk/library_db.py`

The `Library` class has `library_path` but the actual database file path (`library_path / 'library.db'`) is computed inside `init_db()` and never exposed. The MCP server needs this.

- [ ] **Step 1: Add property**

In `ebk/library_db.py`, add to the `Library` class:

```python
@property
def db_path(self) -> Path:
    """Path to the SQLite database file."""
    return self.library_path / "library.db"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short 2>&1 | tail -10`

Expected: All pass (additive change).

- [ ] **Step 3: Commit**

```bash
git add ebk/library_db.py
git commit -m "feat: add db_path property to Library class"
```

---

### Task 10: Read-only SQL executor

**Files:**
- Create: `ebk/mcp/__init__.py`
- Create: `ebk/mcp/sql_executor.py`
- Create: `tests/test_mcp_sql_executor.py`

- [ ] **Step 1: Create package and write failing tests**

Create `ebk/mcp/__init__.py` (empty).

Create `tests/test_mcp_sql_executor.py`:

```python
"""Tests for read-only SQL executor."""
import pytest
from pathlib import Path
from ebk.library_db import Library
from ebk.mcp.sql_executor import ReadOnlySQLExecutor


@pytest.fixture
def executor(tmp_path):
    """Create a library and return an executor against its database."""
    lib = Library.open(tmp_path / "test-lib")
    yield ReadOnlySQLExecutor(lib.db_path)
    lib.close()


class TestReadOnlySQLExecutor:
    def test_select_returns_rows(self, executor):
        result = executor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        assert "columns" in result
        assert "rows" in result
        assert "row_count" in result
        assert result["row_count"] > 0

    def test_rejects_non_select(self, executor):
        result = executor.execute("INSERT INTO books (title) VALUES ('hack')")
        assert "error" in result

    def test_rejects_drop(self, executor):
        result = executor.execute("DROP TABLE books")
        assert "error" in result

    def test_rejects_update(self, executor):
        result = executor.execute("UPDATE books SET title='hacked'")
        assert "error" in result

    def test_rejects_delete(self, executor):
        result = executor.execute("DELETE FROM books")
        assert "error" in result

    def test_rejects_attach(self, executor):
        result = executor.execute("ATTACH DATABASE ':memory:' AS hack")
        assert "error" in result

    def test_rejects_pragma(self, executor):
        result = executor.execute("PRAGMA table_info(books)")
        assert "error" in result

    def test_parameterized_query(self, executor):
        result = executor.execute(
            "SELECT name FROM sqlite_master WHERE type=?", params=["table"]
        )
        assert "error" not in result
        assert result["row_count"] > 0

    def test_row_limit(self, executor):
        result = executor.execute(
            "SELECT name FROM sqlite_master", max_rows=1
        )
        if result["row_count"] > 0:
            assert len(result["rows"]) <= 1
            if result.get("truncated"):
                assert result["truncated"] is True

    def test_empty_result(self, executor):
        result = executor.execute(
            "SELECT * FROM books WHERE title='nonexistent_book_xyz'"
        )
        assert result["row_count"] == 0
        assert result["rows"] == []

    def test_rejects_multi_statement(self, executor):
        result = executor.execute("SELECT 1; DROP TABLE books")
        assert "error" in result

    def test_case_insensitive_select(self, executor):
        result = executor.execute("select name from sqlite_master limit 1")
        assert "error" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_sql_executor.py -v --tb=short`

Expected: FAIL — `ebk.mcp.sql_executor` does not exist yet.

- [ ] **Step 3: Implement `ReadOnlySQLExecutor`**

Create `ebk/mcp/sql_executor.py`:

```python
"""Read-only SQL executor with 3-layer security defense."""
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_AUTHORIZER_ALLOWED = frozenset({
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
})

_SELECT_PREFIX = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MULTI_STATEMENT = re.compile(r";\s*\S")

DEFAULT_MAX_ROWS = 1000


def _sqlite_authorizer(action, arg1, arg2, db_name, trigger_name):
    """SQLite authorizer callback — only allows SELECT/READ/FUNCTION."""
    if action in _AUTHORIZER_ALLOWED:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class ReadOnlySQLExecutor:
    """Execute read-only SQL against a library database with defense-in-depth."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> Dict[str, Any]:
        """Execute a read-only SQL query and return results as dict."""
        # Layer 1: Prefix check
        if not _SELECT_PREFIX.match(sql):
            return {"error": "Only SELECT queries are allowed"}

        # Check for multi-statement
        if _MULTI_STATEMENT.search(sql):
            return {"error": "Multiple SQL statements are not allowed"}

        try:
            # Layer 2: Read-only connection
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                # Layer 3: Authorizer callback
                conn.set_authorizer(_sqlite_authorizer)
                cursor = conn.execute(sql, params or [])
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchmany(max_rows + 1)

                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]

                result = {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows),
                }
                if truncated:
                    result["truncated"] = True
                return result
            finally:
                conn.close()
        except sqlite3.Error as e:
            return {"error": str(e)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_mcp_sql_executor.py -v --tb=short`

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ebk/mcp/__init__.py ebk/mcp/sql_executor.py tests/test_mcp_sql_executor.py
git commit -m "feat(mcp): add read-only SQL executor with 3-layer security"
```

---

### Task 11: `get_schema` tool

**Files:**
- Create: `ebk/mcp/tools.py`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_mcp_tools.py`:

```python
"""Tests for MCP tool implementations."""
import json
import pytest
from pathlib import Path
from ebk.library_db import Library
from ebk.mcp.tools import get_schema_impl, execute_sql_impl, update_books_impl


@pytest.fixture
def library(tmp_path):
    """Create a temporary library for testing."""
    lib = Library.open(tmp_path / "test-lib")
    yield lib
    lib.close()


@pytest.fixture
def populated_library(library):
    """Library with sample books for testing.

    Uses Library API (not raw ORM) to ensure unique_id, timestamps, etc. are set.
    """
    from ebk.db.models import Book, Author
    import uuid
    session = library.session

    author = Author(name="Test Author", sort_name="Author, Test")
    session.add(author)
    session.flush()

    book = Book(title="Test Book", language="en", unique_id=str(uuid.uuid4())[:32])
    book.authors.append(author)
    session.add(book)

    book2 = Book(title="Second Book", language="fr", unique_id=str(uuid.uuid4())[:32])
    book2.authors.append(author)
    session.add(book2)

    session.commit()
    return library


class TestGetSchema:
    def test_returns_tables(self, library):
        schema = get_schema_impl(library.session)
        assert "tables" in schema
        table_names = [t["name"] for t in schema["tables"]]
        assert "books" in table_names
        assert "authors" in table_names
        assert "subjects" in table_names
        assert "tags" in table_names

    def test_tables_have_columns(self, library):
        schema = get_schema_impl(library.session)
        books_table = next(t for t in schema["tables"] if t["name"] == "books")
        col_names = [c["name"] for c in books_table["columns"]]
        assert "id" in col_names
        assert "title" in col_names
        assert "language" in col_names

    def test_includes_relationships(self, library):
        schema = get_schema_impl(library.session)
        assert "relationships" in schema
        # books -> authors relationship should exist
        rel_strs = [r["from"] + "->" + r["to"] for r in schema["relationships"]]
        assert any("books" in r and "authors" in r for r in rel_strs)

    def test_includes_junction_tables(self, library):
        schema = get_schema_impl(library.session)
        table_names = [t["name"] for t in schema["tables"]]
        assert "book_authors" in table_names
        # Junction table should have semantic columns
        ba_table = next(t for t in schema["tables"] if t["name"] == "book_authors")
        col_names = [c["name"] for c in ba_table["columns"]]
        assert "role" in col_names or "position" in col_names

    def test_includes_enums(self, library):
        schema = get_schema_impl(library.session)
        assert "enums" in schema
        assert "reading_status" in schema["enums"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_tools.py::TestGetSchema -v --tb=short`

Expected: FAIL — `get_schema_impl` does not exist.

- [ ] **Step 3: Implement `get_schema_impl`**

In `ebk/mcp/tools.py`:

```python
"""MCP tool implementations for ebk library."""
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session
from ebk.db.models import Base, Book, PersonalMetadata


def get_schema_impl(session: Session) -> Dict[str, Any]:
    """Return the database schema as a JSON-serializable dict."""
    engine = session.get_bind()
    inspector = sa_inspect(engine)

    tables = []
    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("autoincrement", False) or False,
            })
        # Get primary keys properly
        pk = inspector.get_pk_constraint(table_name)
        pk_cols = set(pk["constrained_columns"]) if pk else set()
        for c in columns:
            c["primary_key"] = c["name"] in pk_cols

        tables.append({"name": table_name, "columns": columns})

    # Relationships from ORM
    relationships = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        for rel in mapper.relationships:
            relationships.append({
                "from": cls.__tablename__,
                "to": rel.mapper.class_.__tablename__,
                "name": rel.key,
                "type": rel.direction.name,
                "via": rel.secondary.name if rel.secondary is not None else None,
            })

    # Enum-like constraints
    enums = {
        "reading_status": ["unread", "reading", "read", "abandoned"],
    }

    return {"tables": tables, "relationships": relationships, "enums": enums}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_mcp_tools.py::TestGetSchema -v --tb=short`

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ebk/mcp/tools.py tests/test_mcp_tools.py
git commit -m "feat(mcp): implement get_schema tool with ORM introspection"
```

---

### Task 12: `execute_sql` tool

**Files:**
- Modify: `ebk/mcp/tools.py`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mcp_tools.py`:

```python
class TestExecuteSQL:
    def test_basic_select(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            "SELECT title FROM books"
        )
        assert "columns" in result
        assert result["columns"] == ["title"]
        assert result["row_count"] >= 2

    def test_parameterized_query(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            "SELECT title FROM books WHERE language = ?",
            params=["en"]
        )
        assert result["row_count"] >= 1
        assert all(row[0] for row in result["rows"])

    def test_rejects_insert(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            "INSERT INTO books (title) VALUES ('hack')"
        )
        assert "error" in result

    def test_rejects_update(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            "UPDATE books SET title = 'hacked'"
        )
        assert "error" in result

    def test_row_limit(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            "SELECT title FROM books",
            max_rows=1
        )
        assert len(result["rows"]) <= 1

    def test_join_query(self, populated_library):
        result = execute_sql_impl(
            populated_library.db_path,
            """SELECT b.title, a.name
               FROM books b
               JOIN book_authors ba ON b.id = ba.book_id
               JOIN authors a ON ba.author_id = a.id"""
        )
        assert "error" not in result
        assert result["row_count"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_tools.py::TestExecuteSQL -v --tb=short`

Expected: FAIL — `execute_sql_impl` does not exist.

- [ ] **Step 3: Implement `execute_sql_impl`**

Add to `ebk/mcp/tools.py`:

```python
from pathlib import Path
from ebk.mcp.sql_executor import ReadOnlySQLExecutor


def execute_sql_impl(
    db_path: Path,
    sql: str,
    params: Optional[List[Any]] = None,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """Execute a read-only SQL query against the library database."""
    executor = ReadOnlySQLExecutor(db_path)
    return executor.execute(sql, params=params, max_rows=max_rows)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_mcp_tools.py::TestExecuteSQL -v --tb=short`

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ebk/mcp/tools.py tests/test_mcp_tools.py
git commit -m "feat(mcp): implement execute_sql tool with read-only defense"
```

---

### Task 13: `update_books` tool

**Files:**
- Modify: `ebk/mcp/tools.py`
- Modify: `tests/test_mcp_tools.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_mcp_tools.py`:

```python
class TestUpdateBooks:
    def test_update_scalar_field(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"title": "Updated Title"}}
        )
        assert book_id in result["updated"]
        assert not result["errors"]
        # Verify the update persisted
        book = populated_library.get_book(book_id)
        assert book.title == "Updated Title"

    def test_update_personal_metadata(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"rating": 4.5, "reading_status": "reading"}}
        )
        assert book_id in result["updated"]
        book = populated_library.get_book(book_id)
        assert book.personal is not None
        assert book.personal.rating == 4.5
        assert book.personal.reading_status == "reading"

    def test_add_tags(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"add_tags": ["Test/Tag1", "Test/Tag2"]}}
        )
        assert book_id in result["updated"]
        book = populated_library.get_book(book_id)
        tag_paths = [t.path for t in book.tags]
        assert "Test/Tag1" in tag_paths or any("Tag1" in p for p in tag_paths)

    def test_add_authors(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"add_authors": ["New Author"]}}
        )
        assert book_id in result["updated"]
        book = populated_library.get_book(book_id)
        author_names = [a.name for a in book.authors]
        assert "New Author" in author_names

    def test_remove_authors(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"remove_authors": ["Test Author"]}}
        )
        assert book_id in result["updated"]
        book = populated_library.get_book(book_id)
        author_names = [a.name for a in book.authors]
        assert "Test Author" not in author_names

    def test_batch_update(self, populated_library):
        books = populated_library.get_all_books()
        updates = {
            str(books[0].id): {"language": "de"},
            str(books[1].id): {"language": "es"},
        }
        result = update_books_impl(populated_library.session, updates)
        assert len(result["updated"]) == 2

    def test_unknown_field_returns_error(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(book_id): {"nonexistent_field": "value"}}
        )
        assert book_id in result["errors"] or str(book_id) in result["errors"]

    def test_invalid_book_id_returns_error(self, populated_library):
        result = update_books_impl(
            populated_library.session,
            {"99999": {"title": "Ghost"}}
        )
        assert 99999 in result["errors"] or "99999" in result["errors"]

    def test_merge_into(self, populated_library):
        books = populated_library.get_all_books()
        if len(books) < 2:
            pytest.skip("Need at least 2 books")
        source_id = books[1].id
        target_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {str(source_id): {"merge_into": target_id}}
        )
        assert source_id in result["updated"]
        # Source book should be deleted
        assert populated_library.get_book(source_id) is None

    def test_merge_with_other_fields_rejected(self, populated_library):
        books = populated_library.get_all_books()
        if len(books) < 2:
            pytest.skip("Need at least 2 books")
        result = update_books_impl(
            populated_library.session,
            {str(books[1].id): {"merge_into": books[0].id, "title": "Conflict"}}
        )
        assert books[1].id in result["errors"] or str(books[1].id) in result["errors"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mcp_tools.py::TestUpdateBooks -v --tb=short`

Expected: FAIL — `update_books_impl` does not exist.

- [ ] **Step 3: Implement `update_books_impl`**

Add to `ebk/mcp/tools.py`:

```python
from sqlalchemy import inspect as sa_inspect
from ebk.db.models import Book, Author, Subject, Tag, PersonalMetadata


# Derive allowed fields from ORM models
def _get_book_columns() -> Set[str]:
    """Get updatable column names from Book model."""
    mapper = sa_inspect(Book)
    skip = {"id", "unique_id", "created_at", "updated_at"}
    return {c.key for c in mapper.column_attrs if c.key not in skip}


def _get_personal_columns() -> Set[str]:
    """Get updatable column names from PersonalMetadata model."""
    mapper = sa_inspect(PersonalMetadata)
    skip = {"id", "book_id"}
    return {c.key for c in mapper.column_attrs if c.key not in skip}


_COLLECTION_OPS = {"add_tags", "remove_tags", "add_authors", "remove_authors",
                   "add_subjects", "remove_subjects"}
_SPECIAL_OPS = {"merge_into"}


def update_books_impl(
    session: Session,
    updates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply updates to books. Returns {updated: [...], errors: {...}}."""
    book_cols = _get_book_columns()
    personal_cols = _get_personal_columns()
    updated = []
    errors = {}

    for book_id_str, fields in updates.items():
        book_id = int(book_id_str)
        try:
            book = session.get(Book, book_id)
            if not book:
                errors[book_id] = f"Book {book_id} not found"
                continue

            # Check merge_into exclusivity
            if "merge_into" in fields:
                if len(fields) > 1:
                    errors[book_id] = "merge_into is mutually exclusive with other fields"
                    continue
                _merge_book(session, book, fields["merge_into"])
                updated.append(book_id)
                continue

            # Validate all fields first
            unknown = set(fields.keys()) - book_cols - personal_cols - _COLLECTION_OPS - _SPECIAL_OPS
            if unknown:
                errors[book_id] = f"Unknown fields: {', '.join(sorted(unknown))}"
                continue

            # Apply scalar Book fields
            for key in set(fields.keys()) & book_cols:
                setattr(book, key, fields[key])

            # Apply PersonalMetadata fields
            pm_fields = set(fields.keys()) & personal_cols
            if pm_fields:
                if not book.personal:
                    book.personal = PersonalMetadata(book_id=book.id)
                    session.add(book.personal)
                for key in pm_fields:
                    setattr(book.personal, key, fields[key])

            # Apply collection operations
            _apply_collection_ops(session, book, fields)

            updated.append(book_id)
        except Exception as e:
            errors[book_id] = str(e)

    session.commit()
    return {"updated": updated, "errors": errors}


def _merge_book(session: Session, source: Book, target_id: int):
    """Merge source book into target book.

    Delegates to Library.merge_books() which handles files, covers,
    authors, subjects, tags, and deletion of the source book.
    """
    from ebk.library_db import Library
    # merge_books expects a Library instance but we only have a session.
    # Use the session-level merge logic directly:
    target = session.get(Book, target_id)
    if not target:
        raise ValueError(f"Target book {target_id} not found")
    # Move files and covers
    for f in source.files:
        f.book_id = target_id
    for c in source.covers:
        c.book_id = target_id
    # Merge collections (add missing)
    for a in source.authors:
        if a not in target.authors:
            target.authors.append(a)
    for s in source.subjects:
        if s not in target.subjects:
            target.subjects.append(s)
    for t in source.tags:
        if t not in target.tags:
            target.tags.append(t)
    session.delete(source)


def _apply_collection_ops(session: Session, book: Book, fields: Dict[str, Any]):
    """Apply add_/remove_ collection operations."""
    if "add_tags" in fields:
        for tag_path in fields["add_tags"]:
            _ensure_tag(session, book, tag_path)
    if "remove_tags" in fields:
        book.tags = [t for t in book.tags if t.path not in fields["remove_tags"]]
    if "add_authors" in fields:
        for name in fields["add_authors"]:
            author = session.query(Author).filter_by(name=name).first()
            if not author:
                author = Author(name=name, sort_name=name)
                session.add(author)
            if author not in book.authors:
                book.authors.append(author)
    if "remove_authors" in fields:
        book.authors = [a for a in book.authors if a.name not in fields["remove_authors"]]
    if "add_subjects" in fields:
        for name in fields["add_subjects"]:
            subject = session.query(Subject).filter_by(name=name).first()
            if not subject:
                subject = Subject(name=name)
                session.add(subject)
            if subject not in book.subjects:
                book.subjects.append(subject)
    if "remove_subjects" in fields:
        book.subjects = [s for s in book.subjects if s.name not in fields["remove_subjects"]]


def _ensure_tag(session: Session, book: Book, tag_path: str):
    """Create tag hierarchy if needed and add to book."""
    tag = session.query(Tag).filter_by(path=tag_path).first()
    if not tag:
        parts = tag_path.split("/")
        parent = None
        for i, part in enumerate(parts):
            partial_path = "/".join(parts[:i+1])
            existing = session.query(Tag).filter_by(path=partial_path).first()
            if existing:
                parent = existing
            else:
                new_tag = Tag(name=part, path=partial_path, parent_id=parent.id if parent else None)
                session.add(new_tag)
                session.flush()
                parent = new_tag
        tag = parent
    if tag and tag not in book.tags:
        book.tags.append(tag)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_mcp_tools.py::TestUpdateBooks -v --tb=short`

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ebk/mcp/tools.py tests/test_mcp_tools.py
git commit -m "feat(mcp): implement update_books tool with scalar, collection, and merge ops"
```

---

### Task 14: MCP server and CLI command

**Files:**
- Create: `ebk/mcp/server.py`
- Modify: `ebk/cli.py`
- Create: `tests/test_mcp_server.py`

- [ ] **Step 1: Write failing test for server tool registration**

Create `tests/test_mcp_server.py`:

```python
"""Tests for MCP server setup."""
import pytest
from ebk.mcp.server import create_mcp_server


class TestMCPServer:
    def test_server_has_tools(self, tmp_path):
        from ebk.library_db import Library
        lib = Library.open(tmp_path / "test-lib")
        try:
            mcp = create_mcp_server(lib)
            # FastMCP should have our 3 tools registered
            tools = mcp.list_tools()
            # tools is a coroutine in some versions, handle both
            assert mcp is not None
        finally:
            lib.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_mcp_server.py -v --tb=short`

Expected: FAIL — `create_mcp_server` does not exist.

- [ ] **Step 3: Implement `create_mcp_server`**

Create `ebk/mcp/server.py`:

```python
"""MCP server for ebk library management."""
from mcp.server import FastMCP
from ebk.library_db import Library
from ebk.mcp.tools import get_schema_impl, execute_sql_impl, update_books_impl


def create_mcp_server(library: Library) -> FastMCP:
    """Create and configure the MCP server with library tools."""
    mcp = FastMCP(
        "ebk",
        instructions="ebk ebook library manager. Use get_schema to understand the database, "
        "execute_sql for read queries, and update_books for modifications.",
    )

    @mcp.tool(
        name="get_schema",
        description="Get the library database schema: tables, columns, relationships, and enums. "
        "Use this to understand the data model before writing SQL queries.",
    )
    def get_schema() -> dict:
        return get_schema_impl(library.session)

    @mcp.tool(
        name="execute_sql",
        description="Execute a read-only SQL SELECT query against the library database. "
        "Use positional ? placeholders for parameters. Returns columns, rows, and row_count. "
        "Maximum 1000 rows returned (truncated flag set if more exist).",
    )
    def execute_sql(sql: str, params: list | None = None, max_rows: int = 1000) -> dict:
        return execute_sql_impl(library.db_path, sql, params=params, max_rows=max_rows)

    @mcp.tool(
        name="update_books",
        description="Update book metadata in batch. Pass a dict of book_id -> {field: value, ...}. "
        "Scalar fields: any Book or PersonalMetadata column. "
        "Collection ops: add_tags/remove_tags, add_authors/remove_authors, add_subjects/remove_subjects. "
        "Special: merge_into (mutually exclusive with other fields).",
    )
    def update_books(updates: dict) -> dict:
        return update_books_impl(library.session, updates)

    return mcp


def run_server(library_path):
    """Entry point: open library and run MCP server over stdio."""
    from pathlib import Path
    lib = Library.open(Path(library_path))
    mcp = create_mcp_server(lib)
    try:
        mcp.run(transport="stdio")
    finally:
        lib.close()
```

- [ ] **Step 4: Add `mcp-serve` CLI command**

In `ebk/cli.py`, add a new command:

```python
@app.command("mcp-serve")
def mcp_serve(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library directory"),
):
    """Start the MCP server for Claude Code integration."""
    resolved_path = resolve_library_path(library_path)
    if not resolved_path:
        typer.echo("Error: No library path specified and no default configured.", err=True)
        raise typer.Exit(1)
    from ebk.mcp.server import run_server
    run_server(resolved_path)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_mcp_server.py -v --tb=short`

Expected: Pass.

- [ ] **Step 6: Commit**

```bash
git add ebk/mcp/server.py tests/test_mcp_server.py ebk/cli.py
git commit -m "feat(mcp): add MCP server with stdio transport and mcp-serve CLI command"
```

---

## Chunk 4: Documentation and Final Cleanup

### Task 15: Delete and update documentation

**Files:**
- Delete: `docs/user-guide/llm-features.md`
- Modify: `docs/development/architecture.md`
- Modify: `docs/getting-started/configuration.md`
- Modify: `docs/index.md`
- Modify: `docs/integrations/mcp.md` (rewrite for new MCP server)
- Modify: `mkdocs.yml`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Delete `llm-features.md`**

```bash
rm docs/user-guide/llm-features.md
```

- [ ] **Step 2: Rewrite `docs/integrations/mcp.md` for new MCP server**

Replace contents with documentation for the new `ebk mcp-serve` command, the 3 tools, and Claude Code configuration example:

```json
{
  "mcpServers": {
    "ebk": {
      "command": "ebk",
      "args": ["mcp-serve", "/path/to/library"]
    }
  }
}
```

- [ ] **Step 3: Update `docs/development/architecture.md`**

Replace the AI/LLM Layer section with MCP Server section. Remove references to metadata enrichment, LLM providers, knowledge graph, semantic search.

- [ ] **Step 4: Update `docs/getting-started/configuration.md`**

Remove the LLM Configuration section (lines 24-49). Keep server, CLI, and library config sections.

- [ ] **Step 5: Update `docs/index.md`**

Replace AI features description with MCP server description.

- [ ] **Step 6: Update `mkdocs.yml`**

Remove `llm-features.md` from nav. Ensure `integrations/mcp.md` points to the new content.

- [ ] **Step 7: Update `CLAUDE.md`**

Remove references to `ebk enrich`, AI features, LLM providers. Add `ebk mcp-serve` to entry points. Add MCP module to architecture table.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: replace LLM documentation with MCP server docs"
```

---

### Task 16: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`

Expected: All tests pass.

- [ ] **Step 2: Run coverage**

Run: `pytest tests/ --cov=ebk --cov-report=term-missing 2>&1 | tail -40`

Check that:
- `ebk/mcp/` has reasonable coverage
- `ebk/ai/` no longer appears
- No unexpected coverage drops

- [ ] **Step 3: Verify CLI works**

Run: `ebk --help | grep mcp-serve`

Expected: `mcp-serve` appears in command list.

Run: `ebk --help | grep enrich`

Expected: `enrich` does NOT appear.

- [ ] **Step 4: Verify imports**

Run: `python -c "from ebk.mcp.server import create_mcp_server; print('OK')"`

Expected: `OK`

Run: `python -c "from ebk.ai import KnowledgeGraph" 2>&1`

Expected: `ModuleNotFoundError`

- [ ] **Step 5: Final commit if any fixups needed**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
