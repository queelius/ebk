"""Tests for read-only SQL executor."""
import pytest
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
