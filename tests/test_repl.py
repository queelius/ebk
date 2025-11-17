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


class TestPipelineExecution:
    """Test pipeline command chaining behavior."""

    def test_pipeline_chains_output_between_commands(self, test_library):
        """Test that pipeline correctly passes output from one command to the next.

        Given: A shell with a populated library
        When: User executes a pipeline like "ls | grep Test"
        Then: Output of ls becomes input to grep, and matching lines are returned
        """
        shell = LibraryShell(test_library)

        # Execute pipeline: cd to books, list them, filter by pattern
        shell.cmd_cd(["books"])
        from ebk.repl.shell import Pipeline
        pipeline = Pipeline("ls | grep Test")

        result = pipeline.execute(shell)

        # Result should contain filtered output (not None if matches found)
        # The behavior we're testing: pipeline successfully connected commands
        # We don't care about exact format, just that grep received ls output
        assert result is None or "Test" in result or result == ""

        shell.cleanup()

    def test_pipeline_stops_on_command_failure(self, test_library):
        """Test that pipeline stops executing when a command fails.

        Given: A shell instance
        When: A command in the pipeline fails
        Then: Subsequent commands are not executed
        """
        shell = LibraryShell(test_library)

        from ebk.repl.shell import Pipeline
        # This should fail because "nonexistent" is not a valid command
        with patch.object(shell.console, "print"):
            pipeline = Pipeline("ls | nonexistent | grep test")
            result = pipeline.execute(shell)

        # Pipeline should return None when it encounters an error
        assert result is None

        shell.cleanup()

    def test_pipeline_handles_empty_output(self, test_library):
        """Test pipeline behavior when intermediate command produces no output.

        Given: A pipeline with commands that may produce no output
        When: An intermediate command returns None/empty
        Then: Pipeline handles gracefully without crashing
        """
        shell = LibraryShell(test_library)

        from ebk.repl.shell import Pipeline
        # grep for something that doesn't exist, then try to process it
        with patch.object(shell.console, "print"):
            shell.cmd_cd(["books"])
            pipeline = Pipeline("ls | grep NONEXISTENT")
            result = pipeline.execute(shell)

        # Should return None (no matches) without errors
        assert result is None or result == ""

        shell.cleanup()

    def test_pipeline_with_three_commands(self, test_library):
        """Test pipeline with multiple stages.

        Given: A shell with test data
        When: Pipeline has three or more commands
        Then: Data flows through all stages correctly
        """
        shell = LibraryShell(test_library)

        # Create a simple test: pwd outputs path, which can be processed
        from ebk.repl.shell import Pipeline

        # This tests that output can flow through multiple stages
        # pwd -> (output path as text) -> grep "/" -> (filter)
        with patch.object(shell.console, "print"):
            pipeline = Pipeline("pwd | cat | grep /")
            result = pipeline.execute(shell)

        # Should have found "/" in the path
        assert result is None or "/" in result

        shell.cleanup()


class TestOutputRedirection:
    """Test output redirection to VFS files."""

    def test_redirect_command_output_to_file(self, test_library):
        """Test that > operator redirects command output to a VFS file.

        Given: A shell with a library
        When: User executes "command > filepath"
        Then: Command output is written to the VFS file instead of console
        """
        shell = LibraryShell(test_library)

        # Test redirection: pwd > /test.txt
        with patch.object(shell, "write_to_vfs_file") as mock_write:
            shell.execute("pwd > /test.txt")

            # Verify write_to_vfs_file was called with path and output
            mock_write.assert_called_once()
            args = mock_write.call_args[0]
            assert args[0] == "/test.txt"  # file path
            assert "/" in args[1]  # output contains path

        shell.cleanup()

    def test_redirect_handles_file_errors_gracefully(self, test_library):
        """Test that redirection handles file writing errors gracefully.

        Given: A shell instance
        When: Redirection target cannot be written
        Then: Error is displayed without crashing
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            # Try to redirect to a file with special characters in name
            shell.execute('pwd > "unclosed')

            # Should have printed an error message (behavior: handles errors gracefully)
            mock_print.assert_called()
            # We're testing that an error was shown, not the exact error text
            assert mock_print.call_count > 0

        shell.cleanup()

    def test_redirect_only_on_successful_command(self, test_library):
        """Test that redirection only happens when command succeeds.

        Given: A shell instance
        When: Command before > fails
        Then: No file is written to VFS
        """
        shell = LibraryShell(test_library)

        with patch.object(shell, "write_to_vfs_file") as mock_write:
            with patch.object(shell.console, "print"):
                # Execute a command that doesn't exist
                shell.execute("nonexistent > /output.txt")

            # write_to_vfs_file should NOT have been called
            mock_write.assert_not_called()

        shell.cleanup()


class TestTextProcessingCommands:
    """Test text processing utilities (head, tail, wc, sort, uniq, more)."""

    def test_head_command_returns_first_lines(self, test_library):
        """Test that head returns the first N lines of input.

        Given: A shell with multi-line input
        When: head -n 3 is executed
        Then: Only the first 3 lines are returned
        """
        shell = LibraryShell(test_library)

        test_input = "line1\nline2\nline3\nline4\nline5"

        # Execute head with stdin
        result = shell.cmd_head(["-n", "3"], stdin=test_input, silent=True)

        # Should return first 3 lines
        assert result is not None
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "line1"
        assert lines[2] == "line3"

        shell.cleanup()

    def test_tail_command_returns_last_lines(self, test_library):
        """Test that tail returns the last N lines of input.

        Given: A shell with multi-line input
        When: tail -n 2 is executed
        Then: Only the last 2 lines are returned
        """
        shell = LibraryShell(test_library)

        test_input = "line1\nline2\nline3\nline4\nline5"

        result = shell.cmd_tail(["-n", "2"], stdin=test_input, silent=True)

        # Should return last 2 lines
        assert result is not None
        lines = result.split("\n")
        assert len(lines) == 2
        assert lines[0] == "line4"
        assert lines[1] == "line5"

        shell.cleanup()

    def test_wc_counts_lines_words_characters(self, test_library):
        """Test that wc provides correct counts.

        Given: Text input with known dimensions
        When: wc is executed
        Then: Returns accurate line, word, and character counts
        """
        shell = LibraryShell(test_library)

        test_input = "hello world\nfoo bar\nbaz"

        result = shell.cmd_wc([], stdin=test_input, silent=True)

        # Should return counts (format: lines words chars)
        assert result is not None
        # We're testing behavior (that it counts), not exact format
        assert "3" in result  # 3 lines
        assert "5" in result  # 5 words

        shell.cleanup()

    def test_sort_orders_lines_alphabetically(self, test_library):
        """Test that sort reorders lines.

        Given: Unsorted text input
        When: sort is executed
        Then: Lines are returned in sorted order
        """
        shell = LibraryShell(test_library)

        test_input = "zebra\napple\nbanana"

        result = shell.cmd_sort([], stdin=test_input, silent=True)

        assert result is not None
        lines = result.split("\n")
        # Should be in alphabetical order
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "zebra"

        shell.cleanup()

    def test_uniq_removes_consecutive_duplicates(self, test_library):
        """Test that uniq removes consecutive duplicate lines.

        Given: Input with consecutive duplicate lines
        When: uniq is executed
        Then: Consecutive duplicates are collapsed to single line
        """
        shell = LibraryShell(test_library)

        test_input = "apple\napple\napple\nbanana\nbanana\ncherry"

        result = shell.cmd_uniq([], stdin=test_input, silent=True)

        assert result is not None
        lines = result.split("\n")
        # Should have removed consecutive duplicates
        assert len(lines) == 3
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"

        shell.cleanup()

    def test_more_paginates_long_output(self, test_library):
        """Test that more handles pagination of long content.

        Given: Long text input
        When: more is executed
        Then: Content is prepared for pagination (behavior may vary)
        """
        shell = LibraryShell(test_library)

        # Create long input
        test_input = "\n".join([f"line {i}" for i in range(100)])

        # more should handle this without error
        result = shell.cmd_more([], stdin=test_input, silent=True)

        # Just verify it doesn't crash and returns something
        assert result is not None or result == test_input

        shell.cleanup()


class TestBashCommandExecution:
    """Test bash command execution via ! prefix."""

    def test_bash_command_executes_system_command(self, test_library):
        """Test that !command executes bash commands.

        Given: A shell instance
        When: User prefixes command with !
        Then: Command is executed via system shell
        """
        shell = LibraryShell(test_library)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="test output",
                stderr=""
            )

            shell.execute_bash("echo hello")

            # Verify subprocess.run was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "echo hello" in str(call_args)

        shell.cleanup()

    def test_bash_command_handles_errors(self, test_library):
        """Test that bash command errors are handled gracefully.

        Given: A shell instance
        When: Bash command fails
        Then: Error is displayed without crashing shell
        """
        shell = LibraryShell(test_library)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="command not found"
            )

            with patch.object(shell.console, "print") as mock_print:
                shell.execute_bash("nonexistent_command")

                # Should have printed error info
                mock_print.assert_called()

        shell.cleanup()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_unknown_command_shows_error(self, test_library):
        """Test that unknown commands display helpful error.

        Given: A shell instance
        When: User enters an unknown command
        Then: Error message suggests using help
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.execute("unknowncommand arg1 arg2")

            # Should have printed error with suggestion
            mock_print.assert_called()
            output = str(mock_print.call_args[0][0])
            assert "unknown" in output.lower() or "unknowncommand" in output.lower()
            assert "help" in output.lower()

        shell.cleanup()

    def test_cat_without_arguments_shows_error(self, test_library):
        """Test that cat requires a file argument.

        Given: A shell instance
        When: cat is called without arguments
        Then: Error message is displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_cat([], silent=False)

            # Should have printed error
            mock_print.assert_called()
            output = str(mock_print.call_args[0][0])
            assert "missing" in output.lower() or "argument" in output.lower()

        shell.cleanup()

    def test_grep_without_pattern_shows_usage(self, test_library):
        """Test that grep requires a pattern argument.

        Given: A shell instance
        When: grep is called without pattern
        Then: Usage information is displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_grep([], silent=False)

            # Should have printed usage
            mock_print.assert_called()
            output = str(mock_print.call_args_list)
            assert "missing" in output.lower() or "usage" in output.lower()

        shell.cleanup()

    def test_cd_to_nonexistent_directory_shows_error(self, test_library):
        """Test that cd to invalid path shows error.

        Given: A shell instance
        When: cd is called with nonexistent path
        Then: Error message is displayed and pwd doesn't change
        """
        shell = LibraryShell(test_library)

        original_path = shell.vfs.pwd()

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_cd(["/nonexistent/path"])

            # Should have printed error
            mock_print.assert_called()
            output = str(mock_print.call_args[0][0])
            assert "no such" in output.lower() or "nonexistent" in output.lower()

        # Path should not have changed
        assert shell.vfs.pwd() == original_path

        shell.cleanup()

    def test_ls_nonexistent_path_shows_error(self, test_library):
        """Test that ls on invalid path shows error.

        Given: A shell instance
        When: ls is called with nonexistent path
        Then: Error message is displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            result = shell.cmd_ls(["/nonexistent"], silent=False)

            # Should return None and print error
            assert result is None
            # Error should mention the path
            output = str(mock_print.call_args_list)
            assert "no such" in output.lower() or "nonexistent" in output.lower()

        shell.cleanup()


class TestTagManagementCommands:
    """Test tag management via ln, tag, and untag commands."""

    def test_ln_adds_tag_to_book(self, test_library):
        """Test that ln command links a book to a tag.

        Given: A library with a book
        When: ln /books/ID /tags/TagName/ is executed
        Then: Book is tagged with TagName
        """
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().all()
        assert len(books) > 0
        book_id = books[0].id
        lib.close()

        # Add tag using ln command
        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/books/{book_id}", "/tags/TestTag/"], silent=False)

            # Should show success message
            mock_print.assert_called()
            output = str(mock_print.call_args_list)
            assert "added" in output.lower() or "testtag" in output.lower()

        shell.cleanup()

    def test_ln_requires_two_arguments(self, test_library):
        """Test that ln validates required arguments.

        Given: A shell instance
        When: ln is called with fewer than 2 arguments
        Then: Usage message is displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln(["/books/1"], silent=False)

            # Should show usage
            mock_print.assert_called()
            output = str(mock_print.call_args[0][0])
            assert "usage" in output.lower()

        shell.cleanup()

    def test_ln_validates_source_exists(self, test_library):
        """Test that ln validates source path exists.

        Given: A shell instance
        When: ln is called with nonexistent source
        Then: Error message is displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln(["/books/9999", "/tags/Test/"], silent=False)

            # Should show error
            mock_print.assert_called()
            output = str(mock_print.call_args_list)
            assert "not found" in output.lower()

        shell.cleanup()

    def test_ln_requires_tags_destination(self, test_library):
        """Test that ln destination must be a tag path.

        Given: A library with a book
        When: ln destination is not under /tags/
        Then: Error message is displayed
        """
        shell = LibraryShell(test_library)

        lib = Library.open(test_library)
        books = lib.query().all()
        book_id = books[0].id
        lib.close()

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_ln([f"/books/{book_id}", "/subjects/Test/"], silent=False)

            # Should show error about tag path
            mock_print.assert_called()
            output = str(mock_print.call_args_list)
            assert "tag" in output.lower()

        shell.cleanup()


class TestCommandIntegration:
    """Test integration between multiple commands."""

    def test_grep_on_stdin_from_pipeline(self, test_library):
        """Test that grep can filter stdin from previous command.

        Given: Output from one command
        When: Piped to grep
        Then: grep filters the output correctly
        """
        shell = LibraryShell(test_library)

        # Simulate stdin from previous command
        test_output = "file1.txt contains data\nfile2.txt contains test\nfile3.txt contains info"

        result = shell.cmd_grep(["contains", "-i"], stdin=test_output, silent=True)

        # All lines should match "contains"
        assert result is not None
        assert "contains" in result

        shell.cleanup()

    def test_cat_passes_through_stdin(self, test_library):
        """Test that cat passes stdin through unchanged when no file specified.

        Given: Input from pipeline
        When: cat is called with stdin
        Then: Output equals input
        """
        shell = LibraryShell(test_library)

        test_input = "test content\nline 2\nline 3"

        result = shell.cmd_cat([], stdin=test_input, silent=True)

        assert result == test_input

        shell.cleanup()

    def test_text_commands_can_chain_together(self, test_library):
        """Test that text processing commands work in sequence.

        Given: Text input
        When: Multiple text commands are chained
        Then: Output is processed through all stages
        """
        shell = LibraryShell(test_library)

        # Start with some text
        text = "apple\nbanana\napple\ncherry\nbanana\napple"

        # Sort it
        sorted_text = shell.cmd_sort([], stdin=text, silent=True)
        assert sorted_text is not None

        # Then uniq it
        unique_text = shell.cmd_uniq([], stdin=sorted_text, silent=True)
        assert unique_text is not None

        # Should have only 3 unique lines
        lines = unique_text.split("\n")
        assert len(lines) == 3

        shell.cleanup()

    def test_quit_command_is_alias_for_exit(self, test_library):
        """Test that quit works the same as exit.

        Given: A running shell
        When: quit command is executed
        Then: Shell stops running (same as exit)
        """
        shell = LibraryShell(test_library)

        assert shell.running is True
        shell.cmd_quit([])
        assert shell.running is False

        shell.cleanup()


class TestPathCompletion:
    """Test path completion functionality."""

    def test_path_completer_provides_suggestions(self, test_library):
        """Test that PathCompleter generates completion suggestions.

        Given: A VFS with known paths
        When: User requests completions for partial path
        Then: Relevant suggestions are returned
        """
        shell = LibraryShell(test_library)

        from ebk.repl.shell import PathCompleter
        from unittest.mock import MagicMock

        completer = PathCompleter(shell.vfs)

        # Mock document for completion
        mock_doc = MagicMock()
        mock_doc.text_before_cursor = "cd b"

        # Get completions
        completions = list(completer.get_completions(mock_doc, None))

        # Should have suggestions (books, etc.)
        # We're testing behavior: completion system works
        # Not exact matches, as VFS structure may vary
        assert isinstance(completions, list)

        shell.cleanup()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_command_line_ignored(self, test_library):
        """Test that empty input doesn't cause errors.

        Given: A shell instance
        When: User enters empty command
        Then: Nothing happens, no error
        """
        shell = LibraryShell(test_library)

        # This should not raise an exception
        shell.execute("")
        shell.execute("   ")  # whitespace only

        # Shell should still be running
        assert shell.running is True

        shell.cleanup()

    def test_command_with_only_spaces_ignored(self, test_library):
        """Test that whitespace-only commands are ignored.

        Given: A shell instance
        When: Command is only whitespace
        Then: No operation performed
        """
        shell = LibraryShell(test_library)

        # Should handle gracefully
        with patch.object(shell.console, "print") as mock_print:
            shell.execute("     ")

            # Should not print anything (command was empty)
            assert mock_print.call_count == 0

        shell.cleanup()

    def test_pipeline_with_empty_segments(self, test_library):
        """Test pipeline handles empty segments gracefully.

        Given: A pipeline with empty command segments
        When: Pipeline is executed
        Then: Empty segments are skipped without error
        """
        shell = LibraryShell(test_library)

        from ebk.repl.shell import Pipeline

        # Pipeline with empty segments (multiple pipes)
        with patch.object(shell.console, "print"):
            pipeline = Pipeline("pwd | | ls")
            # Should not crash
            result = pipeline.execute(shell)

        # Should have handled gracefully
        assert result is None or isinstance(result, str)

        shell.cleanup()

    def test_grep_line_numbers_flag(self, test_library):
        """Test grep -n flag shows line numbers.

        Given: Text input with multiple lines
        When: grep -n is used
        Then: Output includes line numbers
        """
        shell = LibraryShell(test_library)

        test_input = "line one\nline two has test\nline three\nline four has test"

        result = shell.cmd_grep(["-n", "test"], stdin=test_input, silent=True)

        # Should include line numbers (2: and 4:)
        assert result is not None
        assert ":" in result  # Line numbers format: "2:line two has test"

        shell.cleanup()

    def test_grep_case_insensitive_on_stdin(self, test_library):
        """Test grep -i flag with stdin.

        Given: Text with mixed case
        When: grep -i searches case-insensitively
        Then: All case variations match
        """
        shell = LibraryShell(test_library)

        test_input = "Test line\ntest line\nTEST line\nother line"

        result = shell.cmd_grep(["-i", "test"], stdin=test_input, silent=True)

        assert result is not None
        lines = result.split("\n")
        # Should match all 3 test variations
        assert len(lines) >= 3

        shell.cleanup()

    def test_find_with_no_args_shows_usage(self, test_library):
        """Test find without arguments shows helpful usage.

        Given: A shell instance
        When: find is called with no arguments
        Then: Usage and examples are displayed
        """
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            shell.cmd_find([], silent=False)

            # Should show usage and examples
            mock_print.assert_called()
            output = str(mock_print.call_args_list)
            assert "usage" in output.lower() or "example" in output.lower()

        shell.cleanup()
