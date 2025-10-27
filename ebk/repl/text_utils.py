"""Text processing utilities for REPL shell.

Implements Unix-like text utilities: head, tail, wc, sort, uniq.
All utilities support reading from stdin or file content.
"""

from typing import Optional, List


class TextUtils:
    """Collection of text processing utilities."""

    @staticmethod
    def head(content: str, lines: int = 10) -> str:
        """Return first N lines of content.

        Args:
            content: Input text
            lines: Number of lines to return (default: 10)

        Returns:
            First N lines joined with newlines
        """
        if not content:
            return ""

        text_lines = content.split("\n")
        return "\n".join(text_lines[:lines])

    @staticmethod
    def tail(content: str, lines: int = 10) -> str:
        """Return last N lines of content.

        Args:
            content: Input text
            lines: Number of lines to return (default: 10)

        Returns:
            Last N lines joined with newlines
        """
        if not content:
            return ""

        text_lines = content.split("\n")
        return "\n".join(text_lines[-lines:])

    @staticmethod
    def wc(content: str, lines_only: bool = False, words_only: bool = False,
           chars_only: bool = False) -> str:
        """Count lines, words, and characters.

        Args:
            content: Input text
            lines_only: Only count lines (-l flag)
            words_only: Only count words (-w flag)
            chars_only: Only count characters (-c flag)

        Returns:
            Formatted count string
        """
        if not content:
            return "0"

        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        word_count = len(content.split())
        char_count = len(content)

        if lines_only:
            return str(line_count)
        elif words_only:
            return str(word_count)
        elif chars_only:
            return str(char_count)
        else:
            # Show all three
            return f"{line_count:>8} {word_count:>8} {char_count:>8}"

    @staticmethod
    def sort_lines(content: str, reverse: bool = False) -> str:
        """Sort lines alphabetically.

        Args:
            content: Input text
            reverse: Sort in reverse order (default: False)

        Returns:
            Sorted lines joined with newlines
        """
        if not content:
            return ""

        lines = content.split("\n")
        # Filter out empty last line if present
        if lines and lines[-1] == "":
            lines = lines[:-1]
            sorted_lines = sorted(lines, reverse=reverse)
            return "\n".join(sorted_lines) + "\n"
        else:
            sorted_lines = sorted(lines, reverse=reverse)
            return "\n".join(sorted_lines)

    @staticmethod
    def uniq(content: str, count: bool = False) -> str:
        """Remove duplicate adjacent lines.

        Args:
            content: Input text
            count: Prefix lines with occurrence count (-c flag)

        Returns:
            Unique lines, optionally with counts
        """
        if not content:
            return ""

        lines = content.split("\n")
        if not lines:
            return ""

        unique_lines = []
        current_line = None
        current_count = 0

        for line in lines:
            if line == current_line:
                current_count += 1
            else:
                # Save previous line if exists
                if current_line is not None:
                    if count:
                        unique_lines.append(f"{current_count:>7} {current_line}")
                    else:
                        unique_lines.append(current_line)

                # Start new line
                current_line = line
                current_count = 1

        # Don't forget the last line
        if current_line is not None:
            if count:
                unique_lines.append(f"{current_count:>7} {current_line}")
            else:
                unique_lines.append(current_line)

        return "\n".join(unique_lines)


def parse_head_args(args: List[str]) -> tuple[int, Optional[str]]:
    """Parse head command arguments.

    Args:
        args: Command arguments

    Returns:
        Tuple of (line_count, filename)

    Raises:
        ValueError: If arguments are invalid
    """
    lines = 10
    filename = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "-n":
            # Next arg is line count
            if i + 1 >= len(args):
                raise ValueError("head: -n requires an argument")
            try:
                lines = int(args[i + 1])
                i += 2
            except ValueError:
                raise ValueError(f"head: invalid line count: {args[i + 1]}")
        elif arg.startswith("-") and arg[1:].isdigit():
            # Short form: -10
            try:
                lines = int(arg[1:])
                i += 1
            except ValueError:
                raise ValueError(f"head: invalid line count: {arg}")
        elif not arg.startswith("-"):
            # Filename
            filename = arg
            i += 1
        else:
            raise ValueError(f"head: unknown option: {arg}")

    return lines, filename


def parse_tail_args(args: List[str]) -> tuple[int, Optional[str]]:
    """Parse tail command arguments.

    Args:
        args: Command arguments

    Returns:
        Tuple of (line_count, filename)

    Raises:
        ValueError: If arguments are invalid
    """
    lines = 10
    filename = None

    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "-n":
            # Next arg is line count
            if i + 1 >= len(args):
                raise ValueError("tail: -n requires an argument")
            try:
                lines = int(args[i + 1])
                i += 2
            except ValueError:
                raise ValueError(f"tail: invalid line count: {args[i + 1]}")
        elif arg.startswith("-") and arg[1:].isdigit():
            # Short form: -10
            try:
                lines = int(arg[1:])
                i += 1
            except ValueError:
                raise ValueError(f"tail: invalid line count: {arg}")
        elif not arg.startswith("-"):
            # Filename
            filename = arg
            i += 1
        else:
            raise ValueError(f"tail: unknown option: {arg}")

    return lines, filename


def parse_wc_args(args: List[str]) -> tuple[bool, bool, bool, Optional[str]]:
    """Parse wc command arguments.

    Args:
        args: Command arguments

    Returns:
        Tuple of (lines_only, words_only, chars_only, filename)

    Raises:
        ValueError: If arguments are invalid
    """
    lines_only = False
    words_only = False
    chars_only = False
    filename = None

    for arg in args:
        if arg == "-l":
            lines_only = True
        elif arg == "-w":
            words_only = True
        elif arg == "-c":
            chars_only = True
        elif not arg.startswith("-"):
            filename = arg
        else:
            raise ValueError(f"wc: unknown option: {arg}")

    return lines_only, words_only, chars_only, filename


def parse_sort_args(args: List[str]) -> tuple[bool, Optional[str]]:
    """Parse sort command arguments.

    Args:
        args: Command arguments

    Returns:
        Tuple of (reverse, filename)

    Raises:
        ValueError: If arguments are invalid
    """
    reverse = False
    filename = None

    for arg in args:
        if arg == "-r":
            reverse = True
        elif not arg.startswith("-"):
            filename = arg
        else:
            raise ValueError(f"sort: unknown option: {arg}")

    return reverse, filename


def parse_uniq_args(args: List[str]) -> tuple[bool, Optional[str]]:
    """Parse uniq command arguments.

    Args:
        args: Command arguments

    Returns:
        Tuple of (count, filename)

    Raises:
        ValueError: If arguments are invalid
    """
    count = False
    filename = None

    for arg in args:
        if arg == "-c":
            count = True
        elif not arg.startswith("-"):
            filename = arg
        else:
            raise ValueError(f"uniq: unknown option: {arg}")

    return count, filename
