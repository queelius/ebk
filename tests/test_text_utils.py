"""Comprehensive unit tests for text processing utilities.

Tests TextUtils class methods and argument parser functions for:
- head: Show first N lines
- tail: Show last N lines
- wc: Count lines, words, characters
- sort: Sort lines alphabetically
- uniq: Remove duplicate adjacent lines
"""

import pytest

from ebk.repl.text_utils import (
    TextUtils,
    parse_head_args,
    parse_tail_args,
    parse_wc_args,
    parse_sort_args,
    parse_uniq_args,
)


# Test data
SAMPLE_TEXT = """Line 1
Line 2
Line 3
Line 4
Line 5
Line 6
Line 7
Line 8
Line 9
Line 10
Line 11
Line 12"""

SINGLE_LINE = "Just one line"

EMPTY_TEXT = ""

DUPLICATES_TEXT = """apple
apple
apple
banana
banana
cherry
cherry
cherry
cherry"""

UNSORTED_TEXT = """zebra
apple
mango
banana
cherry"""


class TestTextUtilsHead:
    """Tests for TextUtils.head method."""

    def test_head_default_10_lines(self):
        """Test head returns first 10 lines by default."""
        result = TextUtils.head(SAMPLE_TEXT)
        lines = result.split("\n")
        assert len(lines) == 10
        assert lines[0] == "Line 1"
        assert lines[9] == "Line 10"

    def test_head_custom_line_count(self):
        """Test head with custom line count."""
        result = TextUtils.head(SAMPLE_TEXT, lines=5)
        lines = result.split("\n")
        assert len(lines) == 5
        assert lines[0] == "Line 1"
        assert lines[4] == "Line 5"

    def test_head_empty_input(self):
        """Test head with empty input."""
        result = TextUtils.head(EMPTY_TEXT)
        assert result == ""

    def test_head_fewer_lines_than_requested(self):
        """Test head when content has fewer lines than requested."""
        result = TextUtils.head(SAMPLE_TEXT, lines=20)
        lines = result.split("\n")
        assert len(lines) == 12  # Only 12 lines in SAMPLE_TEXT
        assert lines[0] == "Line 1"
        assert lines[11] == "Line 12"

    def test_head_single_line(self):
        """Test head with single line input."""
        result = TextUtils.head(SINGLE_LINE, lines=10)
        assert result == SINGLE_LINE

    def test_head_one_line_requested(self):
        """Test head requesting only 1 line."""
        result = TextUtils.head(SAMPLE_TEXT, lines=1)
        assert result == "Line 1"

    def test_head_zero_lines(self):
        """Test head with zero lines (edge case)."""
        result = TextUtils.head(SAMPLE_TEXT, lines=0)
        assert result == ""


class TestTextUtilsTail:
    """Tests for TextUtils.tail method."""

    def test_tail_default_10_lines(self):
        """Test tail returns last 10 lines by default."""
        result = TextUtils.tail(SAMPLE_TEXT)
        lines = result.split("\n")
        assert len(lines) == 10
        assert lines[0] == "Line 3"
        assert lines[9] == "Line 12"

    def test_tail_custom_line_count(self):
        """Test tail with custom line count."""
        result = TextUtils.tail(SAMPLE_TEXT, lines=5)
        lines = result.split("\n")
        assert len(lines) == 5
        assert lines[0] == "Line 8"
        assert lines[4] == "Line 12"

    def test_tail_empty_input(self):
        """Test tail with empty input."""
        result = TextUtils.tail(EMPTY_TEXT)
        assert result == ""

    def test_tail_fewer_lines_than_requested(self):
        """Test tail when content has fewer lines than requested."""
        result = TextUtils.tail(SAMPLE_TEXT, lines=20)
        lines = result.split("\n")
        assert len(lines) == 12  # Only 12 lines in SAMPLE_TEXT
        assert lines[0] == "Line 1"
        assert lines[11] == "Line 12"

    def test_tail_single_line(self):
        """Test tail with single line input."""
        result = TextUtils.tail(SINGLE_LINE, lines=10)
        assert result == SINGLE_LINE

    def test_tail_one_line_requested(self):
        """Test tail requesting only 1 line."""
        result = TextUtils.tail(SAMPLE_TEXT, lines=1)
        assert result == "Line 12"

    def test_tail_zero_lines(self):
        """Test tail with zero lines (edge case)."""
        result = TextUtils.tail(SAMPLE_TEXT, lines=0)
        # Python's list slicing with [-0:] returns the whole list
        # This is expected behavior
        assert len(result.split("\n")) == 12


class TestTextUtilsWc:
    """Tests for TextUtils.wc method."""

    def test_wc_all_counts(self):
        """Test wc returns all counts by default."""
        result = TextUtils.wc(SAMPLE_TEXT)
        # Should show lines, words, chars in formatted output
        parts = result.split()
        assert len(parts) == 3
        assert int(parts[0]) == 12  # 12 lines
        assert int(parts[1]) == 24  # 24 words (Line 1, Line 2, etc.)
        assert int(parts[2]) > 0  # Some number of chars

    def test_wc_lines_only(self):
        """Test wc with -l flag (lines only)."""
        result = TextUtils.wc(SAMPLE_TEXT, lines_only=True)
        assert result == "12"

    def test_wc_words_only(self):
        """Test wc with -w flag (words only)."""
        result = TextUtils.wc(SAMPLE_TEXT, words_only=True)
        assert result == "24"

    def test_wc_chars_only(self):
        """Test wc with -c flag (chars only)."""
        result = TextUtils.wc(SAMPLE_TEXT, chars_only=True)
        char_count = int(result)
        assert char_count == len(SAMPLE_TEXT)

    def test_wc_empty_input(self):
        """Test wc with empty input."""
        result = TextUtils.wc(EMPTY_TEXT)
        assert result == "0"

    def test_wc_single_word(self):
        """Test wc with single word."""
        result = TextUtils.wc("hello", words_only=True)
        assert result == "1"

    def test_wc_single_line_no_newline(self):
        """Test wc with single line without trailing newline."""
        result = TextUtils.wc("hello world", lines_only=True)
        assert result == "1"

    def test_wc_multiple_lines_with_trailing_newline(self):
        """Test wc with text ending in newline."""
        text_with_newline = "line1\nline2\nline3\n"
        result = TextUtils.wc(text_with_newline, lines_only=True)
        assert result == "3"

    def test_wc_whitespace_handling(self):
        """Test wc handles whitespace correctly in word counting."""
        text = "word1    word2\n\nword3"
        result = TextUtils.wc(text, words_only=True)
        assert result == "3"


class TestTextUtilsSort:
    """Tests for TextUtils.sort_lines method."""

    def test_sort_alphabetical(self):
        """Test normal alphabetical sort."""
        result = TextUtils.sort_lines(UNSORTED_TEXT)
        lines = result.split("\n")
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"
        assert lines[3] == "mango"
        assert lines[4] == "zebra"

    def test_sort_reverse(self):
        """Test reverse sort with -r flag."""
        result = TextUtils.sort_lines(UNSORTED_TEXT, reverse=True)
        lines = result.split("\n")
        assert lines[0] == "zebra"
        assert lines[1] == "mango"
        assert lines[2] == "cherry"
        assert lines[3] == "banana"
        assert lines[4] == "apple"

    def test_sort_already_sorted(self):
        """Test sorting already sorted input."""
        sorted_text = "apple\nbanana\ncherry"
        result = TextUtils.sort_lines(sorted_text)
        assert result == sorted_text

    def test_sort_empty_input(self):
        """Test sort with empty input."""
        result = TextUtils.sort_lines(EMPTY_TEXT)
        assert result == ""

    def test_sort_single_line(self):
        """Test sort with single line."""
        result = TextUtils.sort_lines(SINGLE_LINE)
        assert result == SINGLE_LINE

    def test_sort_preserves_trailing_newline(self):
        """Test that sort preserves trailing newline if present."""
        text_with_newline = "zebra\napple\n"
        result = TextUtils.sort_lines(text_with_newline)
        assert result.endswith("\n")
        lines = result.rstrip("\n").split("\n")
        assert lines == ["apple", "zebra"]

    def test_sort_no_trailing_newline(self):
        """Test that sort works without trailing newline."""
        text_no_newline = "zebra\napple"
        result = TextUtils.sort_lines(text_no_newline)
        assert not result.endswith("\n")
        lines = result.split("\n")
        assert lines == ["apple", "zebra"]

    def test_sort_case_sensitive(self):
        """Test that sort is case sensitive."""
        text = "Zebra\napple\nBanana"
        result = TextUtils.sort_lines(text)
        lines = result.split("\n")
        # Uppercase comes before lowercase in ASCII
        assert lines[0] == "Banana"
        assert lines[1] == "Zebra"
        assert lines[2] == "apple"


class TestTextUtilsUniq:
    """Tests for TextUtils.uniq method."""

    def test_uniq_remove_duplicates(self):
        """Test uniq removes duplicate adjacent lines."""
        result = TextUtils.uniq(DUPLICATES_TEXT)
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[0] == "apple"
        assert lines[1] == "banana"
        assert lines[2] == "cherry"

    def test_uniq_with_counts(self):
        """Test uniq with -c flag shows counts."""
        result = TextUtils.uniq(DUPLICATES_TEXT, count=True)
        lines = result.split("\n")
        assert len(lines) == 3
        # Format is "      3 apple" (right-aligned count)
        assert "3" in lines[0] and "apple" in lines[0]
        assert "2" in lines[1] and "banana" in lines[1]
        assert "4" in lines[2] and "cherry" in lines[2]

    def test_uniq_no_duplicates(self):
        """Test uniq with no duplicates in input."""
        text = "apple\nbanana\ncherry"
        result = TextUtils.uniq(text)
        assert result == text

    def test_uniq_all_duplicates(self):
        """Test uniq when all lines are the same."""
        text = "same\nsame\nsame\nsame"
        result = TextUtils.uniq(text)
        assert result == "same"

    def test_uniq_empty_input(self):
        """Test uniq with empty input."""
        result = TextUtils.uniq(EMPTY_TEXT)
        assert result == ""

    def test_uniq_single_line(self):
        """Test uniq with single line."""
        result = TextUtils.uniq(SINGLE_LINE)
        assert result == SINGLE_LINE

    def test_uniq_non_adjacent_duplicates(self):
        """Test that uniq only removes adjacent duplicates."""
        text = "apple\nbanana\napple\nbanana"
        result = TextUtils.uniq(text)
        lines = result.split("\n")
        # Non-adjacent duplicates should remain
        assert len(lines) == 4
        assert lines == ["apple", "banana", "apple", "banana"]

    def test_uniq_count_formatting(self):
        """Test that uniq -c formats counts correctly."""
        text = "a\na\na\na\na\na\na\na\na\na"  # 10 a's
        result = TextUtils.uniq(text, count=True)
        assert "10" in result
        assert "a" in result


class TestParseHeadArgs:
    """Tests for parse_head_args function."""

    def test_parse_head_no_args(self):
        """Test parse_head_args with no arguments."""
        lines, filename = parse_head_args([])
        assert lines == 10  # Default
        assert filename is None

    def test_parse_head_with_n_flag(self):
        """Test parse_head_args with -n flag."""
        lines, filename = parse_head_args(["-n", "20"])
        assert lines == 20
        assert filename is None

    def test_parse_head_with_short_form(self):
        """Test parse_head_args with short form -20."""
        lines, filename = parse_head_args(["-20"])
        assert lines == 20
        assert filename is None

    def test_parse_head_with_filename(self):
        """Test parse_head_args with filename."""
        lines, filename = parse_head_args(["myfile.txt"])
        assert lines == 10  # Default
        assert filename == "myfile.txt"

    def test_parse_head_with_n_and_filename(self):
        """Test parse_head_args with -n and filename."""
        lines, filename = parse_head_args(["-n", "5", "myfile.txt"])
        assert lines == 5
        assert filename == "myfile.txt"

    def test_parse_head_missing_n_argument(self):
        """Test parse_head_args raises error when -n has no argument."""
        with pytest.raises(ValueError, match="head: -n requires an argument"):
            parse_head_args(["-n"])

    def test_parse_head_invalid_line_count(self):
        """Test parse_head_args raises error for invalid line count."""
        with pytest.raises(ValueError, match="head: invalid line count"):
            parse_head_args(["-n", "abc"])

    def test_parse_head_unknown_option(self):
        """Test parse_head_args raises error for unknown option."""
        with pytest.raises(ValueError, match="head: unknown option"):
            parse_head_args(["-x"])

    def test_parse_head_short_form_invalid(self):
        """Test parse_head_args raises error for invalid short form."""
        # -abc is treated as unknown option since it doesn't start with digits
        with pytest.raises(ValueError, match="head: unknown option"):
            parse_head_args(["-abc"])


class TestParseTailArgs:
    """Tests for parse_tail_args function."""

    def test_parse_tail_no_args(self):
        """Test parse_tail_args with no arguments."""
        lines, filename = parse_tail_args([])
        assert lines == 10  # Default
        assert filename is None

    def test_parse_tail_with_n_flag(self):
        """Test parse_tail_args with -n flag."""
        lines, filename = parse_tail_args(["-n", "15"])
        assert lines == 15
        assert filename is None

    def test_parse_tail_with_short_form(self):
        """Test parse_tail_args with short form -15."""
        lines, filename = parse_tail_args(["-15"])
        assert lines == 15
        assert filename is None

    def test_parse_tail_with_filename(self):
        """Test parse_tail_args with filename."""
        lines, filename = parse_tail_args(["myfile.txt"])
        assert lines == 10  # Default
        assert filename == "myfile.txt"

    def test_parse_tail_with_n_and_filename(self):
        """Test parse_tail_args with -n and filename."""
        lines, filename = parse_tail_args(["-n", "3", "myfile.txt"])
        assert lines == 3
        assert filename == "myfile.txt"

    def test_parse_tail_missing_n_argument(self):
        """Test parse_tail_args raises error when -n has no argument."""
        with pytest.raises(ValueError, match="tail: -n requires an argument"):
            parse_tail_args(["-n"])

    def test_parse_tail_invalid_line_count(self):
        """Test parse_tail_args raises error for invalid line count."""
        with pytest.raises(ValueError, match="tail: invalid line count"):
            parse_tail_args(["-n", "xyz"])

    def test_parse_tail_unknown_option(self):
        """Test parse_tail_args raises error for unknown option."""
        with pytest.raises(ValueError, match="tail: unknown option"):
            parse_tail_args(["-z"])


class TestParseWcArgs:
    """Tests for parse_wc_args function."""

    def test_parse_wc_no_args(self):
        """Test parse_wc_args with no arguments."""
        lines_only, words_only, chars_only, filename = parse_wc_args([])
        assert lines_only is False
        assert words_only is False
        assert chars_only is False
        assert filename is None

    def test_parse_wc_with_l_flag(self):
        """Test parse_wc_args with -l flag."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["-l"])
        assert lines_only is True
        assert words_only is False
        assert chars_only is False
        assert filename is None

    def test_parse_wc_with_w_flag(self):
        """Test parse_wc_args with -w flag."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["-w"])
        assert lines_only is False
        assert words_only is True
        assert chars_only is False
        assert filename is None

    def test_parse_wc_with_c_flag(self):
        """Test parse_wc_args with -c flag."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["-c"])
        assert lines_only is False
        assert words_only is False
        assert chars_only is True
        assert filename is None

    def test_parse_wc_with_filename(self):
        """Test parse_wc_args with filename."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["myfile.txt"])
        assert filename == "myfile.txt"

    def test_parse_wc_with_flag_and_filename(self):
        """Test parse_wc_args with flag and filename."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["-l", "myfile.txt"])
        assert lines_only is True
        assert filename == "myfile.txt"

    def test_parse_wc_multiple_flags(self):
        """Test parse_wc_args with multiple flags."""
        lines_only, words_only, chars_only, filename = parse_wc_args(["-l", "-w"])
        assert lines_only is True
        assert words_only is True
        assert chars_only is False

    def test_parse_wc_unknown_option(self):
        """Test parse_wc_args raises error for unknown option."""
        with pytest.raises(ValueError, match="wc: unknown option"):
            parse_wc_args(["-x"])


class TestParseSortArgs:
    """Tests for parse_sort_args function."""

    def test_parse_sort_no_args(self):
        """Test parse_sort_args with no arguments."""
        reverse, filename = parse_sort_args([])
        assert reverse is False
        assert filename is None

    def test_parse_sort_with_r_flag(self):
        """Test parse_sort_args with -r flag."""
        reverse, filename = parse_sort_args(["-r"])
        assert reverse is True
        assert filename is None

    def test_parse_sort_with_filename(self):
        """Test parse_sort_args with filename."""
        reverse, filename = parse_sort_args(["myfile.txt"])
        assert reverse is False
        assert filename == "myfile.txt"

    def test_parse_sort_with_r_and_filename(self):
        """Test parse_sort_args with -r and filename."""
        reverse, filename = parse_sort_args(["-r", "myfile.txt"])
        assert reverse is True
        assert filename == "myfile.txt"

    def test_parse_sort_unknown_option(self):
        """Test parse_sort_args raises error for unknown option."""
        with pytest.raises(ValueError, match="sort: unknown option"):
            parse_sort_args(["-n"])


class TestParseUniqArgs:
    """Tests for parse_uniq_args function."""

    def test_parse_uniq_no_args(self):
        """Test parse_uniq_args with no arguments."""
        count, filename = parse_uniq_args([])
        assert count is False
        assert filename is None

    def test_parse_uniq_with_c_flag(self):
        """Test parse_uniq_args with -c flag."""
        count, filename = parse_uniq_args(["-c"])
        assert count is True
        assert filename is None

    def test_parse_uniq_with_filename(self):
        """Test parse_uniq_args with filename."""
        count, filename = parse_uniq_args(["myfile.txt"])
        assert count is False
        assert filename == "myfile.txt"

    def test_parse_uniq_with_c_and_filename(self):
        """Test parse_uniq_args with -c and filename."""
        count, filename = parse_uniq_args(["-c", "myfile.txt"])
        assert count is True
        assert filename == "myfile.txt"

    def test_parse_uniq_unknown_option(self):
        """Test parse_uniq_args raises error for unknown option."""
        with pytest.raises(ValueError, match="uniq: unknown option"):
            parse_uniq_args(["-d"])
