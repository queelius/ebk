"""Tests for MCP tool implementations."""
import json
import pytest
from pathlib import Path
from ebk.library_db import Library
from ebk.mcp.tools import get_schema_impl


@pytest.fixture
def lib(tmp_path):
    """Create a test library."""
    library = Library.open(tmp_path / "test-lib")
    yield library
    library.close()


class TestGetSchema:
    def test_returns_tables(self, lib):
        result = get_schema_impl(lib.db_path)
        assert "tables" in result
        assert "books" in result["tables"]
        assert "authors" in result["tables"]

    def test_includes_columns(self, lib):
        result = get_schema_impl(lib.db_path)
        books = result["tables"]["books"]
        assert "columns" in books
        col_names = [c["name"] for c in books["columns"]]
        assert "title" in col_names
        assert "unique_id" in col_names

    def test_includes_foreign_keys(self, lib):
        result = get_schema_impl(lib.db_path)
        # Find a table with foreign keys (e.g., files has book_id)
        has_fk = any(
            len(t.get("foreign_keys", [])) > 0
            for t in result["tables"].values()
        )
        assert has_fk

    def test_includes_relationships(self, lib):
        result = get_schema_impl(lib.db_path)
        books = result["tables"]["books"]
        assert "relationships" in books
        rel_names = [r["name"] for r in books["relationships"]]
        assert "authors" in rel_names or "files" in rel_names

    def test_serializable(self, lib):
        result = get_schema_impl(lib.db_path)
        # Must be JSON-serializable
        serialized = json.dumps(result)
        assert len(serialized) > 0
