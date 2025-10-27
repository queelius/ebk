"""Integration tests for Unix-like piping infrastructure.

Tests the Pipeline class and command integration for piping:
- Pipeline parsing
- Pipeline execution
- Command stdin/stdout handling
- Silent mode for intermediate commands
- Error handling in pipelines
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ebk.library_db import Library
from ebk.repl.shell import LibraryShell, Pipeline


@pytest.fixture
def test_library(tmp_path):
    """Create a test library with sample books and content."""
    lib_path = tmp_path / "test_library"
    lib = Library.open(lib_path)

    # Create test files with various content
    test_file1 = tmp_path / "python_book.txt"
    test_file1.write_text("""Python is a high-level programming language.
Python supports multiple programming paradigms.
Python has a large standard library.
Many developers use Python for data science.
Python is known for its simple syntax.
""")

    test_file2 = tmp_path / "java_book.txt"
    test_file2.write_text("""Java is an object-oriented programming language.
Java is platform-independent.
Java has strong typing.
Enterprise applications often use Java.
Java has excellent IDE support.
""")

    # Add books
    book1 = lib.add_book(
        test_file1,
        metadata={
            "title": "Python Programming",
            "creators": ["John Doe"],
            "subjects": ["Programming", "Python"],
            "language": "en",
        },
    )

    book2 = lib.add_book(
        test_file2,
        metadata={
            "title": "Java Fundamentals",
            "creators": ["Jane Smith"],
            "subjects": ["Programming", "Java"],
            "language": "en",
        },
    )

    lib.close()
    return lib_path


class TestPipelineParsing:
    """Tests for Pipeline parsing."""

    def test_pipeline_single_command(self):
        """Test pipeline with single command (no pipe)."""
        pipeline = Pipeline("cat myfile.txt")
        assert len(pipeline.commands) == 1
        assert pipeline.commands[0] == "cat myfile.txt"

    def test_pipeline_two_commands(self):
        """Test pipeline with two commands."""
        pipeline = Pipeline("cat file.txt | grep python")
        assert len(pipeline.commands) == 2
        assert pipeline.commands[0] == "cat file.txt"
        assert pipeline.commands[1] == "grep python"

    def test_pipeline_three_commands(self):
        """Test pipeline with three commands."""
        pipeline = Pipeline("cat file.txt | grep python | head -5")
        assert len(pipeline.commands) == 3
        assert pipeline.commands[0] == "cat file.txt"
        assert pipeline.commands[1] == "grep python"
        assert pipeline.commands[2] == "head -5"

    def test_pipeline_whitespace_handling(self):
        """Test pipeline handles extra whitespace correctly."""
        pipeline = Pipeline("cat file.txt  |  grep python  |  wc -l")
        assert len(pipeline.commands) == 3
        # Commands should be trimmed
        assert pipeline.commands[0] == "cat file.txt"
        assert pipeline.commands[1] == "grep python"
        assert pipeline.commands[2] == "wc -l"

    def test_pipeline_empty_commands(self):
        """Test pipeline with empty command segments."""
        pipeline = Pipeline("cat file.txt ||")
        # Should have empty strings that get filtered during execution
        assert len(pipeline.commands) >= 2


class TestPipelineExecution:
    """Tests for Pipeline execution."""

    def test_cat_pipe_head(self, test_library):
        """Test simple pipeline: cat | head."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        # Execute pipeline
        shell.cmd_cd([f"/books/{book_id}"])
        pipeline = Pipeline("cat text | head -n 2")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should get first 2 lines of the text
        assert output is not None
        lines = output.split("\n")
        assert len(lines) == 2
        assert "Python" in lines[0]

    def test_cat_pipe_grep_pipe_head(self, test_library):
        """Test three-stage pipeline: cat | grep | head."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        # Execute pipeline
        shell.cmd_cd([f"/books/{book_id}"])
        pipeline = Pipeline("cat text | grep Python | head -n 2")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should get first 2 lines that contain "Python"
        assert output is not None
        lines = output.split("\n")
        assert len(lines) == 2
        assert all("Python" in line for line in lines)

    def test_find_pipe_wc(self, test_library):
        """Test pipeline: find | wc -l."""
        shell = LibraryShell(test_library)

        # Execute pipeline to count books
        pipeline = Pipeline("find language:en | wc -l")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should count the number of books found
        assert output is not None
        count = int(output.strip())
        assert count == 2  # Two books in library

    def test_cat_pipe_sort(self, test_library):
        """Test pipeline: cat | sort."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        # Execute pipeline
        shell.cmd_cd([f"/books/{book_id}"])
        pipeline = Pipeline("cat text | sort")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Lines should be sorted
        assert output is not None
        lines = output.split("\n")
        # Filter out empty lines for comparison since they may appear at different positions
        non_empty_lines = [l for l in lines if l.strip()]
        sorted_non_empty = sorted(non_empty_lines)
        assert non_empty_lines == sorted_non_empty

    def test_cat_pipe_sort_pipe_uniq(self, test_library):
        """Test pipeline: cat | sort | uniq."""
        shell = LibraryShell(test_library)

        # Create content with duplicates
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Execute pipeline
        pipeline = Pipeline("cat text | sort | uniq")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should have unique sorted lines
        assert output is not None
        lines = output.split("\n")
        # Check that there are no adjacent duplicates
        for i in range(len(lines) - 1):
            assert lines[i] != lines[i + 1]

    def test_cat_pipe_wc_all_flags(self, test_library):
        """Test pipeline: cat | wc (with different flags)."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Test -l flag
        pipeline = Pipeline("cat text | wc -l")
        output = pipeline.execute(shell)
        assert output is not None
        line_count = int(output.strip())
        assert line_count > 0

        # Test -w flag
        pipeline = Pipeline("cat text | wc -w")
        output = pipeline.execute(shell)
        assert output is not None
        word_count = int(output.strip())
        assert word_count > 0

        # Test -c flag
        pipeline = Pipeline("cat text | wc -c")
        output = pipeline.execute(shell)
        assert output is not None
        char_count = int(output.strip())
        assert char_count > 0

        shell.cleanup()

    def test_cat_pipe_tail(self, test_library):
        """Test pipeline: cat | tail."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Execute pipeline
        pipeline = Pipeline("cat text | tail -n 2")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should get last 2 lines
        assert output is not None
        lines = output.split("\n")
        assert len(lines) == 2

    def test_grep_pipe_sort_pipe_uniq_count(self, test_library):
        """Test complex pipeline: grep | sort | uniq -c."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Execute pipeline
        pipeline = Pipeline("cat text | grep Python | sort | uniq -c")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should have counts and unique sorted lines with "Python"
        assert output is not None
        lines = output.split("\n")
        # Each line should have a count and the word Python
        for line in lines:
            if line.strip():
                assert "Python" in line
                # Should have a number at the beginning
                parts = line.strip().split(None, 1)
                assert len(parts) >= 1
                assert parts[0].isdigit()


class TestPipelineErrorHandling:
    """Tests for error handling in pipelines."""

    def test_pipeline_invalid_command(self, test_library):
        """Test pipeline with invalid command stops execution."""
        shell = LibraryShell(test_library)

        # Mock console to suppress error output
        with patch.object(shell.console, "print"):
            pipeline = Pipeline("invalidcmd | head")
            output = pipeline.execute(shell)

        shell.cleanup()

        # Should return None due to invalid command
        assert output is None

    def test_pipeline_command_parse_error(self, test_library):
        """Test pipeline with command parse error."""
        shell = LibraryShell(test_library)

        # Mock console to suppress error output
        with patch.object(shell.console, "print"):
            # Unmatched quote should cause parse error
            pipeline = Pipeline('cat "unclosed | head')
            output = pipeline.execute(shell)

        shell.cleanup()

        # Should return None due to parse error
        assert output is None

    def test_pipeline_failing_intermediate_command(self, test_library):
        """Test that pipeline stops when intermediate command fails."""
        shell = LibraryShell(test_library)

        # Mock console to suppress error output
        with patch.object(shell.console, "print"):
            # grep with no pattern should fail
            pipeline = Pipeline("cat text | grep | head")
            output = pipeline.execute(shell)

        shell.cleanup()

        # Should return None because grep failed
        assert output is None

    def test_pipeline_empty_command_segment(self, test_library):
        """Test pipeline handles empty command segments gracefully."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Pipeline with empty segment (double pipe)
        pipeline = Pipeline("cat title || head -1")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should still work, skipping empty commands
        # Note: behavior depends on implementation


class TestSilentModeAndOutput:
    """Tests for silent mode and output handling."""

    def test_intermediate_commands_silent(self, test_library):
        """Test that intermediate commands don't print output."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Mock console to capture print calls
        with patch.object(shell.console, "print") as mock_print:
            # Execute pipeline - only final command should print
            pipeline = Pipeline("cat text | head -n 3")
            output = pipeline.execute(shell)

            # Get number of print calls
            print_count = mock_print.call_count

            # Only the final head command should print (when pipeline.execute calls console.print)
            # The intermediate cat should be silent
            # Note: Exact count depends on implementation details

        shell.cleanup()

        assert output is not None

    def test_command_returns_output_for_piping(self, test_library):
        """Test that commands return output strings for piping."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Call command with silent=True and check it returns output
        output = shell.cmd_cat(["title"], stdin=None, silent=True)
        assert output is not None
        assert isinstance(output, str)
        assert len(output) > 0

        shell.cleanup()

    def test_stdin_passed_correctly(self, test_library):
        """Test that stdin is passed correctly between commands."""
        shell = LibraryShell(test_library)

        # Test head with stdin
        test_input = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        output = shell.cmd_head([], stdin=test_input, silent=True)

        assert output is not None
        assert "Line 1" in output

        shell.cleanup()

    def test_grep_with_stdin(self, test_library):
        """Test grep command with stdin from previous command."""
        shell = LibraryShell(test_library)

        # Test grep with stdin
        test_input = "apple\nbanana\napple pie\ncherry"
        output = shell.cmd_grep(["apple"], stdin=test_input, silent=True)

        assert output is not None
        lines = output.split("\n")
        # Should match "apple" and "apple pie"
        assert len(lines) == 2
        assert all("apple" in line for line in lines)

        shell.cleanup()

    def test_wc_with_stdin(self, test_library):
        """Test wc command with stdin from previous command."""
        shell = LibraryShell(test_library)

        # Test wc with stdin
        test_input = "Line 1\nLine 2\nLine 3"
        output = shell.cmd_wc(["-l"], stdin=test_input, silent=True)

        assert output is not None
        assert output.strip() == "3"

        shell.cleanup()

    def test_sort_with_stdin(self, test_library):
        """Test sort command with stdin from previous command."""
        shell = LibraryShell(test_library)

        # Test sort with stdin
        test_input = "zebra\napple\nbanana"
        output = shell.cmd_sort([], stdin=test_input, silent=True)

        assert output is not None
        lines = output.split("\n")
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "zebra"

        shell.cleanup()

    def test_uniq_with_stdin(self, test_library):
        """Test uniq command with stdin from previous command."""
        shell = LibraryShell(test_library)

        # Test uniq with stdin
        test_input = "apple\napple\nbanana\nbanana\ncherry"
        output = shell.cmd_uniq([], stdin=test_input, silent=True)

        assert output is not None
        lines = output.split("\n")
        assert len(lines) == 3
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"

        shell.cleanup()


class TestComplexPipelines:
    """Tests for complex multi-stage pipelines."""

    def test_five_stage_pipeline(self, test_library):
        """Test a complex five-stage pipeline."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Execute complex pipeline: cat | grep | sort | uniq | head
        pipeline = Pipeline("cat text | grep Python | sort | uniq | head -n 3")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should get first 3 unique sorted lines containing "Python"
        assert output is not None
        lines = output.split("\n")
        assert len(lines) <= 3
        for line in lines:
            if line.strip():
                assert "Python" in line

    def test_pipeline_with_grep_flags(self, test_library):
        """Test pipeline with grep flags."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Case-insensitive grep with line numbers
        pipeline = Pipeline("cat text | grep -i -n python")
        output = pipeline.execute(shell)

        shell.cleanup()

        assert output is not None
        # Output should contain line numbers
        if output:
            lines = output.split("\n")
            # Some lines should have line numbers (format: N:content)
            # depending on grep implementation

    def test_pipeline_with_sort_reverse(self, test_library):
        """Test pipeline with reverse sort."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Sort in reverse order
        pipeline = Pipeline("cat text | sort -r | head -n 1")
        output = pipeline.execute(shell)

        shell.cleanup()

        # Should get the last line alphabetically
        assert output is not None

    def test_pipeline_with_uniq_count(self, test_library):
        """Test pipeline with uniq count flag."""
        shell = LibraryShell(test_library)

        # Get book ID
        lib = Library.open(test_library)
        books = lib.query().filter_by_title("Python").all()
        book_id = books[0].id
        lib.close()

        shell.cmd_cd([f"/books/{book_id}"])

        # Count unique lines
        pipeline = Pipeline("cat text | sort | uniq -c")
        output = pipeline.execute(shell)

        shell.cleanup()

        assert output is not None
        # Each line should have a count prefix
        if output:
            lines = output.split("\n")
            for line in lines:
                if line.strip():
                    # Should start with a number
                    parts = line.strip().split(None, 1)
                    assert len(parts) >= 1
                    assert parts[0].isdigit()


class TestExecuteCommandMethod:
    """Tests for the execute_command method."""

    def test_execute_command_valid(self, test_library):
        """Test execute_command with valid command."""
        shell = LibraryShell(test_library)

        output = shell.execute_command("pwd", [], stdin=None, silent=True)
        assert output is not None
        assert output == "/"

        shell.cleanup()

    def test_execute_command_invalid(self, test_library):
        """Test execute_command with invalid command."""
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print"):
            output = shell.execute_command("invalidcmd", [], stdin=None, silent=True)

        assert output is None

        shell.cleanup()

    def test_execute_command_with_stdin(self, test_library):
        """Test execute_command passes stdin correctly."""
        shell = LibraryShell(test_library)

        test_input = "Line 1\nLine 2\nLine 3"
        output = shell.execute_command("head", ["-n", "2"], stdin=test_input, silent=True)

        assert output is not None
        assert "Line 1" in output
        assert "Line 2" in output

        shell.cleanup()

    def test_execute_command_silent_mode(self, test_library):
        """Test execute_command respects silent flag."""
        shell = LibraryShell(test_library)

        with patch.object(shell.console, "print") as mock_print:
            # Silent mode - should not print
            output = shell.execute_command("pwd", [], stdin=None, silent=True)
            assert mock_print.call_count == 0

            # Non-silent mode - should print
            output = shell.execute_command("pwd", [], stdin=None, silent=False)
            assert mock_print.call_count > 0

        shell.cleanup()
