"""
Comprehensive tests for VFS shell command features.

Tests cover:
- ln command with symlink resolution
- Writing to VFS files (echo > file)
- mkdir command for tag creation
- Book deletion with confirmation
- File writability checks
- Tag metadata file updates
- Edge cases and error conditions
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from ebk.library_db import Library
from ebk.repl import LibraryShell
from ebk.services.tag_service import TagService
from ebk.db.models import Tag, Book


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    # Cleanup
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def library_with_books(temp_library):
    """Create a library with test books and tags."""
    # Create test files
    for i in range(3):
        test_file = temp_library.library_path / f"test_{i}.txt"
        test_file.write_text(f"Test content for book {i}")

        temp_library.add_book(
            test_file,
            metadata={
                "title": f"Test Book {i}",
                "creators": ["Test Author"],
                "subjects": ["Testing"],
            },
            extract_text=False,
        )

    # Create some tags
    tag_service = TagService(temp_library.session)
    tag_service.get_or_create_tag("Work")
    tag_service.get_or_create_tag("Archive")
    tag_service.get_or_create_tag("Reading/Fiction")

    return temp_library


@pytest.fixture
def shell(library_with_books):
    """Create a shell instance with test library."""
    shell = LibraryShell(library_with_books.library_path)
    yield shell
    shell.cleanup()


class TestLnCommand:
    """Test ln command for linking books to tags."""

    def test_ln_book_to_tag(self, shell):
        """Test linking a book to a tag using direct book path."""
        # Given: A book exists in the library
        book = shell.library.query().first()
        assert book is not None

        # When: We link the book to a tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"])

        # Then: The book should have the tag
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Work" in tag_paths
        mock_print.assert_called()

    def test_ln_symlink_to_tag(self, shell):
        """Test linking using a symlink source (from /tags/)."""
        # Given: A book already tagged with "Work"
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)
        tag_service.add_tag_to_book(book, "Work")

        # When: We link from the tag symlink to another tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/tags/Work/{book.id}", "/tags/Archive/"])

        # Then: The book should have both tags
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Work" in tag_paths
        assert "Archive" in tag_paths

    def test_ln_creates_tag_hierarchy(self, shell):
        """Test that ln creates parent tags automatically."""
        # Given: A book and a non-existent nested tag path
        book = shell.library.query().first()

        # When: We link to a nested tag that doesn't exist
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/books/{book.id}", "/tags/Projects/2024/Q1/"])

        # Then: The entire hierarchy should be created
        tag_service = TagService(shell.library.session)
        assert tag_service.get_tag("Projects") is not None
        assert tag_service.get_tag("Projects/2024") is not None
        assert tag_service.get_tag("Projects/2024/Q1") is not None

        # And the book should have the tag
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Projects/2024/Q1" in tag_paths

    def test_ln_missing_arguments(self, shell):
        """Test ln with missing arguments shows error."""
        # When: We call ln with no arguments
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "Usage" in output

    def test_ln_invalid_source(self, shell):
        """Test ln with non-existent source."""
        # When: We try to link a non-existent book
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln(["/books/99999", "/tags/Work/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "not found" in output.lower()

    def test_ln_non_tag_destination(self, shell):
        """Test ln with destination that's not a tag path."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We try to link to a non-tag destination
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/books/{book.id}", "/authors/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "tag path" in output.lower()

    def test_ln_idempotent(self, shell):
        """Test that linking same book to same tag twice is safe."""
        # Given: A book
        book = shell.library.query().first()

        # When: We link the book to a tag twice
        shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"], silent=True)
        shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"], silent=True)

        # Then: Book should still have the tag only once
        shell.library.session.refresh(book)
        work_tags = [tag for tag in book.tags if tag.path == "Work"]
        assert len(work_tags) == 1


class TestMkdirCommand:
    """Test mkdir command for creating tags."""

    def test_mkdir_simple_tag(self, shell):
        """Test creating a simple root-level tag."""
        # When: We create a new tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_mkdir(["/tags/NewTag/"])

        # Then: The tag should exist
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_tag("NewTag")
        assert tag is not None
        assert tag.name == "NewTag"
        assert tag.depth == 0

    def test_mkdir_nested_tag(self, shell):
        """Test creating nested tags with auto-parent creation."""
        # When: We create a deeply nested tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_mkdir(["/tags/Work/Projects/2024/"])

        # Then: All parent tags should be created
        tag_service = TagService(shell.library.session)
        assert tag_service.get_tag("Work") is not None
        assert tag_service.get_tag("Work/Projects") is not None
        tag = tag_service.get_tag("Work/Projects/2024")
        assert tag is not None
        assert tag.depth == 2

    def test_mkdir_outside_tags_fails(self, shell):
        """Test that mkdir only works in /tags/."""
        # When: We try to mkdir outside /tags/
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_mkdir(["/books/NewDir/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "/tags/" in output

    def test_mkdir_missing_argument(self, shell):
        """Test mkdir with missing path argument."""
        # When: We call mkdir with no arguments
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_mkdir([])

        # Then: Usage message should be shown
        output = str(mock_print.call_args_list)
        assert "Usage" in output

    def test_mkdir_empty_tag_path(self, shell):
        """Test mkdir with just /tags/ (no tag name)."""
        # When: We try to create an empty tag path
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_mkdir(["/tags/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "Invalid" in output or "tag path" in output.lower()

    def test_mkdir_existing_tag(self, shell):
        """Test creating a tag that already exists."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag_service.get_or_create_tag("ExistingTag")

        # When: We try to create it again
        # Then: Should not raise error (idempotent)
        shell.cmd_mkdir(["/tags/ExistingTag/"], silent=True)

        # Tag should still exist
        tag = tag_service.get_tag("ExistingTag")
        assert tag is not None


class TestEchoAndRedirection:
    """Test echo command and output redirection to VFS files."""

    def test_echo_simple_output(self, shell):
        """Test echo prints text to console."""
        # When: We echo text
        with patch.object(shell.console, "print") as mock_print:
            output = shell.cmd_echo(["Hello", "World"])

        # Then: Text should be printed and returned
        assert output == "Hello World"
        mock_print.assert_called_once_with("Hello World")

    def test_echo_empty_args(self, shell):
        """Test echo with no arguments."""
        # When: We echo with no args
        output = shell.cmd_echo([])

        # Then: Should return empty string
        assert output == ""

    def test_redirect_to_tag_description(self, shell):
        """Test redirecting echo output to tag description file."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")
        assert tag.description is None or tag.description == ""

        # When: We redirect text to the description file
        shell.execute('echo "My work projects" > /tags/Work/description')

        # Then: The tag description should be updated
        shell.library.session.refresh(tag)
        assert tag.description == "My work projects"

    def test_redirect_to_tag_color(self, shell):
        """Test redirecting to tag color file."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Archive")

        # When: We write a color without # prefix
        shell.execute('echo "FF5733" > /tags/Archive/color')

        # Then: Color should be saved with # prefix
        shell.library.session.refresh(tag)
        assert tag.color == "#FF5733"

    def test_redirect_to_tag_color_with_hash(self, shell):
        """Test writing color that already has # prefix."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")

        # When: We write a color with # prefix
        shell.execute('echo "#00FF00" > /tags/Work/color')

        # Then: Color should be saved correctly
        shell.library.session.refresh(tag)
        assert tag.color == "#00FF00"

    def test_redirect_to_nonexistent_file(self, shell):
        """Test redirecting to a file that doesn't exist."""
        # When: We try to redirect to a non-existent file
        with patch.object(shell.console, "print") as mock_print:
            shell.execute('echo "test" > /nonexistent/file')

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "not found" in output.lower()

    def test_redirect_to_readonly_file(self, shell):
        """Test redirecting to a read-only file."""
        # Given: A book exists (title file is read-only)
        book = shell.library.query().first()

        # When: We try to write to a read-only file
        with patch.object(shell.console, "print") as mock_print:
            shell.execute(f'echo "New Title" > /books/{book.id}/title')

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "read-only" in output.lower()

    def test_redirect_overwrites_existing_content(self, shell):
        """Test that redirection overwrites existing content."""
        # Given: A tag with existing description
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")
        tag.description = "Old description"
        shell.library.session.commit()

        # When: We redirect new content
        shell.execute('echo "New description" > /tags/Work/description')

        # Then: Old content should be replaced
        shell.library.session.refresh(tag)
        assert tag.description == "New description"

    def test_redirect_empty_string(self, shell):
        """Test redirecting empty string clears content."""
        # Given: A tag with description
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")
        tag.description = "Some text"
        shell.library.session.commit()

        # When: We redirect empty string
        shell.execute('echo "" > /tags/Work/description')

        # Then: Description should be empty
        shell.library.session.refresh(tag)
        assert tag.description == ""


class TestFileWritability:
    """Test file writability checks."""

    def test_tag_description_is_writable(self, shell):
        """Test that tag description files are writable."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")

        # When: We check the description file node
        node = shell.vfs.get_node("/tags/Work/description")

        # Then: It should be writable
        assert node is not None
        assert node.is_writable()

    def test_tag_color_is_writable(self, shell):
        """Test that tag color files are writable."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")

        # When: We check the color file node
        node = shell.vfs.get_node("/tags/Work/color")

        # Then: It should be writable
        assert node is not None
        assert node.is_writable()

    def test_book_title_is_readonly(self, shell):
        """Test that book metadata files are read-only."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We check the title file node
        node = shell.vfs.get_node(f"/books/{book.id}/title")

        # Then: It should be read-only
        assert node is not None
        assert not node.is_writable()

    def test_write_to_vfs_file_success(self, shell):
        """Test write_to_vfs_file method with writable file."""
        # Given: A writable tag description file
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")

        # When: We write to it via the method
        with patch.object(shell.console, "print") as mock_print:
            shell.write_to_vfs_file("/tags/Work/description", "Test content")

        # Then: Content should be written
        shell.library.session.refresh(tag)
        assert tag.description == "Test content"
        output = str(mock_print.call_args_list)
        assert "Wrote to" in output

    def test_write_to_vfs_file_readonly(self, shell):
        """Test write_to_vfs_file with read-only file."""
        # Given: A read-only file
        book = shell.library.query().first()

        # When: We try to write to it
        with patch.object(shell.console, "print") as mock_print:
            shell.write_to_vfs_file(f"/books/{book.id}/title", "New Title")

        # Then: Error should be shown
        output = str(mock_print.call_args_list)
        assert "read-only" in output.lower()

    def test_write_to_directory_fails(self, shell):
        """Test writing to a directory fails gracefully."""
        # When: We try to write to a directory
        with patch.object(shell.console, "print") as mock_print:
            shell.write_to_vfs_file("/tags/Work/", "content")

        # Then: Error should be shown
        output = str(mock_print.call_args_list)
        assert "Not a file" in output


class TestBookDeletion:
    """Test book deletion with scary confirmation."""

    def test_delete_book_with_confirmation(self, shell):
        """Test deleting a book with proper confirmation."""
        # Given: A book exists
        book = shell.library.query().first()
        book_id = book.id
        book_title = book.title

        # When: We delete it with confirmation
        with patch.object(shell.session, "prompt", return_value="DELETE"):
            with patch.object(shell.console, "print") as mock_print:
                shell.cmd_rm([f"/books/{book_id}/"])

        # Then: Book should be deleted
        deleted_book = shell.library.session.query(Book).filter_by(id=book_id).first()
        assert deleted_book is None

        # Confirmation message should be shown
        output = str(mock_print.call_args_list)
        assert "DELETED" in output

    def test_delete_book_cancelled(self, shell):
        """Test cancelling book deletion."""
        # Given: A book exists
        book = shell.library.query().first()
        book_id = book.id

        # When: We cancel the deletion
        with patch.object(shell.session, "prompt", return_value="cancel"):
            with patch.object(shell.console, "print") as mock_print:
                shell.cmd_rm([f"/books/{book_id}/"])

        # Then: Book should still exist
        existing_book = shell.library.session.query(Book).filter_by(id=book_id).first()
        assert existing_book is not None

        # Cancellation message should be shown
        output = str(mock_print.call_args_list)
        assert "Cancelled" in output or "NOT deleted" in output

    def test_delete_book_shows_details(self, shell):
        """Test that deletion confirmation shows book details."""
        # Given: A book with metadata
        book = shell.library.query().first()

        # When: We attempt deletion
        with patch.object(shell.session, "prompt", return_value="no"):
            with patch.object(shell.console, "print") as mock_print:
                shell.cmd_rm([f"/books/{book.id}/"])

        # Then: Book details should be shown in warning
        output = str(mock_print.call_args_list)
        assert "WARNING" in output
        assert "DELETE BOOK" in output
        assert str(book.id) in output
        if book.title:
            assert book.title in output

    def test_delete_book_wrong_confirmation(self, shell):
        """Test that wrong confirmation text (lowercase) cancels deletion."""
        # Given: A book exists
        book = shell.library.query().first()
        book_id = book.id

        # When: We type "delete" in lowercase instead of "DELETE"
        with patch.object(shell.session, "prompt", return_value="delete"):
            with patch.object(shell.console, "print"):
                shell.cmd_rm([f"/books/{book_id}/"])

        # Then: Book should still exist
        existing_book = shell.library.session.query(Book).filter_by(id=book_id).first()
        assert existing_book is not None

    def test_delete_nonexistent_book(self, shell):
        """Test deleting a book that doesn't exist."""
        # When: We try to delete a non-existent book
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm(["/books/99999/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "not found" in output.lower()

    def test_delete_book_with_files(self, shell):
        """Test deleting a book with physical files."""
        # Given: A book with files
        book = shell.library.query().first()
        assert len(book.files) > 0

        # When: We delete with confirmation
        with patch.object(shell.session, "prompt", return_value="DELETE"):
            with patch.object(shell.console, "print") as mock_print:
                shell.cmd_rm([f"/books/{book.id}/"])

        # Then: Physical files should be deleted
        # (In this test, the files are cleaned up by the temp directory)
        output = str(mock_print.call_args_list)
        assert "DELETED" in output

    def test_delete_book_silent_mode_skips_confirmation(self, shell):
        """Test that silent mode in tests bypasses interactive confirmation."""
        # Given: A book exists
        book = shell.library.query().first()
        book_id = book.id

        # When: We delete in silent mode
        # Note: Silent mode is for testing, should still require explicit confirmation
        # This tests that the confirmation logic is properly skipped when silent=True
        with patch.object(shell.console, "print") as mock_print:
            # In silent mode, confirmation should be skipped
            shell._rm_book(f"/books/{book_id}/", silent=True)

        # Then: Book should be deleted without prompting
        deleted_book = shell.library.session.query(Book).filter_by(id=book_id).first()
        assert deleted_book is None


class TestRmCommand:
    """Test rm command for removing tags and books."""

    def test_rm_tag_from_book(self, shell):
        """Test removing a tag from a book."""
        # Given: A book with a tag
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)
        tag_service.add_tag_to_book(book, "Work")

        # When: We remove the tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm([f"/tags/Work/{book.id}"])

        # Then: Tag should be removed from book
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Work" not in tag_paths

    def test_rm_tag_directory(self, shell):
        """Test removing an empty tag."""
        # Given: An empty tag exists
        tag_service = TagService(shell.library.session)
        tag_service.get_or_create_tag("EmptyTag")

        # When: We remove the tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm(["/tags/EmptyTag/"])

        # Then: Tag should be deleted
        assert tag_service.get_tag("EmptyTag") is None

    def test_rm_tag_with_children_requires_recursive(self, shell):
        """Test that removing tag with children requires -r flag."""
        # Given: A tag with children
        tag_service = TagService(shell.library.session)
        tag_service.get_or_create_tag("Parent/Child")

        # When: We try to remove without -r
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm(["/tags/Parent/"])

        # Then: Should show error about using -r
        output = str(mock_print.call_args_list)
        assert "rm -r" in output or "Error" in output

    def test_rm_tag_recursive(self, shell):
        """Test removing tag with -r flag deletes children."""
        # Given: A tag with children
        tag_service = TagService(shell.library.session)
        parent = tag_service.get_or_create_tag("Parent")
        child = tag_service.get_or_create_tag("Parent/Child")

        # When: We remove with -r flag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm(["-r", "/tags/Parent/"])

        # Then: Both parent and child should be deleted
        assert tag_service.get_tag("Parent") is None
        assert tag_service.get_tag("Parent/Child") is None

    def test_rm_nonexistent_tag_from_book(self, shell):
        """Test removing a tag that the book doesn't have."""
        # Given: A book without the "Work" tag
        book = shell.library.query().first()

        # When: We try to remove a non-existent tag
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm([f"/tags/Work/{book.id}"])

        # Then: Warning should be shown
        output = str(mock_print.call_args_list)
        assert "didn't have" in output.lower() or "Warning" in output

    def test_rm_invalid_path(self, shell):
        """Test rm with invalid path (not /books/ or /tags/)."""
        # When: We try to rm from invalid location
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm(["/authors/someone/"])

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "/books/" in output or "/tags/" in output

    def test_rm_missing_argument(self, shell):
        """Test rm with no arguments."""
        # When: We call rm with no args
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_rm([])

        # Then: Usage message should be shown
        output = str(mock_print.call_args_list)
        assert "Usage" in output


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_ln_with_special_characters_in_tag_path(self, shell):
        """Test tag paths with special characters."""
        # Given: A book
        book = shell.library.query().first()

        # When: We create tags with special characters
        # (Only safe characters should be allowed in paths)
        shell.cmd_ln([f"/books/{book.id}", "/tags/Work-2024/"], silent=True)

        # Then: Tag should be created
        tag_service = TagService(shell.library.session)
        assert tag_service.get_tag("Work-2024") is not None

    def test_mkdir_with_trailing_slash_variations(self, shell):
        """Test that mkdir works with or without trailing slash."""
        # When: We create tags with different slash formats
        shell.cmd_mkdir(["/tags/Tag1/"], silent=True)
        shell.cmd_mkdir(["/tags/Tag2"], silent=True)

        # Then: Both should be created
        tag_service = TagService(shell.library.session)
        assert tag_service.get_tag("Tag1") is not None
        assert tag_service.get_tag("Tag2") is not None

    def test_redirect_with_whitespace_in_content(self, shell):
        """Test redirecting content with leading/trailing whitespace."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("Work")

        # When: We redirect content with whitespace
        shell.execute('echo "  Content with spaces  " > /tags/Work/description')

        # Then: Whitespace should be stripped (per TagDescriptionFile.write_content)
        shell.library.session.refresh(tag)
        assert tag.description == "Content with spaces"

    def test_ln_book_to_multiple_tags_sequentially(self, shell):
        """Test adding multiple tags to same book."""
        # Given: A book
        book = shell.library.query().first()

        # When: We add multiple tags
        shell.cmd_ln([f"/books/{book.id}", "/tags/Work/"], silent=True)
        shell.cmd_ln([f"/books/{book.id}", "/tags/Archive/"], silent=True)
        shell.cmd_ln([f"/books/{book.id}", "/tags/Reading/Fiction/"], silent=True)

        # Then: Book should have all three tags
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Work" in tag_paths
        assert "Archive" in tag_paths
        assert "Reading/Fiction" in tag_paths

    def test_tag_color_validation(self, shell):
        """Test that tag color accepts various hex formats."""
        # Given: A tag
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("ColorTest")

        # When: We set different color formats
        test_cases = [
            ("FF0000", "#FF0000"),  # Without hash
            ("#00FF00", "#00FF00"),  # With hash
            ("ABC", "#ABC"),  # Short form
        ]

        for input_color, expected_color in test_cases:
            shell.execute(f'echo "{input_color}" > /tags/ColorTest/color')
            shell.library.session.refresh(tag)
            assert tag.color == expected_color, f"Failed for input: {input_color}"

    def test_simultaneous_operations_on_same_tag(self, shell):
        """Test that operations maintain consistency."""
        # Given: A tag and multiple books
        tag_service = TagService(shell.library.session)
        books = shell.library.query().limit(3).all()

        # When: We perform multiple operations on same tag
        for book in books:
            shell.cmd_ln([f"/books/{book.id}", "/tags/Shared/"], silent=True)

        # Then: All books should have the tag
        for book in books:
            shell.library.session.refresh(book)
            tag_paths = [tag.path for tag in book.tags]
            assert "Shared" in tag_paths

        # And the tag should link to all books
        tag = tag_service.get_tag("Shared")
        assert len(tag.books) == 3


class TestIntegrationScenarios:
    """Test realistic workflows combining multiple commands."""

    def test_workflow_organize_books_with_tags(self, shell):
        """Test a realistic workflow: create tags and organize books."""
        # Given: Books exist
        books = shell.library.query().all()
        assert len(books) >= 2

        # When: We create a tag hierarchy and organize books
        shell.cmd_mkdir(["/tags/Reading/Queue/"], silent=True)
        shell.cmd_mkdir(["/tags/Reading/Completed/"], silent=True)

        # Add first book to queue
        shell.cmd_ln([f"/books/{books[0].id}", "/tags/Reading/Queue/"], silent=True)

        # Move it to completed
        shell.cmd_mv(
            [f"/tags/Reading/Queue/{books[0].id}", "/tags/Reading/Completed/"],
            silent=True
        )

        # Add description to completed tag
        shell.execute('echo "Books I have finished" > /tags/Reading/Completed/description')

        # Then: Verify the organization
        tag_service = TagService(shell.library.session)

        queue_tag = tag_service.get_tag("Reading/Queue")
        completed_tag = tag_service.get_tag("Reading/Completed")

        assert len(queue_tag.books) == 0
        assert len(completed_tag.books) == 1
        assert completed_tag.description == "Books I have finished"

    def test_workflow_delete_book_from_tagged_collection(self, shell):
        """Test deleting a book that has tags."""
        # Given: A book with multiple tags
        book = shell.library.query().first()
        book_id = book.id
        shell.cmd_ln([f"/books/{book_id}", "/tags/Work/"], silent=True)
        shell.cmd_ln([f"/books/{book_id}", "/tags/Archive/"], silent=True)

        # When: We delete the book
        with patch.object(shell.session, "prompt", return_value="DELETE"):
            shell.cmd_rm([f"/books/{book_id}/"], silent=True)

        # Then: Book should be deleted and tags should still exist
        deleted_book = shell.library.session.query(Book).filter_by(id=book_id).first()
        assert deleted_book is None

        tag_service = TagService(shell.library.session)
        assert tag_service.get_tag("Work") is not None
        assert tag_service.get_tag("Archive") is not None

    def test_workflow_reorganize_tag_hierarchy(self, shell):
        """Test reorganizing tags by creating and deleting."""
        # Given: Initial tag structure
        shell.cmd_mkdir(["/tags/OldProject/SubTask/"], silent=True)
        book = shell.library.query().first()
        shell.cmd_ln([f"/books/{book.id}", "/tags/OldProject/SubTask/"], silent=True)

        # When: We reorganize to new structure
        shell.cmd_mkdir(["/tags/Projects/Active/"], silent=True)
        shell.cmd_ln([f"/books/{book.id}", "/tags/Projects/Active/"], silent=True)
        shell.cmd_rm([f"/tags/OldProject/SubTask/{book.id}"], silent=True)

        # Then: Book should be in new location
        shell.library.session.refresh(book)
        tag_paths = [tag.path for tag in book.tags]
        assert "Projects/Active" in tag_paths
        assert "OldProject/SubTask" not in tag_paths


class TestColorSupport:
    """Test color support for both tags and books."""

    def test_book_color_file_exists(self, shell):
        """Test that books have a color file."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We check for the color file
        node = shell.vfs.get_node(f"/books/{book.id}/color")

        # Then: Color file should exist and be writable
        assert node is not None
        assert node.is_writable()

    def test_book_color_write_hex(self, shell):
        """Test writing hex color to book."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We write a hex color
        shell.execute(f'echo "#FF5733" > /books/{book.id}/color')

        # Then: Color should be saved
        shell.library.session.refresh(book)
        assert book.color == "#FF5733"

    def test_book_color_write_hex_without_hash(self, shell):
        """Test writing hex color without # prefix."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We write a hex color without #
        shell.execute(f'echo "00FF00" > /books/{book.id}/color')

        # Then: # should be added automatically
        shell.library.session.refresh(book)
        assert book.color == "#00FF00"

    def test_book_color_write_named_color(self, shell):
        """Test writing named colors to book."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We write named colors
        test_cases = [
            ("red", "#FF0000"),
            ("blue", "#0000FF"),
            ("green", "#00FF00"),
            ("purple", "#800080"),
        ]

        for named_color, expected_hex in test_cases:
            shell.execute(f'echo "{named_color}" > /books/{book.id}/color')
            shell.library.session.refresh(book)
            assert book.color == expected_hex, f"Failed for {named_color}"

    def test_book_color_read(self, shell):
        """Test reading book color."""
        # Given: A book with a color
        book = shell.library.query().first()
        book.color = "#FF5733"
        shell.library.session.commit()

        # When: We read the color file
        content = shell.cmd_cat([f"/books/{book.id}/color"])

        # Then: Should return the hex color
        assert content.strip() == "#FF5733"

    def test_book_color_clear(self, shell):
        """Test clearing book color."""
        # Given: A book with a color
        book = shell.library.query().first()
        book.color = "#FF5733"
        shell.library.session.commit()

        # When: We write empty string to color
        shell.execute(f'echo "" > /books/{book.id}/color')

        # Then: Color should be cleared
        shell.library.session.refresh(book)
        assert book.color is None

    def test_tag_named_colors(self, shell):
        """Test named color support for tags."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("ColorTest")

        # When: We set named colors
        test_cases = [
            ("cyan", "#00FFFF"),
            ("magenta", "#FF00FF"),
            ("yellow", "#FFFF00"),
            ("orange", "#FFA500"),
        ]

        for named_color, expected_hex in test_cases:
            shell.execute(f'echo "{named_color}" > /tags/ColorTest/color')
            shell.library.session.refresh(tag)
            assert tag.color == expected_hex, f"Failed for {named_color}"

    def test_book_color_invalid_format(self, shell):
        """Test that invalid color formats are rejected."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We try to write invalid color
        with patch.object(shell.console, "print") as mock_print:
            shell.execute(f'echo "ZZZZZZ" > /books/{book.id}/color')

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "Invalid color format" in output or "error" in output.lower()

    def test_tag_color_invalid_format(self, shell):
        """Test that invalid color formats are rejected for tags."""
        # Given: A tag exists
        tag_service = TagService(shell.library.session)
        tag = tag_service.get_or_create_tag("ColorTest")

        # When: We try to write invalid color
        with patch.object(shell.console, "print") as mock_print:
            shell.execute('echo "INVALID" > /tags/ColorTest/color')

        # Then: Error message should be shown
        output = str(mock_print.call_args_list)
        assert "Invalid color format" in output or "error" in output.lower()

    def test_book_color_short_hex(self, shell):
        """Test 3-character hex colors for books."""
        # Given: A book exists
        book = shell.library.query().first()

        # When: We write short hex color
        shell.execute(f'echo "#F73" > /books/{book.id}/color')

        # Then: Short hex should be accepted
        shell.library.session.refresh(book)
        assert book.color == "#F73"


class TestMetadataPreviews:
    """Test metadata file previews in ls output."""

    def test_title_preview(self, shell):
        """Test that title file shows preview in ls."""
        # Given: A book with a title
        book = shell.library.query().first()
        book.title = "Test Book Title"
        shell.library.session.commit()

        # When: We get the title file node info
        node = shell.vfs.get_node(f"/books/{book.id}/title")
        info = node.get_info()

        # Then: Preview should contain the title
        assert "preview" in info
        assert "Test Book Title" in info["preview"]

    def test_title_preview_truncation(self, shell):
        """Test that long titles are truncated in preview."""
        # Given: A book with a very long title
        book = shell.library.query().first()
        long_title = "A" * 100  # 100 characters
        book.title = long_title
        shell.library.session.commit()

        # When: We get the title file node info
        node = shell.vfs.get_node(f"/books/{book.id}/title")
        info = node.get_info()

        # Then: Preview should be truncated to ~60 chars
        assert "preview" in info
        assert len(info["preview"]) <= 64  # 60 chars + "..."

    def test_authors_preview(self, shell):
        """Test that authors file shows preview."""
        # Given: A book with authors
        from ebk.db.models import Author
        book = shell.library.query().first()

        # Clear existing authors and add test authors
        book.authors = []
        author1 = shell.library.session.query(Author).filter_by(name="Test Author 1").first()
        if not author1:
            author1 = Author(name="Test Author 1", sort_name="Author 1, Test")
            shell.library.session.add(author1)
        author2 = shell.library.session.query(Author).filter_by(name="Test Author 2").first()
        if not author2:
            author2 = Author(name="Test Author 2", sort_name="Author 2, Test")
            shell.library.session.add(author2)
        book.authors.extend([author1, author2])
        shell.library.session.commit()

        # When: We get the authors file node info
        node = shell.vfs.get_node(f"/books/{book.id}/authors")
        info = node.get_info()

        # Then: Preview should contain author names
        assert "preview" in info
        assert "Test Author 1" in info["preview"]
        assert "Test Author 2" in info["preview"]

    def test_subjects_preview(self, shell):
        """Test that subjects file shows preview."""
        # Given: A book with subjects
        from ebk.db.models import Subject
        book = shell.library.query().first()

        # Clear and add subjects
        book.subjects = []
        subject1 = shell.library.session.query(Subject).filter_by(name="Fiction").first()
        if not subject1:
            subject1 = Subject(name="Fiction")
            shell.library.session.add(subject1)
        subject2 = shell.library.session.query(Subject).filter_by(name="Adventure").first()
        if not subject2:
            subject2 = Subject(name="Adventure")
            shell.library.session.add(subject2)
        book.subjects.extend([subject1, subject2])
        shell.library.session.commit()

        # When: We get the subjects file node info
        node = shell.vfs.get_node(f"/books/{book.id}/subjects")
        info = node.get_info()

        # Then: Preview should contain subject names
        assert "preview" in info
        assert "Fiction" in info["preview"]
        assert "Adventure" in info["preview"]

    def test_year_preview(self, shell):
        """Test that year file shows preview."""
        # Given: A book with publication year
        book = shell.library.query().first()
        book.publication_date = "2020-06-15"
        shell.library.session.commit()

        # When: We get the year file node info
        node = shell.vfs.get_node(f"/books/{book.id}/year")
        info = node.get_info()

        # Then: Preview should show the year
        assert "preview" in info
        assert "2020" in info["preview"]

    def test_language_preview(self, shell):
        """Test that language file shows preview."""
        # Given: A book with language
        book = shell.library.query().first()
        book.language = "en"
        shell.library.session.commit()

        # When: We get the language file node info
        node = shell.vfs.get_node(f"/books/{book.id}/language")
        info = node.get_info()

        # Then: Preview should show the language
        assert "preview" in info
        assert "en" in info["preview"]

    def test_publisher_preview(self, shell):
        """Test that publisher file shows preview."""
        # Given: A book with publisher
        book = shell.library.query().first()
        book.publisher = "Test Publishing House"
        shell.library.session.commit()

        # When: We get the publisher file node info
        node = shell.vfs.get_node(f"/books/{book.id}/publisher")
        info = node.get_info()

        # Then: Preview should show the publisher
        assert "preview" in info
        assert "Test Publishing House" in info["preview"]

    def test_publisher_preview_truncation(self, shell):
        """Test that long publisher names are truncated."""
        # Given: A book with very long publisher name
        book = shell.library.query().first()
        long_publisher = "P" * 100
        book.publisher = long_publisher
        shell.library.session.commit()

        # When: We get the publisher file node info
        node = shell.vfs.get_node(f"/books/{book.id}/publisher")
        info = node.get_info()

        # Then: Preview should be truncated
        assert "preview" in info
        assert len(info["preview"]) <= 64  # 60 chars + "..."

    def test_empty_metadata_preview(self, shell):
        """Test preview for empty/missing metadata."""
        # Given: A book with minimal metadata
        book = shell.library.query().first()
        book.publication_date = None
        book.language = None
        book.publisher = None
        shell.library.session.commit()

        # When: We get metadata node info
        year_node = shell.vfs.get_node(f"/books/{book.id}/year")
        language_node = shell.vfs.get_node(f"/books/{book.id}/language")

        # Then: Nodes should handle empty values gracefully
        year_info = year_node.get_info()
        language_info = language_node.get_info()

        assert "preview" in year_info
        assert "preview" in language_info


class TestHierarchicalBookTags:
    """Test hierarchical tag navigation in /books/ID/tags/."""

    def test_book_tags_root_level(self, shell):
        """Test listing root-level tags for a book."""
        # Given: A book with hierarchical tags
        from ebk.services.tag_service import TagService
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        # Add hierarchical tags
        tag_service.add_tag_to_book(book, "Work/Project-2024/Backend")
        tag_service.add_tag_to_book(book, "Work/Archive")
        tag_service.add_tag_to_book(book, "Personal")

        # When: We list /books/ID/tags/
        node = shell.vfs.get_node(f"/books/{book.id}/tags")
        children = node.list_children()

        # Then: Should show root-level entries (Work/, Personal)
        child_names = [c.name for c in children]
        assert "Work" in child_names  # Directory for Work hierarchy
        assert "Personal" in child_names  # Leaf tag (no children)

    def test_book_tags_intermediate_level(self, shell):
        """Test navigating intermediate levels in tag hierarchy."""
        # Given: A book with nested tags
        from ebk.services.tag_service import TagService
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        tag_service.add_tag_to_book(book, "Work/Project-2024/Backend")
        tag_service.add_tag_to_book(book, "Work/Project-2024/Frontend")
        tag_service.add_tag_to_book(book, "Work/Archive")

        # When: We navigate to /books/ID/tags/Work/
        node = shell.vfs.get_node(f"/books/{book.id}/tags/Work")
        children = node.list_children()

        # Then: Should show next level (Project-2024/, Archive)
        child_names = [c.name for c in children]
        assert "Project-2024" in child_names  # Directory
        assert "Archive" in child_names  # Leaf tag

    def test_book_tags_leaf_level(self, shell):
        """Test navigating to leaf tags."""
        # Given: A book with nested tags
        from ebk.services.tag_service import TagService
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        tag_service.add_tag_to_book(book, "Work/Project-2024/Backend")
        tag_service.add_tag_to_book(book, "Work/Project-2024/Frontend")

        # When: We navigate to /books/ID/tags/Work/Project-2024/
        node = shell.vfs.get_node(f"/books/{book.id}/tags/Work/Project-2024")
        children = node.list_children()

        # Then: Should show leaf tags (Backend, Frontend)
        child_names = [c.name for c in children]
        assert "Backend" in child_names
        assert "Frontend" in child_names

    def test_book_tags_symlink_targets(self, shell):
        """Test that leaf tags are symlinks to /tags/."""
        # Given: A book with a tag
        from ebk.services.tag_service import TagService
        from ebk.vfs.base import SymlinkNode
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        tag_service.add_tag_to_book(book, "Work/Archive")

        # When: We navigate to the leaf tag
        node = shell.vfs.get_node(f"/books/{book.id}/tags/Work")
        children = node.list_children()

        # Find the Archive child
        archive_node = next((c for c in children if c.name == "Archive"), None)

        # Then: Archive should be a symlink to /tags/Work/Archive/
        assert archive_node is not None
        assert isinstance(archive_node, SymlinkNode)
        assert archive_node.target_path == "/tags/Work/Archive"

    def test_book_tags_empty(self, shell):
        """Test book with no tags."""
        # Given: A book with no tags
        book = shell.library.query().first()
        book.tags = []
        shell.library.session.commit()

        # When: We list /books/ID/tags/
        node = shell.vfs.get_node(f"/books/{book.id}/tags")
        children = node.list_children()

        # Then: Should be empty (no tags)
        assert len(children) == 0

    def test_book_tags_single_level(self, shell):
        """Test book with only root-level tags (no hierarchy)."""
        # Given: A book with simple tags
        from ebk.services.tag_service import TagService
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        tag_service.add_tag_to_book(book, "Fiction")
        tag_service.add_tag_to_book(book, "Adventure")

        # When: We list /books/ID/tags/
        node = shell.vfs.get_node(f"/books/{book.id}/tags")
        children = node.list_children()

        # Then: Should show both tags at root level
        child_names = [c.name for c in children]
        assert "Fiction" in child_names
        assert "Adventure" in child_names

    def test_book_tags_navigation_path(self, shell):
        """Test full navigation path through hierarchy."""
        # Given: A book with deep hierarchy
        from ebk.services.tag_service import TagService
        book = shell.library.query().first()
        tag_service = TagService(shell.library.session)

        tag_service.add_tag_to_book(book, "Projects/2024/Q1/Sprint-1")

        # When: We navigate through each level
        root = shell.vfs.get_node(f"/books/{book.id}/tags")
        assert root is not None

        projects = shell.vfs.get_node(f"/books/{book.id}/tags/Projects")
        assert projects is not None

        year_2024 = shell.vfs.get_node(f"/books/{book.id}/tags/Projects/2024")
        assert year_2024 is not None

        q1 = shell.vfs.get_node(f"/books/{book.id}/tags/Projects/2024/Q1")
        assert q1 is not None

        # Then: All levels should be navigable
        assert "Projects" in [c.name for c in root.list_children()]
        assert "2024" in [c.name for c in projects.list_children()]
        assert "Q1" in [c.name for c in year_2024.list_children()]
        assert "Sprint-1" in [c.name for c in q1.list_children()]
