"""grep implementation for REPL shell."""

import re
from typing import List, Tuple, Optional
from pathlib import Path

from ebk.vfs import LibraryVFS, DirectoryNode, FileNode


class GrepMatcher:
    """Unix-like grep functionality for VFS."""

    def __init__(self, vfs: LibraryVFS):
        """Initialize grep matcher.

        Args:
            vfs: VFS instance
        """
        self.vfs = vfs

    def grep(
        self,
        pattern: str,
        paths: List[str],
        recursive: bool = False,
        ignore_case: bool = False,
        line_numbers: bool = False,
    ) -> List[Tuple[str, int, str]]:
        """Search for pattern in files.

        Args:
            pattern: Regex pattern to search for
            paths: List of paths to search (files or directories)
            recursive: Search directories recursively
            ignore_case: Case-insensitive matching
            line_numbers: Include line numbers in output

        Returns:
            List of (file_path, line_number, line_content) tuples
        """
        results = []

        # Compile regex
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        # Process each path
        for path in paths:
            results.extend(
                self._search_path(path, regex, recursive, line_numbers)
            )

        return results

    def _search_path(
        self,
        path: str,
        regex: re.Pattern,
        recursive: bool,
        line_numbers: bool,
    ) -> List[Tuple[str, int, str]]:
        """Search a single path.

        Args:
            path: Path to search
            regex: Compiled regex pattern
            recursive: Search recursively
            line_numbers: Include line numbers

        Returns:
            List of matches
        """
        results = []

        # Resolve path
        node = self.vfs.get_node(path)
        if node is None:
            return results

        # If it's a file, search it
        if isinstance(node, FileNode):
            results.extend(self._search_file(node, regex, line_numbers))

        # If it's a directory, search children
        elif isinstance(node, DirectoryNode):
            if recursive:
                results.extend(
                    self._search_directory_recursive(node, regex, line_numbers)
                )
            else:
                # Just search immediate children that are files
                for child in node.list_children():
                    if isinstance(child, FileNode):
                        results.extend(
                            self._search_file(child, regex, line_numbers)
                        )

        return results

    def _search_file(
        self,
        file_node: FileNode,
        regex: re.Pattern,
        line_numbers: bool,
    ) -> List[Tuple[str, int, str]]:
        """Search a single file.

        Args:
            file_node: File node to search
            regex: Compiled regex pattern
            line_numbers: Include line numbers

        Returns:
            List of matches
        """
        results = []

        try:
            content = file_node.read_content()
            lines = content.split("\n")

            file_path = file_node.get_path()

            for i, line in enumerate(lines, start=1):
                if regex.search(line):
                    line_num = i if line_numbers else 0
                    results.append((file_path, line_num, line))

        except Exception:
            # Skip files that can't be read
            pass

        return results

    def _search_directory_recursive(
        self,
        dir_node: DirectoryNode,
        regex: re.Pattern,
        line_numbers: bool,
    ) -> List[Tuple[str, int, str]]:
        """Search directory recursively.

        Args:
            dir_node: Directory node to search
            regex: Compiled regex pattern
            line_numbers: Include line numbers

        Returns:
            List of matches
        """
        results = []

        try:
            children = dir_node.list_children()

            for child in children:
                if isinstance(child, FileNode):
                    results.extend(self._search_file(child, regex, line_numbers))
                elif isinstance(child, DirectoryNode):
                    # Recurse into subdirectory
                    results.extend(
                        self._search_directory_recursive(
                            child, regex, line_numbers
                        )
                    )

        except Exception:
            # Skip directories that can't be read
            pass

        return results
