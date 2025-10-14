import os
import sys
import json
import shutil
import csv
from pathlib import Path
import logging
import re
from typing import List, Optional
from datetime import datetime
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.prompt import Confirm
from rich.traceback import install
from rich.table import Table

from .decorators import handle_library_errors
from .ident import add_unique_id

# Export functions (still available)
try:
    from .exports.hugo import export_hugo
    from .exports.zip import export_zipfile
    from .exports.jinja_export import JinjaExporter
except ImportError:
    export_hugo = None
    export_zipfile = None
    JinjaExporter = None

# Initialize Rich Traceback for better error messages
install(show_locals=True)

# Initialize Rich Console
console = Console()

# Configure logging to use Rich's RichHandler
logging.basicConfig(
    level=logging.INFO,  # Set to INFO by default, DEBUG if verbose
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
logger = logging.getLogger(__name__)

# Main app
app = typer.Typer()

# Command groups
export_app = typer.Typer(help="Export library data to various formats")
vlib_app = typer.Typer(help="Manage virtual libraries (collection views)")
note_app = typer.Typer(help="Manage book annotations and notes")

# Register command groups
app.add_typer(export_app, name="export")
app.add_typer(vlib_app, name="vlib")
app.add_typer(note_app, name="note")

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode"),
):
    """
    ebk - eBook metadata management tool with SQLAlchemy + SQLite backend.

    Manage your ebook library with full-text search, automatic text extraction,
    and hash-based deduplication.
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
        console.print("[bold green]Verbose mode enabled.[/bold green]")


@app.command()
def about():
    """Display information about ebk."""
    console.print("[bold cyan]ebk - eBook Metadata Management Tool[/bold cyan]")
    console.print("")
    console.print("A powerful tool for managing ebook libraries with:")
    console.print("  • SQLAlchemy + SQLite database backend")
    console.print("  • Full-text search (FTS5)")
    console.print("  • Automatic text extraction from PDFs, EPUBs, plaintext")
    console.print("  • Hash-based file deduplication")
    console.print("  • Cover extraction and thumbnails")
    console.print("  • Virtual libraries and personal metadata")
    console.print("")
    console.print("[bold]Core Commands:[/bold]")
    console.print("  ebk init <path>              Initialize new library")
    console.print("  ebk import <file> <lib>      Import ebook")
    console.print("  ebk import-calibre <src>     Import from Calibre")
    console.print("  ebk search <query> <lib>     Full-text search")
    console.print("  ebk list <lib>               List books")
    console.print("  ebk stats <lib>              Show statistics")
    console.print("  ebk view <id> <lib>          View book content")
    console.print("")
    console.print("[bold]Command Groups:[/bold]")
    console.print("  ebk export <subcommand>      Export library data")
    console.print("  ebk vlib <subcommand>        Manage virtual libraries")
    console.print("  ebk note <subcommand>        Manage annotations")
    console.print("")
    console.print("[bold]Getting Started:[/bold]")
    console.print("  1. Initialize: ebk init ~/my-library")
    console.print("  2. Import: ebk import book.pdf ~/my-library")
    console.print("  3. Search: ebk search 'python' ~/my-library")
    console.print("")
    console.print("For more info: https://github.com/queelius/ebk")


# ============================================================================
# Core Library Commands
# ============================================================================

@app.command()
def init(
    library_path: Path = typer.Argument(..., help="Path to create the library"),
    echo_sql: bool = typer.Option(False, "--echo-sql", help="Echo SQL statements for debugging")
):
    """
    Initialize a new database-backed library.

    This creates a new library directory with SQLite database backend,
    including directories for files, covers, and vector embeddings.

    Example:
        ebk init ~/my-library
    """
    from .library_db import Library

    library_path = Path(library_path)

    if library_path.exists() and any(library_path.iterdir()):
        console.print(f"[yellow]Warning: Directory {library_path} already exists and is not empty[/yellow]")
        if not Confirm.ask("Continue anyway?"):
            raise typer.Exit(code=0)

    try:
        lib = Library.open(library_path, echo=echo_sql)
        lib.close()
        console.print(f"[green]✓ Library initialized at {library_path}[/green]")
        console.print(f"  Database: {library_path / 'library.db'}")
        console.print(f"  Use 'ebk import' to add books")
    except Exception as e:
        console.print(f"[red]Error initializing library: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="import")
def import_book(
    file_path: Path = typer.Argument(..., help="Path to ebook file"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Book title"),
    authors: Optional[str] = typer.Option(None, "--authors", "-a", help="Authors (comma-separated)"),
    subjects: Optional[str] = typer.Option(None, "--subjects", "-s", help="Subjects/tags (comma-separated)"),
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
    no_text: bool = typer.Option(False, "--no-text", help="Skip text extraction"),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover extraction"),
    auto_metadata: bool = typer.Option(True, "--auto-metadata/--no-auto-metadata", help="Extract metadata from file")
):
    """
    Import an ebook file into a database-backed library.

    Extracts metadata, text, and cover images automatically unless disabled.
    Supports PDF, EPUB, MOBI, and plaintext files.

    Examples:
        ebk import book.pdf ~/my-library
        ebk import book.epub ~/my-library --title "My Book" --authors "Author Name"
    """
    from .library_db import Library
    from .extract_metadata import extract_metadata

    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(code=1)

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        console.print(f"[yellow]Initialize a library first with: ebk init {library_path}[/yellow]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Build metadata dict
        metadata = {}

        # Auto-extract metadata from file if enabled
        if auto_metadata:
            extracted = extract_metadata(str(file_path))
            metadata.update(extracted)

        # Override with CLI arguments
        if title:
            metadata['title'] = title
        if authors:
            metadata['creators'] = [a.strip() for a in authors.split(',')]
        if subjects:
            metadata['subjects'] = [s.strip() for s in subjects.split(',')]
        if language:
            metadata['language'] = language

        # Ensure title exists
        if 'title' not in metadata:
            metadata['title'] = file_path.stem

        # Import book
        book = lib.add_book(
            file_path,
            metadata,
            extract_text=not no_text,
            extract_cover=not no_cover
        )

        if book:
            console.print(f"[green]✓ Imported: {book.title}[/green]")
            console.print(f"  ID: {book.id}")
            console.print(f"  Authors: {', '.join(a.name for a in book.authors)}")
            console.print(f"  Files: {len(book.files)}")
        else:
            console.print("[yellow]Import failed or book already exists[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error importing book: {e}[/red]")
        logger.exception("Import error details:")
        raise typer.Exit(code=1)


@app.command(name="import-calibre")
def import_calibre(
    calibre_path: Path = typer.Argument(..., help="Path to Calibre library"),
    library_path: Path = typer.Argument(..., help="Path to ebk library"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of books to import")
):
    """
    Import books from a Calibre library into database-backed library.

    Reads Calibre's metadata.opf files and imports ebooks with full metadata.
    Supports all Calibre-managed formats (PDF, EPUB, MOBI, etc.).

    Examples:
        ebk import-calibre ~/Calibre/Library ~/my-library
        ebk import-calibre ~/Calibre/Library ~/my-library --limit 100
    """
    from .library_db import Library

    if not calibre_path.exists():
        console.print(f"[red]Error: Calibre library not found: {calibre_path}[/red]")
        raise typer.Exit(code=1)

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        console.print(f"[yellow]Initialize a library first with: ebk init {library_path}[/yellow]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Find all metadata.opf files
        console.print(f"Scanning Calibre library...")
        opf_files = list(calibre_path.rglob("metadata.opf"))

        if limit:
            opf_files = opf_files[:limit]

        console.print(f"Found {len(opf_files)} books in Calibre library")

        if len(opf_files) == 0:
            console.print("[yellow]No books found. Make sure this is a Calibre library directory.[/yellow]")
            lib.close()
            raise typer.Exit(code=0)

        imported = 0
        failed = 0

        with Progress() as progress:
            task = progress.add_task("[green]Importing...", total=len(opf_files))

            for opf_path in opf_files:
                try:
                    book = lib.add_calibre_book(opf_path)
                    if book:
                        imported += 1
                    else:
                        failed += 1
                except Exception as e:
                    failed += 1
                    logger.debug(f"Failed to import {opf_path.parent.name}: {e}")

                progress.advance(task)

        console.print(f"[green]✓ Import complete[/green]")
        console.print(f"  Successfully imported: {imported}")
        if failed > 0:
            console.print(f"  Failed: {failed}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error importing Calibre library: {e}[/red]")
        logger.exception("Calibre import error details:")
        raise typer.Exit(code=1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results")
):
    """
    Search books in database-backed library using full-text search.

    Searches across titles, descriptions, and extracted text content using
    SQLite's FTS5 engine for fast, relevance-ranked results.

    Examples:
        ebk search "python programming" ~/my-library
        ebk search "machine learning" ~/my-library --limit 50
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        results = lib.search(query, limit=limit)

        if not results:
            console.print(f"[yellow]No results found for: {query}[/yellow]")
        else:
            table = Table(title=f"Search Results: '{query}'")
            table.add_column("ID", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Authors", style="blue")
            table.add_column("Language", style="magenta")

            for book in results:
                authors = ", ".join(a.name for a in book.authors[:2])
                if len(book.authors) > 2:
                    authors += f" +{len(book.authors) - 2} more"

                table.add_row(
                    str(book.id),
                    book.title[:50],
                    authors,
                    book.language or "?"
                )

            console.print(table)
            console.print(f"\n[dim]Showing {len(results)} results[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error searching library: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def stats(
    library_path: Path = typer.Argument(..., help="Path to library")
):
    """
    Show statistics for database-backed library.

    Displays book counts, author counts, language distribution,
    format distribution, and reading progress.

    Example:
        ebk stats ~/my-library
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        stats = lib.stats()

        table = Table(title="Library Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green", justify="right")

        table.add_row("Total Books", str(stats['total_books']))
        table.add_row("Total Authors", str(stats['total_authors']))
        table.add_row("Total Subjects", str(stats['total_subjects']))
        table.add_row("Total Files", str(stats['total_files']))
        table.add_row("Books Read", str(stats['read_count']))
        table.add_row("Currently Reading", str(stats['reading_count']))

        console.print(table)

        # Language distribution
        if stats['languages']:
            console.print("\n[bold]Languages:[/bold]")
            for lang, count in sorted(stats['languages'].items(), key=lambda x: x[1], reverse=True):
                console.print(f"  {lang}: {count}")

        # Format distribution
        if stats['formats']:
            console.print("\n[bold]Formats:[/bold]")
            for fmt, count in sorted(stats['formats'].items(), key=lambda x: x[1], reverse=True):
                console.print(f"  {fmt}: {count}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error getting library stats: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="list")
def list_books(
    library_path: Path = typer.Argument(..., help="Path to library"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum number of books to show"),
    offset: int = typer.Option(0, "--offset", help="Starting offset"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Filter by author"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language")
):
    """
    List books in database-backed library with optional filtering.

    Supports pagination and filtering by author, subject, or language.

    Examples:
        ebk list ~/my-library
        ebk list ~/my-library --author "Knuth"
        ebk list ~/my-library --subject "Python" --limit 20
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Build query with filters
        query = lib.query()

        if author:
            query = query.filter_by_author(author)
        if subject:
            query = query.filter_by_subject(subject)
        if language:
            query = query.filter_by_language(language)

        query = query.order_by('title').limit(limit).offset(offset)

        books = query.all()
        total = query.count()

        if not books:
            console.print("[yellow]No books found[/yellow]")
        else:
            table = Table(title="Books")
            table.add_column("ID", style="cyan")
            table.add_column("Title", style="green")
            table.add_column("Authors", style="blue")
            table.add_column("Language", style="magenta")
            table.add_column("Formats", style="yellow")

            for book in books:
                authors = ", ".join(a.name for a in book.authors[:2])
                if len(book.authors) > 2:
                    authors += f" +{len(book.authors) - 2}"

                formats = ", ".join(f.format for f in book.files)

                table.add_row(
                    str(book.id),
                    book.title[:40],
                    authors[:30],
                    book.language or "?",
                    formats
                )

            console.print(table)
            console.print(f"\n[dim]Showing {len(books)} of {total} books (offset: {offset})[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error listing books: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Personal Metadata Commands (Tags, Ratings, Favorites, Annotations)
# ============================================================================

@app.command()
def rate(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    rating: float = typer.Option(..., "--rating", "-r", help="Rating (0-5 stars)")
):
    """
    Rate a book (0-5 stars).

    Example:
        ebk rate 42 ~/my-library --rating 4.5
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    if not (0 <= rating <= 5):
        console.print(f"[red]Error: Rating must be between 0 and 5[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        lib.update_reading_status(book_id, "unread", rating=rating)

        book = lib.get_book(book_id)
        if book:
            console.print(f"[green]✓ Rated '{book.title}': {rating} stars[/green]")
        else:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error rating book: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def favorite(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    unfavorite: bool = typer.Option(False, "--unfavorite", "-u", help="Remove from favorites")
):
    """
    Mark/unmark a book as favorite.

    Examples:
        ebk favorite 42 ~/my-library
        ebk favorite 42 ~/my-library --unfavorite
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        lib.set_favorite(book_id, favorite=not unfavorite)

        book = lib.get_book(book_id)
        if book:
            action = "Removed from" if unfavorite else "Added to"
            console.print(f"[green]✓ {action} favorites: '{book.title}'[/green]")
        else:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error updating favorite: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def tag(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    tags: str = typer.Option(..., "--tags", "-t", help="Tags (comma-separated)"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove tags instead of adding")
):
    """
    Add or remove personal tags from a book.

    Examples:
        ebk tag 42 ~/my-library --tags "to-read,programming"
        ebk tag 42 ~/my-library --tags "to-read" --remove
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_list = [t.strip() for t in tags.split(',')]

        if remove:
            lib.remove_tags(book_id, tag_list)
            action = "Removed tags from"
        else:
            lib.add_tags(book_id, tag_list)
            action = "Added tags to"

        book = lib.get_book(book_id)
        if book:
            console.print(f"[green]✓ {action} '{book.title}': {', '.join(tag_list)}[/green]")
        else:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error updating tags: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def purge(
    library_path: Path = typer.Argument(..., help="Path to library"),
    # Filtering criteria
    no_files: bool = typer.Option(False, "--no-files", help="Purge books with no file attachments"),
    no_supported_formats: bool = typer.Option(False, "--no-supported-formats", help="Purge books without supported ebook formats (pdf, epub, mobi, azw3)"),
    language: Optional[str] = typer.Option(None, "--language", help="Purge books in this language"),
    format_filter: Optional[str] = typer.Option(None, "--format", help="Purge books with this format only"),
    unread: bool = typer.Option(False, "--unread", help="Purge unread books only"),
    max_rating: Optional[int] = typer.Option(None, "--max-rating", help="Purge books with rating <= this (1-5)"),
    author: Optional[str] = typer.Option(None, "--author", help="Purge books by this author (partial match)"),
    subject: Optional[str] = typer.Option(None, "--subject", help="Purge books with this subject (partial match)"),
    # Safety options
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Show what would be deleted without deleting"),
    delete_files: bool = typer.Option(False, "--delete-files", help="Also delete associated files from disk")
):
    """
    Remove books from library based on filtering criteria.

    By default runs in dry-run mode to show what would be deleted.
    Use --execute to actually perform the deletion.

    WARNING: This operation cannot be undone!

    Examples:
        # Preview books without files
        ebk purge ~/my-library --no-files

        # Preview books without supported ebook formats
        ebk purge ~/my-library --no-supported-formats

        # Delete books without files (after confirming)
        ebk purge ~/my-library --no-files --execute

        # Delete books with only unsupported formats
        ebk purge ~/my-library --no-supported-formats --execute

        # Delete unread books with rating <= 2 and their files
        ebk purge ~/my-library --unread --max-rating 2 --execute --delete-files

        # Delete all books in a specific language
        ebk purge ~/my-library --language fr --execute
    """
    from .library_db import Library
    from rich.table import Table

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Build filtered query
        query = lib.query()

        # Apply filters
        if language:
            query = query.filter_by_language(language)
        if author:
            query = query.filter_by_author(author)
        if subject:
            query = query.filter_by_subject(subject)
        if format_filter:
            query = query.filter_by_format(format_filter)
        if max_rating is not None:
            # Get books with rating <= max_rating
            query = query.filter_by_rating(0, max_rating)
        if unread:
            # Filter for unread status
            from .db.models import PersonalMetadata
            query.query = query.query.join(PersonalMetadata).filter(
                PersonalMetadata.reading_status == 'unread'
            )

        books = query.all()

        # Filter for no files if requested
        if no_files:
            books = [b for b in books if len(b.files) == 0]

        # Filter for no supported formats if requested
        if no_supported_formats:
            SUPPORTED_FORMATS = {'pdf', 'epub', 'mobi', 'azw3', 'azw', 'djvu', 'fb2', 'txt'}
            books = [
                b for b in books
                if len(b.files) == 0 or not any(f.format.lower() in SUPPORTED_FORMATS for f in b.files)
            ]

        if not books:
            console.print("[yellow]No books match the specified criteria[/yellow]")
            lib.close()
            return

        # Display what will be purged
        table = Table(title=f"Books to {'DELETE' if not dry_run else 'purge'} ({len(books)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Authors", style="blue")
        table.add_column("Files", style="magenta")
        table.add_column("Language", style="green")

        for book in books[:20]:  # Show first 20
            authors = ", ".join(a.name for a in book.authors) or "Unknown"
            files = ", ".join(f.format for f in book.files) or "None"
            table.add_row(
                str(book.id),
                book.title[:50],
                authors[:30],
                files,
                book.language or "?"
            )

        if len(books) > 20:
            table.add_row("...", f"and {len(books) - 20} more", "", "", "")

        console.print(table)

        if dry_run:
            console.print("\n[yellow]This is a DRY RUN - no changes will be made[/yellow]")
            console.print("[yellow]Use --execute to actually delete these books[/yellow]")
            if delete_files:
                console.print("[yellow]--delete-files will also remove files from disk[/yellow]")
        else:
            # Confirm deletion
            console.print("\n[red]WARNING: This will permanently delete these books![/red]")
            if delete_files:
                console.print("[red]This will also DELETE FILES from disk![/red]")

            confirm = typer.confirm("Are you sure you want to proceed?")
            if not confirm:
                console.print("[yellow]Purge cancelled[/yellow]")
                lib.close()
                return

            # Perform deletion
            deleted_count = 0
            files_deleted = 0
            total_size = 0

            for book in books:
                # Delete files from disk if requested
                if delete_files:
                    for file in book.files:
                        file_path = library_path / file.path
                        if file_path.exists():
                            total_size += file.size_bytes
                            file_path.unlink()
                            files_deleted += 1

                # Delete from database
                lib.session.delete(book)
                deleted_count += 1

            lib.session.commit()

            console.print(f"\n[green]✓ Deleted {deleted_count} books from database[/green]")
            if delete_files:
                console.print(f"[green]✓ Deleted {files_deleted} files ({total_size / (1024**2):.1f} MB)[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error during purge: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1)


@note_app.command(name="add")
def note_add(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    content: str = typer.Option(..., "--content", "-c", help="Note/annotation text"),
    page: Optional[int] = typer.Option(None, "--page", "-p", help="Page number"),
    note_type: str = typer.Option("note", "--type", "-t", help="Annotation type (note, highlight, bookmark)")
):
    """
    Add a note/annotation to a book.

    Examples:
        ebk note add 42 ~/my-library --content "Great explanation of algorithms"
        ebk note add 42 ~/my-library --content "Important theorem" --page 42
        ebk note add 42 ~/my-library --content "Key passage" --type highlight
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        annotation_id = lib.add_annotation(book_id, content, page=page, annotation_type=note_type)

        book = lib.get_book(book_id)
        if book:
            loc_info = f" (page {page})" if page else ""
            console.print(f"[green]✓ Added {note_type} to '{book.title}'{loc_info}[/green]")
            console.print(f"  Annotation ID: {annotation_id}")
        else:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error adding note: {e}[/red]")
        raise typer.Exit(code=1)


@note_app.command(name="list")
def note_list(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library")
):
    """
    List all notes/annotations for a book.

    Example:
        ebk note list 42 ~/my-library
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        annotations = lib.get_annotations(book_id)

        if not annotations:
            console.print(f"[yellow]No notes found for '{book.title}'[/yellow]")
        else:
            console.print(f"\n[bold]Notes for: {book.title}[/bold]\n")

            for i, ann in enumerate(annotations, 1):
                type_info = f"[{ann.annotation_type}]" if ann.annotation_type else "[note]"
                page_info = f" Page {ann.page_number}" if ann.page_number else ""
                console.print(f"{i}. {type_info}{page_info}")
                console.print(f"   {ann.content}")
                console.print(f"   [dim]ID: {ann.id} | Added: {ann.created_at.strftime('%Y-%m-%d %H:%M')}[/dim]\n")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error listing notes: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Export Commands
# ============================================================================

@export_app.command(name="json")
def export_json(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output JSON file"),
    include_annotations: bool = typer.Option(True, "--annotations/--no-annotations", help="Include annotations")
):
    """
    Export library to JSON format.

    Example:
        ebk export json ~/my-library ~/backup.json
    """
    from .library_db import Library
    import json

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        books = lib.get_all_books()

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "total_books": len(books),
            "books": []
        }

        for book in books:
            book_data = {
                "id": book.id,
                "unique_id": book.unique_id,
                "title": book.title,
                "subtitle": book.subtitle,
                "authors": [a.name for a in book.authors],
                "subjects": [s.name for s in book.subjects],
                "language": book.language,
                "publisher": book.publisher,
                "publication_date": book.publication_date,
                "description": book.description,
                "page_count": book.page_count,
                "word_count": book.word_count,
                "files": [{"format": f.format, "size": f.size_bytes, "path": f.path} for f in book.files],
                "created_at": book.created_at.isoformat(),
            }

            # Add personal metadata if exists
            if book.personal:
                book_data["personal"] = {
                    "reading_status": book.personal.reading_status,
                    "reading_progress": book.personal.reading_progress,
                    "rating": book.personal.rating,
                    "favorite": book.personal.favorite,
                    "tags": book.personal.personal_tags
                }

            # Add annotations if requested
            if include_annotations:
                annotations = lib.get_annotations(book.id)
                book_data["annotations"] = [
                    {
                        "id": ann.id,
                        "type": ann.annotation_type,
                        "content": ann.content,
                        "page": ann.page_number,
                        "position": ann.position,
                        "created_at": ann.created_at.isoformat()
                    }
                    for ann in annotations
                ]

            export_data["books"].append(book_data)

        # Write JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        console.print(f"[green]✓ Exported {len(books)} books to {output_file}[/green]")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to JSON: {e}[/red]")
        raise typer.Exit(code=1)


@export_app.command(name="csv")
def export_csv(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output CSV file")
):
    """
    Export library to CSV format.

    Example:
        ebk export csv ~/my-library ~/books.csv
    """
    from .library_db import Library
    import csv

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        books = lib.get_all_books()

        # Write CSV file
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'ID', 'Title', 'Authors', 'Publisher', 'Publication Date',
                'Language', 'Subjects', 'Page Count', 'Rating', 'Favorite',
                'Reading Status', 'Tags', 'Formats'
            ])

            # Data
            for book in books:
                authors = '; '.join(a.name for a in book.authors)
                subjects = '; '.join(s.name for s in book.subjects)
                formats = ', '.join(f.format for f in book.files)

                rating = book.personal.rating if book.personal else None
                favorite = book.personal.favorite if book.personal else False
                status = book.personal.reading_status if book.personal else 'unread'
                tags = ', '.join(book.personal.personal_tags) if book.personal and book.personal.personal_tags else ''

                writer.writerow([
                    book.id,
                    book.title,
                    authors,
                    book.publisher or '',
                    book.publication_date or '',
                    book.language or '',
                    subjects,
                    book.page_count or '',
                    rating or '',
                    favorite,
                    status,
                    tags,
                    formats
                ])

        console.print(f"[green]✓ Exported {len(books)} books to {output_file}[/green]")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to CSV: {e}[/red]")
        raise typer.Exit(code=1)


@export_app.command(name="html")
def export_html(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output HTML file"),
    include_stats: bool = typer.Option(True, "--stats/--no-stats", help="Include library statistics"),
    base_url: str = typer.Option("", "--base-url", help="Base URL for file links (e.g., '/library' or 'https://example.com/books')"),
    copy_files: bool = typer.Option(False, "--copy", help="Copy referenced files to output directory"),
    # Filtering options
    language: Optional[str] = typer.Option(None, "--language", help="Filter by language code (e.g., 'en', 'es')"),
    author: Optional[str] = typer.Option(None, "--author", help="Filter by author name (partial match)"),
    subject: Optional[str] = typer.Option(None, "--subject", help="Filter by subject/tag (partial match)"),
    format_filter: Optional[str] = typer.Option(None, "--format", help="Filter by file format (e.g., 'pdf', 'epub')"),
    has_files: bool = typer.Option(True, "--has-files/--no-files", help="Only include books with file attachments"),
    favorite: Optional[bool] = typer.Option(None, "--favorite", help="Filter by favorite status"),
    min_rating: Optional[int] = typer.Option(None, "--min-rating", help="Minimum rating (1-5)"),
):
    """
    Export library to a self-contained HTML5 file.

    Creates an interactive, searchable, filterable catalog that works offline.
    All metadata including contributors, series, keywords, etc. is preserved.

    File links are included in the export. Use --base-url to set the URL prefix for files
    when deploying to a web server (e.g., Hugo site).

    Use --copy to copy only the referenced files to the output directory, avoiding duplication
    of the entire library.

    Examples:
        # Basic export with relative paths
        ebk export html ~/my-library ~/library.html

        # Export for Hugo deployment with file copying
        ebk export html ~/my-library ~/hugo/static/library.html \\
            --base-url /library --copy

        # Export only English PDFs rated 4+
        ebk export html ~/my-library ~/library.html \\
            --language en --format pdf --min-rating 4
    """
    from .library_db import Library
    from .exports.html_library import export_to_html
    import shutil

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        console.print("[blue]Exporting library to HTML...[/blue]")
        lib = Library.open(library_path)

        # Build filtered query
        query = lib.query()

        # Apply filters
        if language:
            query = query.filter_by_language(language)
        if author:
            query = query.filter_by_author(author)
        if subject:
            query = query.filter_by_subject(subject)
        if format_filter:
            query = query.filter_by_format(format_filter)
        if favorite is not None:
            query = query.filter_by_favorite(favorite)
        if min_rating:
            query = query.filter_by_rating(min_rating)

        books = query.all()

        # Filter out books without files if requested
        if has_files:
            books = [b for b in books if len(b.files) > 0]

        if not books:
            console.print("[yellow]No books match the specified filters[/yellow]")
            lib.close()
            return

        # Copy files if requested
        if copy_files:
            output_dir = output_file.parent
            if not base_url:
                console.print("[yellow]Warning: --copy requires --base-url to be set[/yellow]")
                console.print("[yellow]Files will be copied but may not resolve correctly[/yellow]")

            # Determine copy destination
            if base_url.startswith(('http://', 'https://')):
                console.print("[red]Error: --copy cannot be used with full URLs in --base-url[/red]")
                console.print("[red]Use a relative path like '/library' instead[/red]")
                lib.close()
                raise typer.Exit(code=1)

            # Copy files to output_dir / base_url (stripping leading /)
            copy_dest = output_dir / base_url.lstrip('/')
            copy_dest.mkdir(parents=True, exist_ok=True)

            console.print(f"[blue]Copying files to {copy_dest}...[/blue]")
            files_copied = 0
            covers_copied = 0
            total_size = 0

            for book in books:
                # Copy ebook files
                for file in book.files:
                    src = library_path / file.path
                    dest = copy_dest / file.path

                    if src.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
                        files_copied += 1
                        total_size += file.size_bytes

                # Copy cover images
                for cover in book.covers:
                    src = library_path / cover.path
                    dest = copy_dest / cover.path

                    if src.exists():
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, dest)
                        covers_copied += 1
                        total_size += src.stat().st_size

            console.print(f"[green]✓ Copied {files_copied} files and {covers_copied} covers ({total_size / (1024**2):.1f} MB)[/green]")

        export_to_html(books, output_file, include_stats=include_stats, base_url=base_url)

        console.print(f"[green]✓ Exported {len(books)} books to {output_file}[/green]")
        if base_url:
            console.print(f"  File links will use base URL: {base_url}")
        console.print(f"  Open {output_file} in a web browser to view your library")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to HTML: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1)


@vlib_app.command(name="add")
def vlib_add(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    vlib: str = typer.Option(..., "--library", "-l", help="Virtual library name (e.g., 'computer-science', 'mathematics')")
):
    """
    Add a book to a virtual library (collection view).

    Virtual libraries allow organizing books into multiple collections.
    A book can belong to multiple virtual libraries.

    Examples:
        ebk vlib add 1 ~/my-library --library computer-science
        ebk vlib add 1 ~/my-library -l mathematics
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        lib.add_to_virtual_library(book_id, vlib)

        book = lib.get_book(book_id)
        if book:
            console.print(f"[green]✓ Added '{book.title}' to virtual library '{vlib}'[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vlib_app.command(name="remove")
def vlib_remove(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    vlib: str = typer.Option(..., "--library", "-l", help="Virtual library name")
):
    """
    Remove a book from a virtual library.

    Example:
        ebk vlib remove 1 ~/my-library --library computer-science
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        lib.remove_from_virtual_library(book_id, vlib)

        book = lib.get_book(book_id)
        if book:
            console.print(f"[green]✓ Removed '{book.title}' from virtual library '{vlib}'[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vlib_app.command(name="list")
def vlib_list(
    library_path: Path = typer.Argument(..., help="Path to library"),
    vlib: Optional[str] = typer.Option(None, "--library", "-l", help="Show books in specific virtual library")
):
    """
    List all virtual libraries or books in a specific virtual library.

    Examples:
        ebk vlib list ~/my-library                     # List all virtual libraries
        ebk vlib list ~/my-library --library mathematics # List books in 'mathematics'
    """
    from .library_db import Library

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        if vlib:
            # Show books in this virtual library
            books = lib.get_virtual_library(vlib)

            if not books:
                console.print(f"[yellow]No books found in virtual library '{vlib}'[/yellow]")
            else:
                console.print(f"\n[bold]Virtual Library: {vlib}[/bold] ({len(books)} books)\n")

                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("ID", style="dim")
                table.add_column("Title")
                table.add_column("Authors")

                for book in books:
                    authors = ", ".join(a.name for a in book.authors[:2])
                    if len(book.authors) > 2:
                        authors += "..."

                    table.add_row(
                        str(book.id),
                        book.title[:50] + "..." if len(book.title) > 50 else book.title,
                        authors
                    )

                console.print(table)
        else:
            # List all virtual libraries
            libraries = lib.list_virtual_libraries()

            if not libraries:
                console.print("[yellow]No virtual libraries found[/yellow]")
                console.print("[dim]Use 'ebk vlib add' to create virtual libraries[/dim]")
            else:
                console.print(f"\n[bold]Virtual Libraries[/bold] ({len(libraries)} total)\n")

                for vlib_name in libraries:
                    books = lib.get_virtual_library(vlib_name)
                    console.print(f"  • {vlib_name} ({len(books)} books)")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def view(
    book_id: int = typer.Argument(..., help="Book ID to view"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    text: bool = typer.Option(False, "--text", help="Display extracted text in console"),
    page: Optional[int] = typer.Option(None, "--page", help="View specific page (for text mode)"),
    format_choice: Optional[str] = typer.Option(None, "--format", help="Choose specific format (pdf, epub, txt, etc.)")
):
    """
    View a book's content.

    Without --text: Opens the ebook file in the default application.
    With --text: Displays extracted text in the console with paging.
    """
    import subprocess
    import platform
    from .library_db import Library
    from .db.models import ExtractedText

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book with ID {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        if text:
            # Display extracted text in console
            # ExtractedText is linked to File, not Book directly
            extracted_text = None
            for file in book.files:
                if file.extracted_text and file.extracted_text.content:
                    extracted_text = file.extracted_text.content
                    break

            if not extracted_text:
                console.print(f"[yellow]No extracted text available for '{book.title}'[/yellow]")
                console.print("[dim]Try re-importing the book with text extraction enabled[/dim]")
                lib.close()
                raise typer.Exit(code=1)

            # Display book info
            console.print(f"\n[bold blue]{book.title}[/bold blue]")
            if book.authors:
                console.print(f"[dim]by {', '.join(a.name for a in book.authors)}[/dim]")
            console.print()

            # If page specified, try to show just that page
            # (This is approximate - we don't have exact page boundaries)
            if page is not None:
                # Estimate ~400 words per page
                words = extracted_text.split()
                words_per_page = 400
                start_idx = (page - 1) * words_per_page
                end_idx = start_idx + words_per_page

                if start_idx >= len(words):
                    console.print(f"[yellow]Page {page} exceeds document length[/yellow]")
                    lib.close()
                    raise typer.Exit(code=1)

                page_words = words[start_idx:end_idx]
                text_content = ' '.join(page_words)
                console.print(f"[dim]Approximate page {page} (words {start_idx+1}-{end_idx}):[/dim]\n")
                console.print(text_content)
            else:
                # Show full text with paging
                # Use rich pager for long text
                with console.pager(styles=True):
                    console.print(extracted_text)
        else:
            # Open file in default application
            if not book.files:
                console.print(f"[yellow]No files available for '{book.title}'[/yellow]")
                lib.close()
                raise typer.Exit(code=1)

            # Select file to open
            file_to_open = None
            if format_choice:
                # Find file matching requested format
                for f in book.files:
                    if f.format.lower() == format_choice.lower():
                        file_to_open = f
                        break
                if not file_to_open:
                    console.print(f"[yellow]No {format_choice} file found for this book[/yellow]")
                    console.print(f"Available formats: {', '.join(f.format for f in book.files)}")
                    lib.close()
                    raise typer.Exit(code=1)
            else:
                # Use first file (prefer PDF > EPUB > others)
                formats_priority = ['pdf', 'epub', 'mobi', 'azw3', 'txt']
                for fmt in formats_priority:
                    for f in book.files:
                        if f.format.lower() == fmt:
                            file_to_open = f
                            break
                    if file_to_open:
                        break

                if not file_to_open:
                    file_to_open = book.files[0]

            file_path = library_path / file_to_open.path

            if not file_path.exists():
                console.print(f"[red]File not found: {file_path}[/red]")
                lib.close()
                raise typer.Exit(code=1)

            console.print(f"[blue]Opening '{book.title}' ({file_to_open.format})[/blue]")

            # Open with default application based on OS
            system = platform.system()
            try:
                if system == 'Darwin':  # macOS
                    subprocess.run(['open', str(file_path)], check=True)
                elif system == 'Windows':
                    subprocess.run(['start', '', str(file_path)], shell=True, check=True)
                else:  # Linux and others
                    subprocess.run(['xdg-open', str(file_path)], check=True)

                console.print("[green]✓ File opened successfully[/green]")
            except subprocess.CalledProcessError as e:
                console.print(f"[red]Failed to open file: {e}[/red]")
                console.print(f"[dim]File location: {file_path}[/dim]")
                lib.close()
                raise typer.Exit(code=1)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error viewing book: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def serve(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (defaults from config)"),
    host: Optional[str] = typer.Option(None, "--host", help="Host to bind to (defaults from config)"),
    port: Optional[int] = typer.Option(None, "--port", help="Port to bind to (defaults from config)"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open browser")
):
    """
    Start the web server for library management.

    Provides a browser-based interface for managing your ebook library.
    Access the interface at http://localhost:8000 (or the specified host/port).

    Configuration:
        Default server settings are loaded from ~/.config/ebk/config.json
        Command-line options override config file values.
        Use 'ebk config' to set default library path and server settings.

    Examples:
        # Start server with configured defaults
        ebk serve

        # Override config for one-time use
        ebk serve ~/my-library --port 8080

        # Start with auto-reload (development)
        ebk serve --reload
    """
    from ebk.config import load_config
    import webbrowser

    # Load config
    config = load_config()

    # Resolve library path
    if library_path is None:
        if config.library.default_path:
            library_path = Path(config.library.default_path)
        else:
            console.print("[red]Error: No library path specified[/red]")
            console.print("[yellow]Either provide a path or set default with:[/yellow]")
            console.print("[yellow]  ebk config --library-path ~/my-library[/yellow]")
            raise typer.Exit(code=1)

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    # Resolve host and port
    server_host = host if host is not None else config.server.host
    server_port = port if port is not None else config.server.port
    auto_open = config.server.auto_open_browser and not no_open

    try:
        import uvicorn
    except ImportError:
        console.print("[red]Error: uvicorn is not installed[/red]")
        console.print("[yellow]Install with: pip install uvicorn[/yellow]")
        raise typer.Exit(code=1)

    try:
        from .server import create_app

        console.print(f"[blue]Starting ebk server...[/blue]")
        console.print(f"[blue]Library: {library_path}[/blue]")
        console.print(f"[green]Server running at http://{server_host}:{server_port}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        # Auto-open browser
        if auto_open:
            # Use localhost for browser even if binding to 0.0.0.0
            browser_host = "localhost" if server_host == "0.0.0.0" else server_host
            url = f"http://{browser_host}:{server_port}"
            console.print(f"[dim]Opening browser to {url}...[/dim]")
            webbrowser.open(url)

        # Create app with library
        app_instance = create_app(library_path)

        # Run server
        uvicorn.run(
            app_instance,
            host=server_host,
            port=server_port,
            reload=reload,
            log_level="info"
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped[/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting server: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def enrich(
    library_path: Path = typer.Argument(..., help="Path to library"),
    provider: Optional[str] = typer.Option(None, help="LLM provider (ollama, openai) - defaults from config"),
    model: Optional[str] = typer.Option(None, help="Model name - defaults from config"),
    host: Optional[str] = typer.Option(None, help="Ollama host (for remote GPU) - defaults from config"),
    port: Optional[int] = typer.Option(None, help="Ollama port - defaults from config"),
    api_key: Optional[str] = typer.Option(None, help="API key (for OpenAI)"),
    book_id: Optional[int] = typer.Option(None, help="Enrich specific book ID only"),
    generate_tags: bool = typer.Option(True, help="Generate tags"),
    categorize: bool = typer.Option(True, help="Categorize books"),
    enhance_descriptions: bool = typer.Option(False, help="Enhance descriptions"),
    assess_difficulty: bool = typer.Option(False, help="Assess difficulty levels"),
    dry_run: bool = typer.Option(False, help="Show what would be done without saving"),
):
    """
    Enrich book metadata using LLM.

    Uses LLM to generate tags, categorize books, enhance descriptions,
    and assess difficulty levels based on existing metadata and extracted text.

    Configuration:
        Default LLM settings are loaded from ~/.config/ebk/config.json
        Command-line options override config file values.
        Use 'ebk config' to view/edit your default configuration.

    Examples:
        # Enrich all books using configured defaults
        ebk enrich ~/my-library

        # Override config to use different host
        ebk enrich ~/my-library --host 192.168.1.100

        # Enrich specific book
        ebk enrich ~/my-library --book-id 42

        # Generate tags and descriptions
        ebk enrich ~/my-library --enhance-descriptions

        # Dry run to see what would be generated
        ebk enrich ~/my-library --dry-run
    """
    import asyncio
    from ebk.library_db import Library
    from ebk.ai.llm_providers.ollama import OllamaProvider
    from ebk.ai.llm_providers.base import LLMConfig
    from ebk.ai.metadata_enrichment import MetadataEnrichmentService
    from ebk.config import load_config

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    # Load configuration and apply CLI overrides
    config = load_config()
    llm_cfg = config.llm

    # Override config with CLI options if provided
    if provider is not None:
        llm_cfg.provider = provider
    if model is not None:
        llm_cfg.model = model
    if host is not None:
        llm_cfg.host = host
    if port is not None:
        llm_cfg.port = port
    if api_key is not None:
        llm_cfg.api_key = api_key

    console.print(f"[dim]Using provider: {llm_cfg.provider}[/dim]")
    console.print(f"[dim]Model: {llm_cfg.model}[/dim]")
    console.print(f"[dim]Host: {llm_cfg.host}:{llm_cfg.port}[/dim]")

    async def enrich_library():
        # Initialize LLM provider
        console.print(f"[blue]Initializing {llm_cfg.provider} provider...[/blue]")

        if llm_cfg.provider == "ollama":
            llm_provider = OllamaProvider.remote(
                host=llm_cfg.host,
                port=llm_cfg.port,
                model=llm_cfg.model,
                temperature=llm_cfg.temperature
            )
        elif llm_cfg.provider == "openai":
            if not llm_cfg.api_key:
                console.print("[red]Error: API key required for OpenAI (use --api-key or set in config)[/red]")
                raise typer.Exit(code=1)
            config = LLMConfig(
                base_url="https://api.openai.com/v1",
                api_key=llm_cfg.api_key,
                model=llm_cfg.model
            )
            # Would need OpenAI provider implementation
            console.print("[red]OpenAI provider not yet implemented[/red]")
            raise typer.Exit(code=1)
        else:
            console.print(f"[red]Unknown provider: {llm_cfg.provider}[/red]")
            raise typer.Exit(code=1)

        # Initialize provider
        await llm_provider.initialize()

        try:
            # Test connection by listing models
            models = await llm_provider.list_models()
            console.print(f"[green]Connected! Available models: {', '.join(models[:5])}[/green]")

            # Initialize service
            service = MetadataEnrichmentService(llm_provider)

            # Open library
            console.print(f"[blue]Opening library: {library_path}[/blue]")
            lib = Library.open(library_path)

            try:
                # Get books to process
                if book_id:
                    books = [lib.get_book(book_id)]
                    if not books[0]:
                        console.print(f"[red]Book ID {book_id} not found[/red]")
                        raise typer.Exit(code=1)
                else:
                    books = lib.query().all()

                console.print(f"[blue]Processing {len(books)} books...[/blue]")

                with Progress() as progress:
                    task = progress.add_task("Enriching metadata...", total=len(books))

                    for book in books:
                        progress.console.print(f"\n[cyan]Processing: {book.title}[/cyan]")

                        # Get extracted text if available
                        text_sample = None
                        if book.files:
                            for file in book.files:
                                if file.extracted_text and file.extracted_text.content:
                                    text_sample = file.extracted_text.content[:5000]
                                    break

                        # Generate tags
                        if generate_tags:
                            progress.console.print("  Generating tags...")
                            tags = await service.generate_tags(
                                title=book.title,
                                authors=[a.name for a in book.authors],
                                subjects=[s.name for s in book.subjects],
                                description=book.description,
                                text_sample=text_sample
                            )

                            if tags:
                                progress.console.print(f"  [green]Tags: {', '.join(tags)}[/green]")
                                if not dry_run:
                                    lib.add_tags(book.id, tags)

                        # Categorize
                        if categorize:
                            progress.console.print("  Categorizing...")
                            categories = await service.categorize(
                                title=book.title,
                                subjects=[s.name for s in book.subjects],
                                description=book.description
                            )

                            if categories:
                                progress.console.print(f"  [green]Categories: {', '.join(categories)}[/green]")
                                if not dry_run:
                                    # Add categories as subjects
                                    for cat in categories:
                                        lib.add_subject(book.id, cat)

                        # Enhance description
                        if enhance_descriptions and (not book.description or len(book.description) < 100):
                            progress.console.print("  Enhancing description...")
                            description = await service.enhance_description(
                                title=book.title,
                                existing_description=book.description,
                                text_sample=text_sample
                            )

                            if description and description != book.description:
                                progress.console.print(f"  [green]New description: {description[:100]}...[/green]")
                                if not dry_run:
                                    book.description = description
                                    lib.session.commit()

                        # Assess difficulty
                        if assess_difficulty and text_sample:
                            progress.console.print("  Assessing difficulty...")
                            difficulty = await service.assess_difficulty(
                                text_sample=text_sample,
                                subjects=[s.name for s in book.subjects]
                            )

                            progress.console.print(f"  [green]Difficulty: {difficulty}[/green]")
                            # Could store in keywords or custom field

                        progress.update(task, advance=1)

                if dry_run:
                    console.print("\n[yellow]Dry run completed - no changes saved[/yellow]")
                else:
                    lib.session.commit()
                    console.print("\n[green]Enrichment completed![/green]")

            finally:
                lib.close()

        finally:
            await llm_provider.cleanup()

    # Run async function
    try:
        asyncio.run(enrich_library())
    except KeyboardInterrupt:
        console.print("\n[yellow]Enrichment cancelled[/yellow]")
    except Exception as e:
        console.print(f"[red]Enrichment failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def config(
    show: bool = typer.Option(False, "--show", help="Show current configuration"),
    init: bool = typer.Option(False, "--init", help="Initialize config file with defaults"),
    # LLM settings
    set_provider: Optional[str] = typer.Option(None, "--llm-provider", help="Set LLM provider (ollama, openai)"),
    set_model: Optional[str] = typer.Option(None, "--llm-model", help="Set default model name"),
    set_llm_host: Optional[str] = typer.Option(None, "--llm-host", help="Set Ollama/LLM host"),
    set_llm_port: Optional[int] = typer.Option(None, "--llm-port", help="Set Ollama/LLM port"),
    set_api_key: Optional[str] = typer.Option(None, "--llm-api-key", help="Set LLM API key"),
    set_temperature: Optional[float] = typer.Option(None, "--llm-temperature", help="Set temperature (0.0-1.0)"),
    # Server settings
    set_server_host: Optional[str] = typer.Option(None, "--server-host", help="Set web server host"),
    set_server_port: Optional[int] = typer.Option(None, "--server-port", help="Set web server port"),
    set_auto_open: Optional[bool] = typer.Option(None, "--server-auto-open/--no-server-auto-open", help="Auto-open browser on server start"),
    # Library settings
    set_library_path: Optional[str] = typer.Option(None, "--library-path", help="Set default library path"),
    # CLI settings
    set_verbose: Optional[bool] = typer.Option(None, "--cli-verbose/--no-cli-verbose", help="Enable verbose output by default"),
    set_color: Optional[bool] = typer.Option(None, "--cli-color/--no-cli-color", help="Enable colored output by default"),
):
    """
    View or edit EBK configuration.

    Configuration is stored at ~/.config/ebk/config.json (or ~/.ebk/config.json).

    Examples:
        # Show current configuration
        ebk config --show

        # Initialize config file with defaults
        ebk config --init

        # Set default library path
        ebk config --library-path ~/my-library

        # Set remote Ollama host
        ebk config --llm-host 192.168.0.225

        # Set server to auto-open browser
        ebk config --server-auto-open --server-host 0.0.0.0

        # Set multiple values
        ebk config --llm-host 192.168.0.225 --llm-model llama3.2 --server-port 9000
    """
    from ebk.config import (
        load_config, save_config, ensure_config_exists,
        update_config, get_config_path
    )
    import json

    # Handle --init
    if init:
        config_path = ensure_config_exists()
        console.print(f"[green]Configuration initialized at {config_path}[/green]")
        return

    # Check if any settings provided
    has_settings = any([
        set_provider, set_model, set_llm_host, set_llm_port, set_api_key, set_temperature,
        set_server_host, set_server_port, set_auto_open is not None,
        set_library_path, set_verbose is not None, set_color is not None
    ])

    # Handle --show or no args (default to show)
    if show or not has_settings:
        config = load_config()
        config_path = get_config_path()

        console.print(f"\n[bold]EBK Configuration[/bold]")
        console.print(f"[dim]Location: {config_path}[/dim]\n")

        console.print("[bold cyan]Library Settings:[/bold cyan]")
        if config.library.default_path:
            console.print(f"  Default Path: {config.library.default_path}")
        else:
            console.print(f"  Default Path: [dim]not set[/dim]")

        console.print("\n[bold cyan]LLM Settings:[/bold cyan]")
        console.print(f"  Provider:    {config.llm.provider}")
        console.print(f"  Model:       {config.llm.model}")
        console.print(f"  Host:        {config.llm.host}")
        console.print(f"  Port:        {config.llm.port}")
        console.print(f"  Temperature: {config.llm.temperature}")
        if config.llm.api_key:
            masked = f"{config.llm.api_key[:4]}...{config.llm.api_key[-4:]}"
            console.print(f"  API Key:     {masked}")
        else:
            console.print(f"  API Key:     [dim]not set[/dim]")

        console.print("\n[bold cyan]Server Settings:[/bold cyan]")
        console.print(f"  Host:        {config.server.host}")
        console.print(f"  Port:        {config.server.port}")
        console.print(f"  Auto-open:   {config.server.auto_open_browser}")
        console.print(f"  Page Size:   {config.server.page_size}")

        console.print("\n[bold cyan]CLI Settings:[/bold cyan]")
        console.print(f"  Verbose:     {config.cli.verbose}")
        console.print(f"  Color:       {config.cli.color}")
        console.print(f"  Page Size:   {config.cli.page_size}")

        console.print(f"\n[dim]Edit with: ebk config --library-path <path> --llm-host <host> etc.[/dim]")
        console.print(f"[dim]Or edit directly: {config_path}[/dim]\n")
        return

    # Handle setting values
    changes = []

    if set_provider is not None:
        changes.append(f"LLM provider: {set_provider}")
    if set_model is not None:
        changes.append(f"LLM model: {set_model}")
    if set_llm_host is not None:
        changes.append(f"LLM host: {set_llm_host}")
    if set_llm_port is not None:
        changes.append(f"LLM port: {set_llm_port}")
    if set_api_key is not None:
        changes.append("LLM API key: ****")
    if set_temperature is not None:
        changes.append(f"LLM temperature: {set_temperature}")
    if set_server_host is not None:
        changes.append(f"Server host: {set_server_host}")
    if set_server_port is not None:
        changes.append(f"Server port: {set_server_port}")
    if set_auto_open is not None:
        changes.append(f"Server auto-open: {set_auto_open}")
    if set_library_path is not None:
        changes.append(f"Library path: {set_library_path}")
    if set_verbose is not None:
        changes.append(f"CLI verbose: {set_verbose}")
    if set_color is not None:
        changes.append(f"CLI color: {set_color}")

    if changes:
        console.print("[blue]Updating configuration:[/blue]")
        for change in changes:
            console.print(f"  • {change}")

        update_config(
            llm_provider=set_provider,
            llm_model=set_model,
            llm_host=set_llm_host,
            llm_port=set_llm_port,
            llm_api_key=set_api_key,
            llm_temperature=set_temperature,
            server_host=set_server_host,
            server_port=set_server_port,
            server_auto_open=set_auto_open,
            library_default_path=set_library_path,
            cli_verbose=set_verbose,
            cli_color=set_color,
        )
        console.print("[green]✓ Configuration updated![/green]")
        console.print("[dim]Use 'ebk config --show' to view current settings[/dim]")


if __name__ == "__main__":
    app()
