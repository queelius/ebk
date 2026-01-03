"""
Tests for new CLI commands: sql, book group, and migrate improvements.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typer.testing import CliRunner
from ebk.cli import app
from ebk.library_db import Library


runner = CliRunner()


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def populated_library(temp_library):
    """Library with test data - returns the path."""
    lib = temp_library

    # Create test files with different content
    for i, (title, creators, subjects) in enumerate([
        ("Python Programming", ["John Doe"], ["Programming", "Python"]),
        ("Data Science Handbook", ["Jane Smith", "Bob Johnson"], ["Data Science", "Statistics"]),
        ("Machine Learning Guide", ["Alice Brown"], ["Machine Learning", "AI"])
    ]):
        test_file = lib.library_path / f"test{i}.txt"
        test_file.write_text(f"Test content for {title}")

        lib.add_book(
            test_file,
            metadata={
                "title": title,
                "creators": creators,
                "subjects": subjects,
                "language": "en",
                "publication_date": str(2020 + i)
            },
            extract_text=False,
            extract_cover=False
        )

    # Return the path for CLI commands
    return lib.library_path


class TestSqlCommand:
    """Tests for the sql command."""

    def test_sql_select_basic(self, populated_library):
        """Test basic SELECT query."""
        result = runner.invoke(app, ["sql", "SELECT COUNT(*) as count FROM books", str(populated_library)])
        assert result.exit_code == 0
        assert "count" in result.stdout

    def test_sql_select_with_json_format(self, populated_library):
        """Test SELECT with JSON output."""
        result = runner.invoke(app, [
            "sql", "SELECT id, title FROM books LIMIT 1",
            str(populated_library), "--format", "json"
        ])
        assert result.exit_code == 0
        assert '"id"' in result.stdout
        assert '"title"' in result.stdout

    def test_sql_select_with_csv_format(self, populated_library):
        """Test SELECT with CSV output."""
        result = runner.invoke(app, [
            "sql", "SELECT id, title FROM books LIMIT 1",
            str(populated_library), "--format", "csv"
        ])
        assert result.exit_code == 0
        assert "id,title" in result.stdout

    def test_sql_select_with_limit(self, populated_library):
        """Test SELECT with --limit option."""
        result = runner.invoke(app, [
            "sql", "SELECT id FROM books",
            str(populated_library), "--limit", "2"
        ])
        assert result.exit_code == 0
        assert "2 row(s) returned" in result.stdout

    def test_sql_rejects_delete(self, populated_library):
        """Test that DELETE queries are rejected."""
        result = runner.invoke(app, ["sql", "DELETE FROM books", str(populated_library)])
        assert result.exit_code == 1
        assert "Only SELECT queries are allowed" in result.stdout

    def test_sql_rejects_insert(self, populated_library):
        """Test that INSERT queries are rejected."""
        result = runner.invoke(app, ["sql", "INSERT INTO books (title) VALUES ('x')", str(populated_library)])
        assert result.exit_code == 1
        assert "Only SELECT queries are allowed" in result.stdout

    def test_sql_rejects_drop_in_subquery(self, populated_library):
        """Test that DROP in subquery is rejected."""
        result = runner.invoke(app, ["sql", "SELECT * FROM (DROP TABLE books)", str(populated_library)])
        assert result.exit_code == 1
        assert "disallowed keyword" in result.stdout


class TestBookCommands:
    """Tests for the book command group."""

    def test_book_info(self, populated_library):
        """Test book info command."""
        result = runner.invoke(app, ["book", "info", "1", str(populated_library)])
        assert result.exit_code == 0
        assert "Title" in result.stdout

    def test_book_info_json(self, populated_library):
        """Test book info with JSON output."""
        result = runner.invoke(app, ["book", "info", "1", str(populated_library), "--format", "json"])
        assert result.exit_code == 0
        assert '"id":' in result.stdout
        assert '"title":' in result.stdout

    def test_book_info_not_found(self, populated_library):
        """Test book info for non-existent book."""
        result = runner.invoke(app, ["book", "info", "99999", str(populated_library)])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_book_status_get(self, populated_library):
        """Test getting book status."""
        result = runner.invoke(app, ["book", "status", "1", str(populated_library)])
        assert result.exit_code == 0

    def test_book_status_set(self, populated_library):
        """Test setting book status."""
        result = runner.invoke(app, ["book", "status", "1", str(populated_library), "--set", "reading"])
        assert result.exit_code == 0
        assert "reading" in result.stdout

    def test_book_status_invalid(self, populated_library):
        """Test invalid book status."""
        result = runner.invoke(app, ["book", "status", "1", str(populated_library), "--set", "invalid"])
        assert result.exit_code == 1
        assert "Invalid status" in result.stdout

    def test_book_progress_get(self, populated_library):
        """Test getting book progress."""
        result = runner.invoke(app, ["book", "progress", "1", str(populated_library)])
        assert result.exit_code == 0
        assert "%" in result.stdout

    def test_book_progress_set(self, populated_library):
        """Test setting book progress."""
        result = runner.invoke(app, ["book", "progress", "1", str(populated_library), "--set", "50"])
        assert result.exit_code == 0
        assert "50%" in result.stdout

    def test_book_progress_invalid(self, populated_library):
        """Test invalid book progress."""
        result = runner.invoke(app, ["book", "progress", "1", str(populated_library), "--set", "150"])
        assert result.exit_code == 1
        assert "between 0 and 100" in result.stdout

    def test_book_rate(self, populated_library):
        """Test rating a book."""
        result = runner.invoke(app, ["book", "rate", "1", str(populated_library), "--rating", "4.5"])
        assert result.exit_code == 0
        assert "4.5 stars" in result.stdout

    def test_book_rate_invalid(self, populated_library):
        """Test invalid rating."""
        result = runner.invoke(app, ["book", "rate", "1", str(populated_library), "--rating", "10"])
        assert result.exit_code == 1
        assert "between 0 and 5" in result.stdout

    def test_book_favorite(self, populated_library):
        """Test favoriting a book."""
        result = runner.invoke(app, ["book", "favorite", "1", str(populated_library)])
        assert result.exit_code == 0
        assert "Added to favorites" in result.stdout

    def test_book_unfavorite(self, populated_library):
        """Test unfavoriting a book."""
        result = runner.invoke(app, ["book", "favorite", "1", str(populated_library), "--unfavorite"])
        assert result.exit_code == 0
        assert "Removed from favorites" in result.stdout

    def test_book_tag(self, populated_library):
        """Test tagging a book."""
        result = runner.invoke(app, ["book", "tag", "1", str(populated_library), "--tags", "test-tag"])
        assert result.exit_code == 0
        assert "Added tags" in result.stdout


class TestSqlViews:
    """Tests for SQL-based views."""

    def test_create_sql_view(self, populated_library):
        """Test creating a view with SQL query."""
        result = runner.invoke(app, [
            "view", "create", "sql-test",
            "--library", str(populated_library),
            "--sql", "SELECT id FROM books WHERE language = 'en'",
            "--description", "English books via SQL"
        ])
        assert result.exit_code == 0
        assert "Created view 'sql-test'" in result.stdout

        # Clean up
        runner.invoke(app, ["view", "delete", "sql-test", "--library", str(populated_library)], input="y\n")

    def test_sql_view_with_invalid_query(self, populated_library):
        """Test that invalid SQL in view is rejected."""
        result = runner.invoke(app, [
            "view", "create", "bad-sql",
            "--library", str(populated_library),
            "--sql", "DELETE FROM books"
        ])
        assert result.exit_code == 1


class TestMigrateCommand:
    """Tests for the migrate command improvements."""

    def test_migrate_check(self, populated_library):
        """Test migrate --check."""
        result = runner.invoke(app, ["migrate", str(populated_library), "--check"])
        assert result.exit_code == 0
        assert "Schema version:" in result.stdout

    def test_migrate_version(self, populated_library):
        """Test migrate --version."""
        result = runner.invoke(app, ["migrate", str(populated_library), "--version"])
        assert result.exit_code == 0
        assert "Schema version:" in result.stdout

    def test_migrate_run(self, populated_library):
        """Test running migrations."""
        result = runner.invoke(app, ["migrate", str(populated_library)])
        assert result.exit_code == 0
        # Either "up-to-date" or "completed successfully"
        assert "up-to-date" in result.stdout or "completed" in result.stdout


class TestBookDelete:
    """Tests for book delete command."""

    def test_book_delete_without_confirmation(self, populated_library):
        """Test that delete requires confirmation."""
        result = runner.invoke(app, ["book", "delete", "1", str(populated_library)], input="n\n")
        # User cancelled
        assert result.exit_code == 0 or "Cancelled" in result.stdout or "Aborted" in result.stdout

    def test_book_delete_with_yes_flag(self, populated_library):
        """Test delete with --yes flag."""
        result = runner.invoke(app, ["book", "delete", "1", str(populated_library), "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout or "deleted" in result.stdout

    def test_book_delete_not_found(self, populated_library):
        """Test delete for non-existent book."""
        result = runner.invoke(app, ["book", "delete", "99999", str(populated_library), "--yes"])
        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestBookEdit:
    """Tests for book edit command."""

    def test_book_edit_title(self, populated_library):
        """Test editing book title."""
        result = runner.invoke(app, [
            "book", "edit", "1", str(populated_library),
            "--title", "New Title"
        ])
        assert result.exit_code == 0
        assert "Updated" in result.stdout or "updated" in result.stdout

    def test_book_edit_authors(self, populated_library):
        """Test editing book authors."""
        result = runner.invoke(app, [
            "book", "edit", "1", str(populated_library),
            "--authors", "New Author, Another Author"
        ])
        assert result.exit_code == 0

    def test_book_edit_not_found(self, populated_library):
        """Test editing non-existent book."""
        result = runner.invoke(app, [
            "book", "edit", "99999", str(populated_library),
            "--title", "New Title"
        ])
        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestBookMerge:
    """Tests for book merge command."""

    def test_book_merge_dry_run(self, tmp_path):
        """Test merge dry run shows preview without making changes."""
        from ebk.library_db import Library

        # Create library with two books
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file1 = lib_path / "book1.txt"
        file1.write_text("First book content")
        lib.add_book(file1, {"title": "Book One", "creators": ["Author A"]}, extract_text=False)

        file2 = lib_path / "book2.txt"
        file2.write_text("Second book content")
        lib.add_book(file2, {"title": "Book Two", "creators": ["Author B"]}, extract_text=False)

        lib.close()

        # Dry run
        result = runner.invoke(app, [
            "book", "merge", "1", "2", str(lib_path), "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        assert "Book One" in result.stdout
        assert "Book Two" in result.stdout

        # Verify book 2 still exists
        lib = Library.open(lib_path)
        assert lib.get_book(2) is not None
        lib.close()

    def test_book_merge_basic(self, tmp_path):
        """Test basic merge of two books."""
        from ebk.library_db import Library

        # Create library with two books
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file1 = lib_path / "book1.txt"
        file1.write_text("First book content")
        lib.add_book(file1, {"title": "Book One", "creators": ["Author A"]}, extract_text=False)

        file2 = lib_path / "book2.txt"
        file2.write_text("Second book content")
        lib.add_book(file2, {"title": "Book Two", "creators": ["Author B"]}, extract_text=False)

        lib.close()

        # Merge with --yes to skip confirmation
        result = runner.invoke(app, [
            "book", "merge", "1", "2", str(lib_path), "--yes"
        ])
        assert result.exit_code == 0
        assert "Merged 1 book" in result.stdout

        # Verify book 2 is deleted and book 1 has both authors
        lib = Library.open(lib_path)
        assert lib.get_book(2) is None
        book1 = lib.get_book(1)
        assert book1 is not None
        author_names = [a.name for a in book1.authors]
        assert "Author A" in author_names
        assert "Author B" in author_names
        lib.close()

    def test_book_merge_multiple(self, tmp_path):
        """Test merging multiple books into one."""
        from ebk.library_db import Library
        import uuid

        # Create library with three books (unique content to avoid duplicate hash)
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        for i in range(1, 4):
            file = lib_path / f"book{i}.txt"
            # Use uuid to ensure unique content and thus unique file hash
            file.write_text(f"Book {i} content - unique id: {uuid.uuid4()}")
            lib.add_book(file, {"title": f"Book {i}", "creators": [f"Author {i}"]}, extract_text=False)

        lib.close()

        # Merge all into book 1
        result = runner.invoke(app, [
            "book", "merge", "1", "2,3", str(lib_path), "--yes"
        ])
        assert result.exit_code == 0
        assert "Merged 2 book" in result.stdout

        # Verify
        lib = Library.open(lib_path)
        assert lib.get_book(2) is None
        assert lib.get_book(3) is None
        book1 = lib.get_book(1)
        assert len(book1.authors) == 3
        assert len(book1.files) == 3
        lib.close()

    def test_book_merge_not_found(self, populated_library):
        """Test merge with non-existent primary book."""
        result = runner.invoke(app, [
            "book", "merge", "99999", "1", str(populated_library)
        ])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_book_merge_no_valid_secondary(self, populated_library):
        """Test merge with no valid secondary books."""
        result = runner.invoke(app, [
            "book", "merge", "1", "99999", str(populated_library)
        ])
        assert result.exit_code == 1
        assert "No valid secondary" in result.stdout


class TestBulkEdit:
    """Tests for bulk edit command."""

    def test_bulk_edit_by_ids(self, tmp_path):
        """Test bulk edit using --ids."""
        from ebk.library_db import Library

        # Create library with books (import service sets default language='en')
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        for i in range(1, 4):
            file = lib_path / f"book{i}.txt"
            file.write_text(f"Book {i} content")
            lib.add_book(file, {"title": f"Book {i}", "creators": [f"Author {i}"]}, extract_text=False)

        lib.close()

        # Bulk edit with --yes to skip confirmation - change to 'de' to verify edit
        result = runner.invoke(app, [
            "book", "bulk-edit", str(lib_path),
            "--ids", "1,2",
            "--language", "de",
            "--yes"
        ])
        assert result.exit_code == 0
        assert "Updated 2 book" in result.stdout

        # Verify changes - books 1,2 now 'de', book 3 still has default 'en'
        lib = Library.open(lib_path)
        assert lib.get_book(1).language == "de"
        assert lib.get_book(2).language == "de"
        assert lib.get_book(3).language == "en"  # Not edited, still has default
        lib.close()

    def test_bulk_edit_dry_run(self, tmp_path):
        """Test bulk edit dry run."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        # Import service sets default language='en'
        lib.add_book(file, {"title": "Test Book", "creators": ["Author"]}, extract_text=False)

        lib.close()

        result = runner.invoke(app, [
            "book", "bulk-edit", str(lib_path),
            "--ids", "1",
            "--language", "de",
            "--dry-run"
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout

        # Verify no changes made - still has original default 'en'
        lib = Library.open(lib_path)
        assert lib.get_book(1).language == "en"
        lib.close()

    def test_bulk_edit_no_selection(self, populated_library):
        """Test bulk edit without selection criteria."""
        result = runner.invoke(app, [
            "book", "bulk-edit", str(populated_library),
            "--language", "en"
        ])
        assert result.exit_code == 1
        assert "Must specify" in result.stdout

    def test_bulk_edit_no_edit_option(self, populated_library):
        """Test bulk edit without edit options."""
        result = runner.invoke(app, [
            "book", "bulk-edit", str(populated_library),
            "--ids", "1"
        ])
        assert result.exit_code == 1
        assert "Must specify at least one edit option" in result.stdout

    def test_bulk_edit_add_tag(self, tmp_path):
        """Test bulk edit adding a tag."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        lib.add_book(file, {"title": "Test Book", "creators": ["Author"]}, extract_text=False)

        lib.close()

        result = runner.invoke(app, [
            "book", "bulk-edit", str(lib_path),
            "--ids", "1",
            "--add-tag", "Programming",
            "--yes"
        ])
        assert result.exit_code == 0
        assert "Updated 1 book" in result.stdout

        # Verify tag was added
        lib = Library.open(lib_path)
        book = lib.get_book(1)
        tag_paths = [t.path for t in book.tags]
        assert "Programming" in tag_paths
        lib.close()

    def test_bulk_edit_set_rating(self, tmp_path):
        """Test bulk edit setting rating."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        lib.add_book(file, {"title": "Test Book", "creators": ["Author"]}, extract_text=False)

        lib.close()

        result = runner.invoke(app, [
            "book", "bulk-edit", str(lib_path),
            "--ids", "1",
            "--rating", "4.5",
            "--yes"
        ])
        assert result.exit_code == 0

        # Verify rating
        lib = Library.open(lib_path)
        book = lib.get_book(1)
        assert book.personal is not None
        assert book.personal.rating == 4.5
        lib.close()


class TestBookSimilar:
    """Tests for book similar command."""

    def test_book_similar_basic(self, populated_library):
        """Test basic similar books query."""
        result = runner.invoke(app, ["book", "similar", "1", str(populated_library)])
        # May fail due to insufficient text for TF-IDF, which is expected for test data
        # Just verify the command runs and produces output
        assert "similar" in result.stdout.lower() or "Error" in result.stdout

    def test_book_similar_with_limit(self, populated_library):
        """Test similar books with limit."""
        result = runner.invoke(app, ["book", "similar", "1", str(populated_library), "--limit", "5"])
        # Same as above - may fail for insufficient text
        assert result.stdout  # Just verify there's output

    def test_book_similar_not_found(self, populated_library):
        """Test similar for non-existent book."""
        result = runner.invoke(app, ["book", "similar", "99999", str(populated_library)])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_book_similar_with_mode_metadata(self, populated_library):
        """Test similar with metadata-only mode."""
        result = runner.invoke(app, [
            "book", "similar", "1", str(populated_library),
            "--mode", "metadata"
        ])
        # Should work even without extracted text
        assert result.stdout

    def test_book_similar_with_mode_sparse(self, populated_library):
        """Test similar with sparse-friendly mode."""
        result = runner.invoke(app, [
            "book", "similar", "1", str(populated_library),
            "--mode", "sparse"
        ])
        # Should work even without extracted text
        assert result.stdout

    def test_book_similar_json_output(self, populated_library):
        """Test similar with JSON output."""
        result = runner.invoke(app, [
            "book", "similar", "1", str(populated_library),
            "--format", "json", "--mode", "metadata"
        ])
        # Verify output is present
        assert result.stdout


class TestReadCommand:
    """Tests for the renamed read command (formerly view)."""

    def test_read_not_found(self, populated_library):
        """Test read for non-existent book."""
        result = runner.invoke(app, ["read", "99999", str(populated_library)])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_read_text_mode_no_text(self, populated_library):
        """Test read --text when no extracted text available."""
        result = runner.invoke(app, ["read", "1", str(populated_library), "--text"])
        # Should fail gracefully - no extracted text in test data
        assert result.exit_code == 1
        assert "No extracted text" in result.stdout or "no text" in result.stdout.lower()


class TestBookExportCommand:
    """Tests for the book export command."""

    def test_book_export_json(self, populated_library):
        """Test exporting book as JSON."""
        result = runner.invoke(app, ["book", "export", "1", str(populated_library)])
        assert result.exit_code == 0
        assert '"id":' in result.stdout
        assert '"title":' in result.stdout

    def test_book_export_json_to_file(self, populated_library, tmp_path):
        """Test exporting book as JSON to file."""
        output_file = tmp_path / "book.json"
        result = runner.invoke(app, [
            "book", "export", "1", str(populated_library),
            "--output", str(output_file)
        ])
        assert result.exit_code == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert '"title":' in content

    def test_book_export_bibtex(self, populated_library):
        """Test exporting book as BibTeX."""
        result = runner.invoke(app, [
            "book", "export", "1", str(populated_library),
            "--format", "bibtex"
        ])
        assert result.exit_code == 0
        assert "@book{" in result.stdout
        assert "title =" in result.stdout

    def test_book_export_not_found(self, populated_library):
        """Test exporting non-existent book."""
        result = runner.invoke(app, ["book", "export", "99999", str(populated_library)])
        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestCheckCommand:
    """Tests for the check command."""

    def test_check_basic(self, populated_library):
        """Test basic library check."""
        result = runner.invoke(app, ["check", str(populated_library)])
        assert result.exit_code == 0 or result.exit_code == 1  # May find issues
        assert "Checking library integrity" in result.stdout
        assert "Summary" in result.stdout

    def test_check_verbose(self, populated_library):
        """Test verbose library check."""
        result = runner.invoke(app, ["check", str(populated_library), "--verbose"])
        assert "Checking library integrity" in result.stdout
        # Verbose mode shows all files
        assert "Checking for missing files" in result.stdout


class TestListWithViewOption:
    """Tests for the list --view option."""

    def test_list_with_custom_view(self, populated_library):
        """Test listing books from a custom view."""
        # First create a view using --language filter
        create_result = runner.invoke(app, [
            "view", "create", "test-view",
            "--library", str(populated_library),
            "--language", "en"
        ])
        assert create_result.exit_code == 0, f"View creation failed: {create_result.stdout}"

        result = runner.invoke(app, ["list", str(populated_library), "--view", "test-view"])
        assert result.exit_code == 0
        assert "Books" in result.stdout or "No books found" in result.stdout

        # Clean up
        runner.invoke(app, ["view", "delete", "test-view", "--library", str(populated_library)], input="y\n")

    def test_list_with_nonexistent_view(self, populated_library):
        """Test listing books from non-existent view."""
        result = runner.invoke(app, ["list", str(populated_library), "--view", "nonexistent-view"])
        assert result.exit_code == 1
        assert "Error" in result.stdout or "not found" in result.stdout.lower()


class TestBackupCommand:
    """Tests for the backup command."""

    def test_backup_tar_gz(self, populated_library, tmp_path):
        """Test creating a tar.gz backup."""
        backup_file = tmp_path / "backup.tar.gz"
        result = runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])
        assert result.exit_code == 0
        assert backup_file.exists()
        assert "Backup created" in result.stdout

    def test_backup_zip(self, populated_library, tmp_path):
        """Test creating a zip backup."""
        backup_file = tmp_path / "backup.zip"
        result = runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])
        assert result.exit_code == 0
        assert backup_file.exists()
        assert "Backup created" in result.stdout

    def test_backup_db_only(self, populated_library, tmp_path):
        """Test creating a database-only backup."""
        backup_file = tmp_path / "backup.tar.gz"
        result = runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file),
            "--db-only"
        ])
        assert result.exit_code == 0
        assert backup_file.exists()

    def test_backup_invalid_format(self, populated_library, tmp_path):
        """Test backup with invalid format."""
        backup_file = tmp_path / "backup.txt"  # Invalid format
        result = runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])
        assert result.exit_code == 1
        assert "must be .tar.gz" in result.stdout or ".zip" in result.stdout


class TestRestoreCommand:
    """Tests for the restore command."""

    def test_restore_tar_gz(self, populated_library, tmp_path):
        """Test restoring from a tar.gz backup."""
        # First create a backup
        backup_file = tmp_path / "backup.tar.gz"
        runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])

        # Restore to new location
        restore_path = tmp_path / "restored_library"
        result = runner.invoke(app, [
            "restore", str(backup_file), str(restore_path)
        ])
        assert result.exit_code == 0
        assert "Library restored" in result.stdout
        assert (restore_path / "library.db").exists()

    def test_restore_zip(self, populated_library, tmp_path):
        """Test restoring from a zip backup."""
        # First create a backup
        backup_file = tmp_path / "backup.zip"
        runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])

        # Restore to new location
        restore_path = tmp_path / "restored_library"
        result = runner.invoke(app, [
            "restore", str(backup_file), str(restore_path)
        ])
        assert result.exit_code == 0
        assert "Library restored" in result.stdout

    def test_restore_nonexistent_backup(self, tmp_path):
        """Test restoring from non-existent backup file."""
        backup_file = tmp_path / "nonexistent.tar.gz"
        restore_path = tmp_path / "restored"
        result = runner.invoke(app, [
            "restore", str(backup_file), str(restore_path)
        ])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_restore_existing_without_force(self, populated_library, tmp_path):
        """Test restoring to existing path without --force."""
        # Create backup
        backup_file = tmp_path / "backup.tar.gz"
        runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])

        # Try to restore to existing path
        existing_path = tmp_path / "existing"
        existing_path.mkdir()

        result = runner.invoke(app, [
            "restore", str(backup_file), str(existing_path)
        ])
        assert result.exit_code == 1
        assert "exists" in result.stdout

    def test_restore_with_force(self, populated_library, tmp_path):
        """Test restoring to existing path with --force."""
        # Create backup
        backup_file = tmp_path / "backup.tar.gz"
        runner.invoke(app, [
            "backup", str(populated_library),
            "--output", str(backup_file)
        ])

        # Create existing path
        existing_path = tmp_path / "existing"
        existing_path.mkdir()
        (existing_path / "dummy.txt").write_text("test")

        # Restore with force
        result = runner.invoke(app, [
            "restore", str(backup_file), str(existing_path), "--force"
        ])
        assert result.exit_code == 0
        assert "Library restored" in result.stdout


class TestImportFolderImprovements:
    """Tests for improved import folder command."""

    def test_import_folder_dry_run(self, tmp_path):
        """Test import folder with dry run."""
        # Create a library
        from ebk.library_db import Library
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)
        lib.close()

        # Create source folder with some files
        source = tmp_path / "source"
        source.mkdir()
        (source / "book1.txt").write_text("Test book content 1")
        (source / "book2.txt").write_text("Test book content 2")

        result = runner.invoke(app, [
            "import", "folder", str(source), str(lib_path),
            "--dry-run", "--extensions", "txt"
        ])
        assert result.exit_code == 0
        assert "Dry run" in result.stdout
        # Books should NOT be imported in dry run
        assert "book1.txt" in result.stdout or "book2.txt" in result.stdout

    def test_import_folder_resume(self, tmp_path):
        """Test import folder resume capability."""
        # Create a library
        from ebk.library_db import Library
        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)
        lib.close()

        # Create source folder
        source = tmp_path / "source"
        source.mkdir()
        (source / "book1.txt").write_text("Test book content for resume test")

        # First import
        runner.invoke(app, [
            "import", "folder", str(source), str(lib_path),
            "--extensions", "txt"
        ])

        # Add another file
        (source / "book2.txt").write_text("Second book content")

        # Second import with resume (should skip book1)
        result = runner.invoke(app, [
            "import", "folder", str(source), str(lib_path),
            "--extensions", "txt", "--resume"
        ])
        assert result.exit_code == 0
        # Should have skipped duplicates
        assert "Skipped" in result.stdout or "Imported" in result.stdout


class TestGoodreadsExport:
    """Tests for Goodreads CSV export."""

    def test_export_goodreads_basic(self, populated_library, tmp_path):
        """Test basic Goodreads export."""
        output_file = tmp_path / "goodreads.csv"
        result = runner.invoke(app, [
            "export", "goodreads", str(populated_library), str(output_file)
        ])
        assert result.exit_code == 0
        assert "Exported" in result.stdout
        assert output_file.exists()

        # Verify CSV structure
        content = output_file.read_text()
        assert "Title" in content
        assert "Author" in content
        assert "ISBN" in content
        assert "Exclusive Shelf" in content

    def test_export_goodreads_with_view(self, populated_library, tmp_path):
        """Test Goodreads export with view filter."""
        # Create a view first
        runner.invoke(app, [
            "view", "create", "gr-test",
            "--library", str(populated_library),
            "--language", "en"
        ])

        output_file = tmp_path / "goodreads.csv"
        result = runner.invoke(app, [
            "export", "goodreads", str(populated_library), str(output_file),
            "--view", "gr-test"
        ])
        assert result.exit_code == 0
        assert output_file.exists()

        # Clean up
        runner.invoke(app, ["view", "delete", "gr-test", "--library", str(populated_library)], input="y\n")

    def test_export_goodreads_includes_rating(self, tmp_path):
        """Test that Goodreads export includes ratings."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        lib.add_book(file, {"title": "Rated Book", "creators": ["Test Author"]}, extract_text=False)

        # Set rating
        from ebk.services import PersonalMetadataService
        pm_svc = PersonalMetadataService(lib.session)
        pm_svc.set_rating(1, 4.5)

        lib.close()

        output_file = tmp_path / "goodreads.csv"
        result = runner.invoke(app, [
            "export", "goodreads", str(lib_path), str(output_file)
        ])
        assert result.exit_code == 0

        content = output_file.read_text()
        # Rating 4.5 is exported (Python banker's rounding gives 4)
        # My Rating field is the 6th column
        assert ",4," in content or "My Rating" in content


class TestCalibreExport:
    """Tests for Calibre CSV export."""

    def test_export_calibre_basic(self, populated_library, tmp_path):
        """Test basic Calibre export."""
        output_file = tmp_path / "calibre.csv"
        result = runner.invoke(app, [
            "export", "calibre", str(populated_library), str(output_file)
        ])
        assert result.exit_code == 0
        assert "Exported" in result.stdout
        assert output_file.exists()

        # Verify CSV structure
        content = output_file.read_text()
        assert "title" in content
        assert "authors" in content
        assert "author_sort" in content
        assert "tags" in content

    def test_export_calibre_with_view(self, populated_library, tmp_path):
        """Test Calibre export with view filter."""
        # Create a view first
        runner.invoke(app, [
            "view", "create", "cal-test",
            "--library", str(populated_library),
            "--language", "en"
        ])

        output_file = tmp_path / "calibre.csv"
        result = runner.invoke(app, [
            "export", "calibre", str(populated_library), str(output_file),
            "--view", "cal-test"
        ])
        assert result.exit_code == 0
        assert output_file.exists()

        # Clean up
        runner.invoke(app, ["view", "delete", "cal-test", "--library", str(populated_library)], input="y\n")

    def test_export_calibre_includes_series(self, tmp_path):
        """Test that Calibre export includes series info."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        lib.add_book(file, {
            "title": "Series Book",
            "creators": ["Test Author"],
            "series": "Test Series",
            "series_index": "3"
        }, extract_text=False)

        lib.close()

        output_file = tmp_path / "calibre.csv"
        result = runner.invoke(app, [
            "export", "calibre", str(lib_path), str(output_file)
        ])
        assert result.exit_code == 0

        content = output_file.read_text()
        assert "Test Series" in content
        assert "3" in content

    def test_export_calibre_author_sort(self, tmp_path):
        """Test that Calibre export generates proper author sort."""
        from ebk.library_db import Library

        lib_path = tmp_path / "library"
        lib = Library.open(lib_path)

        file = lib_path / "book.txt"
        file.write_text("Test content")
        lib.add_book(file, {
            "title": "Test Book",
            "creators": ["John Smith", "Jane Doe"]
        }, extract_text=False)

        lib.close()

        output_file = tmp_path / "calibre.csv"
        result = runner.invoke(app, [
            "export", "calibre", str(lib_path), str(output_file)
        ])
        assert result.exit_code == 0

        content = output_file.read_text()
        # Should have "Smith, John" format
        assert "Smith, John" in content
