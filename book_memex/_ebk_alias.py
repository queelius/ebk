"""Deprecation shim for the old `ebk` CLI entrypoint.

Prints a one-time deprecation notice and forwards to the book-memex CLI.
This alias is scheduled for removal in the release after v1.
"""
import sys
import warnings

from book_memex.cli import app


def main():
    warnings.warn(
        "The `ebk` command has been renamed to `book-memex`. "
        "`ebk` will be removed in the release after v1. "
        "Update your scripts and configs to use `book-memex`.",
        DeprecationWarning,
        stacklevel=2,
    )
    print(
        "[DEPRECATED] `ebk` is now `book-memex`. Use `book-memex` going forward.",
        file=sys.stderr,
    )
    app()
