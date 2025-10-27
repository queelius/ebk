"""Tests for REPL shell functionality."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ebk.library_db import Library
from ebk.repl import LibraryShell


@pytest.fixture
def test_library(tmp_path):
    """Create a test library with some books."""
    lib_path = tmp_path / "test_library"
    lib = Library.open(lib_path)

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a test book content.")

    # Add a test book
    book = lib.add_book(
        test_file,
        metadata={
            "title": "Test Book",
            "creators": ["Test Author"],
            "subjects": ["Python", "Testing"],
            "description": "A test book",
            "language": "en",
        },
    )

    lib.close()
    return lib_path


def test_shell_initialization(test_library):
    """Test that shell initializes correctly."""
    shell = LibraryShell(test_library)

    assert shell.library is not None
    assert shell.vfs is not None
    assert shell.console is not None
    assert shell.running is True

    shell.cleanup()


def test_shell_pwd(test_library):
    """Test pwd command."""
    shell = LibraryShell(test_library)

    # Should start at root
    assert shell.vfs.pwd() == "/"

    shell.cleanup()


def test_shell_cd(test_library):
    """Test cd command."""
    shell = LibraryShell(test_library)

    # cd to /books
    shell.cmd_cd(["books"])
    assert shell.vfs.pwd() == "/books"

    # cd to /
    shell.cmd_cd(["/"])
    assert shell.vfs.pwd() == "/"

    # cd to /authors
    shell.cmd_cd(["authors"])
    assert shell.vfs.pwd() == "/authors"

    # cd with no args goes to root
    shell.cmd_cd([])
    assert shell.vfs.pwd() == "/"

    shell.cleanup()


def test_shell_ls(test_library):
    """Test ls command."""
    shell = LibraryShell(test_library)

    # ls at root should show books/, authors/, subjects/, tags/
    nodes = shell.vfs.ls(".")
    assert len(nodes) == 4
    names = [n.name for n in nodes]
    assert "books" in names
    assert "authors" in names
    assert "subjects" in names
    assert "tags" in names

    shell.cleanup()


def test_shell_cat(test_library):
    """Test cat command."""
    shell = LibraryShell(test_library)

    # Open library to get book ID
    lib = Library.open(test_library)
    books = lib.query().all()
    assert len(books) > 0
    book_id = books[0].id
    lib.close()

    # cd to book directory
    shell.cmd_cd([f"/books/{book_id}"])

    # Mock console to capture output
    with patch.object(shell.console, "print") as mock_print:
        shell.cmd_cat(["title"])
        # Should have printed the title
        mock_print.assert_called_once()
        args = mock_print.call_args[0][0]
        assert "Test Book" in args

    shell.cleanup()


def test_shell_help(test_library):
    """Test help command."""
    shell = LibraryShell(test_library)

    # Mock console to capture output
    with patch.object(shell.console, "print") as mock_print:
        shell.cmd_help([])
        # Should have printed help
        assert mock_print.called

    shell.cleanup()


def test_shell_exit(test_library):
    """Test exit command."""
    shell = LibraryShell(test_library)

    assert shell.running is True
    shell.cmd_exit([])
    assert shell.running is False

    shell.cleanup()


def test_execute_bash_command(test_library):
    """Test executing bash commands."""
    shell = LibraryShell(test_library)

    # Mock console to capture output
    with patch.object(shell.console, "print") as mock_print:
        shell.execute_bash("echo 'hello world'")
        # Should have printed the output
        mock_print.assert_called()

    shell.cleanup()


def test_get_prompt(test_library):
    """Test prompt generation."""
    shell = LibraryShell(test_library)

    # At root
    prompt = shell.get_prompt()
    assert "ebk:/" in prompt

    # After cd
    shell.cmd_cd(["books"])
    prompt = shell.get_prompt()
    assert "ebk:/books" in prompt

    shell.cleanup()


def test_grep_command(test_library):
    """Test grep command."""
    shell = LibraryShell(test_library)

    # Get book ID
    lib = Library.open(test_library)
    books = lib.query().all()
    book_id = books[0].id
    lib.close()

    # cd to book
    shell.cmd_cd([f"/books/{book_id}"])

    # Mock console to capture grep output
    with patch.object(shell.console, "print") as mock_print:
        # Search for "Test" in title
        shell.cmd_grep(["Test", "title"])
        # Should have printed matches
        assert mock_print.called
        # Check that output contains "Test"
        output = str(mock_print.call_args_list)
        assert "Test" in output

    shell.cleanup()


def test_grep_recursive(test_library):
    """Test grep with recursive flag."""
    shell = LibraryShell(test_library)

    # Mock console to capture grep output
    with patch.object(shell.console, "print") as mock_print:
        # Search recursively from root for "Test"
        shell.cmd_grep(["-r", "Test", "/books"])
        # Should have found matches
        assert mock_print.called

    shell.cleanup()


def test_grep_case_insensitive(test_library):
    """Test grep with case insensitive flag."""
    shell = LibraryShell(test_library)

    # Get book ID
    lib = Library.open(test_library)
    books = lib.query().all()
    book_id = books[0].id
    lib.close()

    # cd to book
    shell.cmd_cd([f"/books/{book_id}"])

    # Mock console to capture grep output
    with patch.object(shell.console, "print") as mock_print:
        # Search case-insensitively for "test" (lowercase)
        shell.cmd_grep(["-i", "test", "title"])
        # Should have found matches
        assert mock_print.called

    shell.cleanup()


def test_find_command(test_library):
    """Test find command with filters."""
    shell = LibraryShell(test_library)

    # Mock console to capture find output
    with patch.object(shell.console, "print") as mock_print:
        # Find books by author
        shell.cmd_find(["author:Test"])
        # Should have printed results (at least 2 calls: header + table)
        assert mock_print.call_count >= 2
        # Check that "Found" is in one of the calls
        output = str(mock_print.call_args_list)
        assert "Found" in output

    shell.cleanup()


def test_find_multiple_filters(test_library):
    """Test find with multiple filters."""
    shell = LibraryShell(test_library)

    # Mock console to capture find output
    with patch.object(shell.console, "print") as mock_print:
        # Find books by author and language
        shell.cmd_find(["author:Test", "language:en"])
        # Should have printed results
        assert mock_print.called

    shell.cleanup()


def test_find_no_results(test_library):
    """Test find with no matching books."""
    shell = LibraryShell(test_library)

    # Mock console to capture find output
    with patch.object(shell.console, "print") as mock_print:
        # Find books that don't exist
        shell.cmd_find(["author:NonexistentAuthor"])
        # Should have printed no results message
        assert mock_print.called
        output = str(mock_print.call_args_list)
        assert "No books found" in output

    shell.cleanup()
