"""Tests for MCP tool implementations."""
import json
import pytest
from book_memex.library_db import Library
from book_memex.mcp.tools import get_schema_impl, execute_sql_impl, update_books_impl


@pytest.fixture
def lib(tmp_path):
    """Create a test library."""
    library = Library.open(tmp_path / "test-lib")
    yield library
    library.close()


class TestGetSchema:
    def test_returns_tables(self, lib):
        result = get_schema_impl(lib.session)
        assert "tables" in result
        assert "books" in result["tables"]
        assert "authors" in result["tables"]

    def test_includes_columns(self, lib):
        result = get_schema_impl(lib.session)
        books = result["tables"]["books"]
        assert "columns" in books
        col_names = [c["name"] for c in books["columns"]]
        assert "title" in col_names
        assert "unique_id" in col_names

    def test_includes_foreign_keys(self, lib):
        result = get_schema_impl(lib.session)
        # Find a table with foreign keys (e.g., files has book_id)
        has_fk = any(
            len(t.get("foreign_keys", [])) > 0
            for t in result["tables"].values()
        )
        assert has_fk

    def test_includes_relationships(self, lib):
        result = get_schema_impl(lib.session)
        books = result["tables"]["books"]
        assert "relationships" in books
        rel_names = [r["name"] for r in books["relationships"]]
        assert "authors" in rel_names or "files" in rel_names

    def test_serializable(self, lib):
        result = get_schema_impl(lib.session)
        # Must be JSON-serializable
        serialized = json.dumps(result)
        assert len(serialized) > 0


@pytest.fixture
def populated_library(lib):
    """Library with sample books for testing."""
    from book_memex.db.models import Book, Author
    import uuid
    session = lib.session

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
    return lib


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
        assert "Test/Tag1" in tag_paths

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

    def test_non_integer_book_id_returns_error(self, populated_library):
        result = update_books_impl(
            populated_library.session,
            {"abc": {"title": "Bad ID"}}
        )
        assert "abc" in result["errors"]
        assert not result["updated"]

    def test_partial_batch_error_does_not_rollback_success(self, populated_library):
        books = populated_library.get_all_books()
        book_id = books[0].id
        result = update_books_impl(
            populated_library.session,
            {
                str(book_id): {"title": "Partial Success"},
                "99999": {"title": "Ghost"},
            }
        )
        assert book_id in result["updated"]
        assert 99999 in result["errors"]
        book = populated_library.get_book(book_id)
        assert book.title == "Partial Success"
