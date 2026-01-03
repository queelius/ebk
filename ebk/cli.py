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


def resolve_library_path(library_path: Optional[Path]) -> Path:
    """
    Resolve library path with config fallback.

    If library_path is None, attempts to use the default from config.
    Validates that the path exists.

    Args:
        library_path: Optional path provided by user

    Returns:
        Resolved Path to library

    Raises:
        typer.Exit: If no path provided and no default configured,
                   or if path doesn't exist
    """
    from .config import load_config

    if library_path is None:
        config = load_config()
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

    return library_path


# Main app
app = typer.Typer()

# Command groups
import_app = typer.Typer(help="Import books from various sources")
export_app = typer.Typer(help="Export library data to various formats")
book_app = typer.Typer(help="Book-specific commands (info, rate, favorite, status, tag)")
note_app = typer.Typer(help="Manage book annotations and notes")
tag_app = typer.Typer(help="Manage hierarchical tags for organizing books")
vfs_app = typer.Typer(help="VFS commands (ln, mv, rm, ls, cat, mkdir)")
queue_app = typer.Typer(help="Manage reading queue")
view_app = typer.Typer(help="Manage views (composable, named subsets of the library)")

# Register command groups
app.add_typer(import_app, name="import")
app.add_typer(export_app, name="export")
app.add_typer(book_app, name="book")
app.add_typer(note_app, name="note")
app.add_typer(tag_app, name="tag")
app.add_typer(vfs_app, name="vfs")
app.add_typer(queue_app, name="queue")
app.add_typer(view_app, name="view")

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
    console.print("  ebk book <subcommand>        Book operations (info, rate, favorite, status, tag)")
    console.print("  ebk export <subcommand>      Export library data")
    console.print("  ebk note <subcommand>        Manage annotations")
    console.print("  ebk tag <subcommand>         Manage hierarchical tags")
    console.print("  ebk view <subcommand>        Manage views (composable library subsets)")
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
def shell(
    library_path: Optional[Path] = typer.Argument(None, help="Path to the library (uses config default if not specified)"),
):
    """
    Launch interactive shell for navigating the library.

    The shell provides a Linux-like interface for browsing and
    managing your library through a virtual filesystem.
    If no library path is specified, uses the default from config.

    Commands:
        cd, pwd, ls    - Navigate the VFS
        cat            - Read file content
        grep, find     - Search and query
        open           - Open files
        !<bash>        - Execute bash commands
        !ebk <cmd>     - Pass through to ebk CLI
        help           - Show help

    Example:
        ebk shell               # Uses config default
        ebk shell ~/my-library
    """
    from .repl import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)
        shell.run()
    except Exception as e:
        from rich.markup import escape
        console.print(f"[red]Error launching shell: {escape(str(e))}[/red]")
        raise typer.Exit(code=1)


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


@app.command()
def migrate(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    check_only: bool = typer.Option(False, "--check", help="Check which migrations are needed without applying"),
    show_version: bool = typer.Option(False, "--version", "-v", help="Show current schema version"),
):
    """
    Run database migrations on an existing library.

    This upgrades the database schema to support new features without losing data.
    Migrations are tracked in a schema_versions table for reliable versioning.

    Examples:
        ebk migrate                    # Migrate default library
        ebk migrate ~/my-library       # Migrate specific library
        ebk migrate --check            # Check pending migrations
        ebk migrate --version          # Show schema version
    """
    from .db.migrations import (
        run_all_migrations, check_migrations, get_engine,
        get_schema_version, CURRENT_SCHEMA_VERSION, get_applied_migrations
    )

    library_path = resolve_library_path(library_path)

    db_path = library_path / 'library.db'
    if not db_path.exists():
        console.print(f"[red]Error: Database not found at {db_path}[/red]")
        console.print("Use 'ebk init' to create a new library.")
        raise typer.Exit(code=1)

    try:
        engine = get_engine(library_path)

        if show_version:
            current = get_schema_version(engine)
            applied = get_applied_migrations(engine)
            console.print(f"[cyan]Schema version:[/cyan] {current} / {CURRENT_SCHEMA_VERSION}")
            if applied:
                console.print(f"[cyan]Applied migrations:[/cyan]")
                for name in sorted(applied):
                    console.print(f"  • {name}")
            return

        if check_only:
            console.print(f"[cyan]Checking migrations for {library_path}...[/cyan]")
            results = check_migrations(library_path)
            current = get_schema_version(engine)

            console.print(f"[dim]Schema version: {current} / {CURRENT_SCHEMA_VERSION}[/dim]")

            if not any(results.values()):
                console.print("[green]✓ Database is up-to-date, no migrations needed[/green]")
            else:
                console.print("[yellow]Migrations needed:[/yellow]")
                for name, needed in results.items():
                    if needed:
                        console.print(f"  • {name}")
        else:
            console.print(f"[cyan]Running migrations on {library_path}...[/cyan]")
            results = run_all_migrations(library_path)

            applied = [name for name, was_applied in results.items() if was_applied]

            if not applied:
                console.print("[green]✓ Database is up-to-date, no migrations applied[/green]")
            else:
                console.print("[green]✓ Migrations completed successfully:[/green]")
                for name in applied:
                    console.print(f"  • {name}")

            current = get_schema_version(engine)
            console.print(f"[dim]Schema version: {current} / {CURRENT_SCHEMA_VERSION}[/dim]")

    except Exception as e:
        console.print(f"[red]Error during migration: {e}[/red]")
        logger.exception("Migration failed")
        raise typer.Exit(code=1)


@app.command()
def backup(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output backup file (.tar.gz or .zip)"),
    include_files: bool = typer.Option(True, "--include-files/--db-only", help="Include book files (or just database)"),
    include_covers: bool = typer.Option(True, "--include-covers/--no-covers", help="Include cover images"),
):
    """
    Create a backup of the library.

    Creates a compressed archive containing the database and optionally
    book files and covers.

    Examples:
        ebk backup -o library-backup.tar.gz
        ebk backup -o backup.zip --db-only           # Database only (small)
        ebk backup ~/my-library -o full-backup.tar.gz
    """
    import tarfile
    import zipfile
    import shutil
    from datetime import datetime

    library_path = resolve_library_path(library_path)

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        db_path = library_path / "library.db"
        files_dir = library_path / "files"
        covers_dir = library_path / "covers"

        if not db_path.exists():
            console.print(f"[red]Error: Database not found: {db_path}[/red]")
            raise typer.Exit(code=1)

        console.print(f"[cyan]Creating backup of {library_path}...[/cyan]")

        # Determine archive type
        output_str = str(output).lower()
        is_tar = output_str.endswith('.tar.gz') or output_str.endswith('.tgz')
        is_zip = output_str.endswith('.zip')

        if not is_tar and not is_zip:
            console.print("[red]Error: Output must be .tar.gz, .tgz, or .zip[/red]")
            raise typer.Exit(code=1)

        file_count = 0
        total_size = 0

        if is_tar:
            with tarfile.open(output, "w:gz") as tar:
                # Always include database
                console.print("  Adding database...")
                tar.add(db_path, arcname="library.db")
                total_size += db_path.stat().st_size
                file_count += 1

                # Include files if requested
                if include_files and files_dir.exists():
                    console.print("  Adding book files...")
                    for f in files_dir.rglob("*"):
                        if f.is_file():
                            tar.add(f, arcname=f"files/{f.relative_to(files_dir)}")
                            total_size += f.stat().st_size
                            file_count += 1

                # Include covers if requested
                if include_covers and covers_dir.exists():
                    console.print("  Adding covers...")
                    for f in covers_dir.rglob("*"):
                        if f.is_file():
                            tar.add(f, arcname=f"covers/{f.relative_to(covers_dir)}")
                            total_size += f.stat().st_size
                            file_count += 1
        else:
            with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Always include database
                console.print("  Adding database...")
                zf.write(db_path, "library.db")
                total_size += db_path.stat().st_size
                file_count += 1

                # Include files if requested
                if include_files and files_dir.exists():
                    console.print("  Adding book files...")
                    for f in files_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"files/{f.relative_to(files_dir)}")
                            total_size += f.stat().st_size
                            file_count += 1

                # Include covers if requested
                if include_covers and covers_dir.exists():
                    console.print("  Adding covers...")
                    for f in covers_dir.rglob("*"):
                        if f.is_file():
                            zf.write(f, f"covers/{f.relative_to(covers_dir)}")
                            total_size += f.stat().st_size
                            file_count += 1

        backup_size = output.stat().st_size

        console.print(f"\n[green]✓ Backup created: {output}[/green]")
        console.print(f"  Files: {file_count}")
        console.print(f"  Original size: {total_size / 1024 / 1024:.1f} MB")
        console.print(f"  Backup size: {backup_size / 1024 / 1024:.1f} MB")

    except Exception as e:
        console.print(f"[red]Error creating backup: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def restore(
    backup_file: Path = typer.Argument(..., help="Backup file to restore (.tar.gz or .zip)"),
    library_path: Path = typer.Argument(..., help="Target library path (will be created)"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing library"),
):
    """
    Restore a library from backup.

    Extracts a backup archive to create or restore a library.

    Examples:
        ebk restore backup.tar.gz ~/restored-library
        ebk restore backup.zip ~/my-library --force   # Overwrite existing
    """
    import tarfile
    import zipfile
    import shutil

    if not backup_file.exists():
        console.print(f"[red]Error: Backup file not found: {backup_file}[/red]")
        raise typer.Exit(code=1)

    if library_path.exists():
        if not force:
            console.print(f"[red]Error: Library path exists: {library_path}[/red]")
            console.print("[yellow]Use --force to overwrite[/yellow]")
            raise typer.Exit(code=1)
        else:
            console.print(f"[yellow]Removing existing library...[/yellow]")
            shutil.rmtree(library_path)

    try:
        library_path.mkdir(parents=True, exist_ok=True)

        backup_str = str(backup_file).lower()
        is_tar = backup_str.endswith('.tar.gz') or backup_str.endswith('.tgz')

        console.print(f"[cyan]Restoring from {backup_file}...[/cyan]")

        if is_tar:
            with tarfile.open(backup_file, "r:gz") as tar:
                tar.extractall(library_path)
        else:
            with zipfile.ZipFile(backup_file, 'r') as zf:
                zf.extractall(library_path)

        # Verify database exists
        db_path = library_path / "library.db"
        if not db_path.exists():
            console.print(f"[red]Error: Backup does not contain library.db[/red]")
            raise typer.Exit(code=1)

        console.print(f"\n[green]✓ Library restored to: {library_path}[/green]")

        # Show stats
        from .library_db import Library
        lib = Library.open(library_path)
        book_count = lib.query().count()
        lib.close()
        console.print(f"  Books: {book_count}")

    except Exception as e:
        console.print(f"[red]Error restoring backup: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def check(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    fix: bool = typer.Option(False, "--fix", help="Attempt to fix issues (remove orphan DB entries)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show all files, not just issues"),
):
    """
    Check library integrity and report issues.

    Checks for:
    - Missing files: Database entries pointing to non-existent files
    - Orphan files: Files on disk not tracked in database
    - Books without files: Book entries with no associated files
    - Hash mismatches: Files whose content doesn't match stored hash

    Examples:
        ebk check                    # Check default library
        ebk check ~/my-library       # Check specific library
        ebk check --fix              # Remove orphan DB entries
        ebk check --verbose          # Show all checked files
    """
    from .library_db import Library
    import hashlib
    import os

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        files_dir = library_path / "files"

        issues = {
            "missing_files": [],
            "orphan_files": [],
            "books_without_files": [],
            "hash_mismatches": [],
        }

        console.print(f"[cyan]Checking library integrity: {library_path}[/cyan]\n")

        # Get all files from database
        from .db.models import File, Book
        db_files = lib.session.query(File).all()
        db_file_paths = {f.path for f in db_files}

        # Check for missing files
        console.print("[bold]Checking for missing files...[/bold]")
        for f in db_files:
            file_path = library_path / f.path
            if not file_path.exists():
                issues["missing_files"].append({
                    "id": f.id,
                    "path": f.path,
                    "book_id": f.book_id,
                })
                console.print(f"  [red]✗ Missing: {f.path}[/red]")
            elif verbose:
                console.print(f"  [green]✓ {f.path}[/green]")

        # Check for orphan files on disk
        console.print("\n[bold]Checking for orphan files...[/bold]")
        if files_dir.exists():
            for root, dirs, files in os.walk(files_dir):
                for filename in files:
                    full_path = Path(root) / filename
                    rel_path = str(full_path.relative_to(library_path))

                    if rel_path not in db_file_paths:
                        issues["orphan_files"].append(rel_path)
                        console.print(f"  [yellow]? Orphan: {rel_path}[/yellow]")
                    elif verbose:
                        console.print(f"  [green]✓ {rel_path}[/green]")

        # Check for books without files
        console.print("\n[bold]Checking for books without files...[/bold]")
        books_without_files = lib.session.query(Book).filter(
            ~Book.files.any()
        ).all()

        for book in books_without_files:
            issues["books_without_files"].append({
                "id": book.id,
                "title": book.title,
            })
            console.print(f"  [yellow]? Book #{book.id}: {book.title[:50]}[/yellow]")

        # Summary
        console.print("\n[bold]Summary:[/bold]")
        total_issues = sum(len(v) for v in issues.values())

        if total_issues == 0:
            console.print("[green]✓ No issues found![/green]")
        else:
            console.print(f"[yellow]Found {total_issues} issue(s):[/yellow]")
            if issues["missing_files"]:
                console.print(f"  • Missing files: {len(issues['missing_files'])}")
            if issues["orphan_files"]:
                console.print(f"  • Orphan files: {len(issues['orphan_files'])}")
            if issues["books_without_files"]:
                console.print(f"  • Books without files: {len(issues['books_without_files'])}")
            if issues["hash_mismatches"]:
                console.print(f"  • Hash mismatches: {len(issues['hash_mismatches'])}")

        # Fix issues if requested
        if fix and issues["missing_files"]:
            console.print("\n[cyan]Fixing missing file entries...[/cyan]")
            for item in issues["missing_files"]:
                file_obj = lib.session.get(File, item["id"])
                if file_obj:
                    lib.session.delete(file_obj)
                    console.print(f"  [dim]Removed DB entry for: {item['path']}[/dim]")
            lib.session.commit()
            console.print("[green]✓ Fixed missing file entries[/green]")

        lib.close()

        # Exit with error code if issues found
        if total_issues > 0 and not fix:
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[red]Error checking library: {e}[/red]")
        raise typer.Exit(code=1)


@import_app.command(name="add")
def import_add(
    file_path: Path = typer.Argument(..., help="Path to ebook file"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Book title"),
    authors: Optional[str] = typer.Option(None, "--authors", "-a", help="Authors (comma-separated)"),
    subjects: Optional[str] = typer.Option(None, "--subjects", "-s", help="Subjects/tags (comma-separated)"),
    language: str = typer.Option("en", "--language", "-l", help="Language code"),
    no_text: bool = typer.Option(False, "--no-text", help="Skip text extraction"),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover extraction"),
    auto_metadata: bool = typer.Option(True, "--auto-metadata/--no-auto-metadata", help="Extract metadata from file")
):
    """
    Import a single ebook file into the library.

    Extracts metadata, text, and cover images automatically unless disabled.
    Supports PDF, EPUB, MOBI, and plaintext files.
    If no library path is specified, uses the default from config.

    Examples:
        ebk import add book.pdf                    # Uses config default
        ebk import add book.pdf ~/my-library
        ebk import add book.epub --title "My Book" --authors "Author Name"
    """
    from .library_db import Library
    from .extract_metadata import extract_metadata

    if not file_path.exists():
        console.print(f"[red]Error: File not found: {file_path}[/red]")
        raise typer.Exit(code=1)

    library_path = resolve_library_path(library_path)

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


@import_app.command(name="calibre")
def import_calibre(
    calibre_path: Path = typer.Argument(..., help="Path to Calibre library"),
    library_path: Path = typer.Argument(..., help="Path to ebk library"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of books to import")
):
    """
    Import books from a Calibre library.

    Reads Calibre's metadata.opf files and imports ebooks with full metadata.
    Supports all Calibre-managed formats (PDF, EPUB, MOBI, etc.).

    Examples:
        ebk import calibre ~/Calibre/Library ~/my-library
        ebk import calibre ~/Calibre/Library ~/my-library --limit 100
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


@import_app.command(name="folder")
def import_folder(
    folder_path: Path = typer.Argument(..., help="Path to folder containing ebooks"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to ebk library (uses config default if not specified)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r", help="Search subdirectories recursively"),
    extensions: Optional[str] = typer.Option("pdf,epub,mobi,azw3,txt", "--extensions", "-e", help="File extensions to import (comma-separated)"),
    limit: Optional[int] = typer.Option(None, "--limit", help="Limit number of books to import"),
    no_text: bool = typer.Option(False, "--no-text", help="Skip text extraction"),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover extraction"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported without importing"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Skip files already in library (by hash)"),
    log_failures: Optional[Path] = typer.Option(None, "--log-failures", help="Log failed imports to file for retry"),
):
    """
    Import all ebook files from a folder (batch import).

    Scans a directory for ebook files and imports them with automatic
    metadata extraction. Useful for importing large collections.

    Features:
    - Progress bar with ETA
    - Automatic resume (skips files already imported by hash)
    - Failure logging for later retry

    Examples:
        ebk import folder ~/Downloads/Books ~/my-library
        ebk import folder ~/Books ~/my-library --no-recursive
        ebk import folder ~/Books ~/my-library --extensions pdf,epub --limit 100
        ebk import folder ~/Books ~/my-library --dry-run      # Preview only
        ebk import folder ~/Books ~/my-library --log-failures failed.txt
    """
    from .library_db import Library
    from .extract_metadata import extract_metadata
    import hashlib
    import time

    if not folder_path.exists():
        console.print(f"[red]Error: Folder not found: {folder_path}[/red]")
        raise typer.Exit(code=1)

    if not folder_path.is_dir():
        console.print(f"[red]Error: Not a directory: {folder_path}[/red]")
        raise typer.Exit(code=1)

    library_path = resolve_library_path(library_path)

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        console.print(f"[yellow]Initialize a library first with: ebk init {library_path}[/yellow]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Parse extensions
        ext_list = [f".{ext.strip().lower()}" for ext in extensions.split(",")]

        # Find all ebook files
        console.print(f"[cyan]Scanning folder for ebooks...[/cyan]")
        ebook_files = []

        if recursive:
            for ext in ext_list:
                ebook_files.extend(folder_path.rglob(f"*{ext}"))
        else:
            for ext in ext_list:
                ebook_files.extend(folder_path.glob(f"*{ext}"))

        # Remove duplicates and sort
        ebook_files = sorted(set(ebook_files))

        if limit:
            ebook_files = ebook_files[:limit]

        console.print(f"Found {len(ebook_files)} ebook files")

        if len(ebook_files) == 0:
            console.print("[yellow]No ebook files found.[/yellow]")
            lib.close()
            raise typer.Exit(code=0)

        # Get existing hashes for resume capability
        existing_hashes = set()
        if resume:
            from .db.models import File
            existing_hashes = {f.file_hash for f in lib.session.query(File.file_hash).all() if f.file_hash}
            if existing_hashes:
                console.print(f"[dim]Resume mode: {len(existing_hashes)} files already in library[/dim]")

        # Dry run mode
        if dry_run:
            console.print("\n[yellow]Dry run mode - no files will be imported[/yellow]\n")
            for fp in ebook_files[:20]:  # Show first 20
                console.print(f"  • {fp.name}")
            if len(ebook_files) > 20:
                console.print(f"  ... and {len(ebook_files) - 20} more")
            lib.close()
            return

        imported = 0
        failed = 0
        skipped = 0
        failed_files = []
        start_time = time.time()

        with Progress(
            "[progress.description]{task.description}",
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            "[progress.completed]{task.completed}/{task.total}",
            "•",
            "ETA: [cyan]{task.fields[eta]}[/cyan]",
        ) as progress:
            task = progress.add_task("[cyan]Importing...", total=len(ebook_files), eta="calculating...")

            for idx, file_path in enumerate(ebook_files):
                # Calculate ETA
                elapsed = time.time() - start_time
                if idx > 0:
                    per_file = elapsed / idx
                    remaining = (len(ebook_files) - idx) * per_file
                    eta = f"{int(remaining // 60)}m {int(remaining % 60)}s"
                else:
                    eta = "calculating..."

                progress.update(task, description=f"[cyan]{file_path.name[:40]}", eta=eta)

                try:
                    # Check if already imported (by hash) for resume
                    if resume and existing_hashes:
                        file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
                        if file_hash in existing_hashes:
                            skipped += 1
                            progress.advance(task)
                            continue

                    # Extract metadata
                    metadata = extract_metadata(str(file_path))

                    # Ensure title exists
                    if 'title' not in metadata or not metadata['title']:
                        metadata['title'] = file_path.stem

                    # Import book
                    book = lib.add_book(
                        file_path,
                        metadata,
                        extract_text=not no_text,
                        extract_cover=not no_cover
                    )

                    if book:
                        imported += 1
                    else:
                        skipped += 1  # Already exists

                except Exception as e:
                    failed += 1
                    failed_files.append((str(file_path), str(e)))
                    logger.debug(f"Failed to import {file_path}: {e}")

                progress.advance(task)

        elapsed = time.time() - start_time

        # Summary
        console.print(f"\n[bold]Import Summary:[/bold]")
        console.print(f"  ✓ Imported: [green]{imported}[/green]")
        console.print(f"  ○ Skipped (duplicates): [dim]{skipped}[/dim]")
        if failed > 0:
            console.print(f"  ✗ Failed: [red]{failed}[/red]")
        console.print(f"  Time: {int(elapsed // 60)}m {int(elapsed % 60)}s")

        # Log failures to file if requested
        if log_failures and failed_files:
            with open(log_failures, 'w') as f:
                for path, error in failed_files:
                    f.write(f"{path}\t{error}\n")
            console.print(f"\n[dim]Failed imports logged to: {log_failures}[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error importing folder: {e}[/red]")
        logger.exception("Folder import error details:")
        raise typer.Exit(code=1)


@import_app.command(name="url")
def import_url(
    url: str = typer.Argument(..., help="URL to download ebook from"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    no_text: bool = typer.Option(False, "--no-text", help="Skip text extraction"),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover extraction")
):
    """
    Import an ebook from a URL.

    Downloads the ebook file from the given URL and imports it into the library.
    Supports PDF, EPUB, MOBI, and other common ebook formats.

    Examples:
        ebk import url https://example.com/book.epub
        ebk import url https://example.com/book.pdf ~/my-library
    """
    import httpx
    import re
    import tempfile
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    if not url.startswith(('http://', 'https://')):
        console.print("[red]Error: Invalid URL. Must start with http:// or https://[/red]")
        raise typer.Exit(code=1)

    supported_extensions = {'.pdf', '.epub', '.mobi', '.azw', '.azw3', '.txt'}

    try:
        lib = Library.open(library_path)

        console.print(f"Downloading from: {url}")

        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(url)
            response.raise_for_status()

            # Try to determine filename
            filename = None
            content_disposition = response.headers.get('content-disposition', '')
            if 'filename=' in content_disposition:
                match = re.search(r'filename[*]?=["\']?([^"\';]+)', content_disposition)
                if match:
                    filename = match.group(1)

            if not filename:
                from urllib.parse import urlparse, unquote
                parsed = urlparse(url)
                filename = unquote(parsed.path.split('/')[-1])

            if not filename:
                filename = 'downloaded_book'

            # Check extension
            ext = Path(filename).suffix.lower()
            if ext not in supported_extensions:
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type:
                    ext = '.pdf'
                elif 'epub' in content_type:
                    ext = '.epub'
                else:
                    console.print(f"[red]Error: Unsupported file type. Supported: {', '.join(supported_extensions)}[/red]")
                    lib.close()
                    raise typer.Exit(code=1)
                filename = Path(filename).stem + ext

            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(response.content)
                tmp_path = Path(tmp.name)

        console.print(f"Downloaded: {filename} ({len(response.content) / 1024:.1f} KB)")

        # Extract metadata and import
        metadata = extract_metadata(str(tmp_path))
        if 'title' not in metadata or not metadata['title']:
            metadata['title'] = Path(filename).stem

        book = lib.add_book(
            tmp_path,
            metadata=metadata,
            extract_text=not no_text,
            extract_cover=not no_cover
        )

        # Clean up temp file
        tmp_path.unlink()

        if book:
            console.print(f"[green]✓ Imported: {book.title}[/green]")
            console.print(f"  ID: {book.id}")
            console.print(f"  Authors: {', '.join(a.name for a in book.authors)}")
        else:
            console.print("[yellow]Import failed or book already exists[/yellow]")

        lib.close()

    except httpx.HTTPError as e:
        console.print(f"[red]Error downloading file: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error importing from URL: {e}[/red]")
        logger.exception("URL import error details:")
        raise typer.Exit(code=1)


@import_app.command(name="opds")
def import_opds(
    opds_url: str = typer.Argument(..., help="OPDS catalog URL"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Limit number of books to import"),
    no_text: bool = typer.Option(False, "--no-text", help="Skip text extraction"),
    no_cover: bool = typer.Option(False, "--no-cover", help="Skip cover extraction")
):
    """
    Import books from an OPDS catalog feed.

    OPDS (Open Publication Distribution System) is a standard format used by
    many digital libraries and ebook servers for distributing ebooks.

    Examples:
        ebk import opds https://example.com/opds/catalog.xml
        ebk import opds https://library.example.com/opds --limit 50
    """
    import httpx
    import xml.etree.ElementTree as ET
    import tempfile
    from urllib.parse import urljoin
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    if not opds_url.startswith(('http://', 'https://')):
        console.print("[red]Error: Invalid URL. Must start with http:// or https://[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        console.print(f"Fetching OPDS catalog: {opds_url}")

        with httpx.Client(follow_redirects=True, timeout=30.0) as client:
            response = client.get(opds_url)
            response.raise_for_status()

            # Parse OPDS (Atom) feed
            root = ET.fromstring(response.content)

            # OPDS uses Atom namespace
            ns = {
                'atom': 'http://www.w3.org/2005/Atom',
                'opds': 'http://opds-spec.org/2010/catalog',
                'dc': 'http://purl.org/dc/elements/1.1/'
            }

            entries = root.findall('.//atom:entry', ns)
            if not entries:
                entries = root.findall('.//entry')

            if limit:
                entries = entries[:limit]

            console.print(f"Found {len(entries)} entries in catalog")

            if len(entries) == 0:
                console.print("[yellow]No entries found in OPDS catalog.[/yellow]")
                lib.close()
                raise typer.Exit(code=0)

            imported = 0
            failed = 0
            skipped = 0

            with Progress() as progress:
                task = progress.add_task("[cyan]Importing from OPDS...", total=len(entries))

                for entry in entries:
                    title_el = entry.find('atom:title', ns) or entry.find('title')
                    title = title_el.text if title_el is not None else 'Unknown'
                    progress.update(task, description=f"[cyan]Importing: {title[:40]}...")

                    try:
                        # Find acquisition link
                        acquisition_link = None
                        for link in entry.findall('atom:link', ns) or entry.findall('link'):
                            rel = link.get('rel', '')
                            href = link.get('href', '')
                            link_type = link.get('type', '')

                            if 'acquisition' in rel and href:
                                if 'epub' in link_type:
                                    acquisition_link = href
                                    break
                                elif 'pdf' in link_type and not acquisition_link:
                                    acquisition_link = href

                        if not acquisition_link:
                            skipped += 1
                            progress.advance(task)
                            continue

                        # Make URL absolute
                        if not acquisition_link.startswith(('http://', 'https://')):
                            acquisition_link = urljoin(opds_url, acquisition_link)

                        # Download file
                        file_response = client.get(acquisition_link, timeout=60.0)
                        file_response.raise_for_status()

                        # Determine extension
                        content_type = file_response.headers.get('content-type', '')
                        if 'epub' in content_type:
                            ext = '.epub'
                        elif 'pdf' in content_type:
                            ext = '.pdf'
                        elif 'mobi' in content_type:
                            ext = '.mobi'
                        else:
                            ext = '.epub'

                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                            tmp.write(file_response.content)
                            tmp_path = Path(tmp.name)

                        metadata = extract_metadata(str(tmp_path))
                        if 'title' not in metadata or not metadata['title']:
                            metadata['title'] = title

                        book = lib.add_book(
                            tmp_path,
                            metadata=metadata,
                            extract_text=not no_text,
                            extract_cover=not no_cover
                        )

                        tmp_path.unlink()

                        if book:
                            imported += 1
                        else:
                            skipped += 1

                    except Exception as e:
                        failed += 1
                        logger.debug(f"Failed to import {title}: {e}")

                    progress.advance(task)

            # Summary
            console.print(f"\n[bold]OPDS Import Summary:[/bold]")
            console.print(f"  Imported: {imported}")
            console.print(f"  Skipped (no download link or duplicate): {skipped}")
            if failed > 0:
                console.print(f"  Failed: {failed}")

        lib.close()

    except httpx.HTTPError as e:
        console.print(f"[red]Error fetching OPDS feed: {e}[/red]")
        raise typer.Exit(code=1)
    except ET.ParseError as e:
        console.print(f"[red]Error parsing OPDS feed: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error importing from OPDS: {e}[/red]")
        logger.exception("OPDS import error details:")
        raise typer.Exit(code=1)


@import_app.command(name="isbn")
def import_isbn(
    isbn: str = typer.Argument(..., help="ISBN-10 or ISBN-13"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)")
):
    """
    Create a book entry by ISBN lookup.

    Fetches book metadata from Google Books and Open Library APIs.
    Creates a metadata-only entry without an actual ebook file.

    Examples:
        ebk import isbn 978-0-13-468599-1
        ebk import isbn 0134685997 ~/my-library
    """
    import httpx
    import re
    from .library_db import Library
    from .db.models import Book, Author, Subject, Identifier
    from .services.import_service import get_sort_name

    library_path = resolve_library_path(library_path)

    # Clean ISBN
    clean_isbn = re.sub(r'[^0-9X]', '', isbn.upper())

    if len(clean_isbn) not in (10, 13):
        console.print("[red]Error: Invalid ISBN. Must be 10 or 13 digits.[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        console.print(f"Looking up ISBN: {clean_isbn}")

        metadata = None

        with httpx.Client(timeout=15.0) as client:
            # Try Google Books API first
            google_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}"
            response = client.get(google_url)

            if response.status_code == 200:
                data = response.json()
                if data.get('totalItems', 0) > 0:
                    volume = data['items'][0]['volumeInfo']
                    metadata = {
                        'title': volume.get('title', 'Unknown'),
                        'subtitle': volume.get('subtitle'),
                        'authors': volume.get('authors', []),
                        'publisher': volume.get('publisher'),
                        'publication_date': volume.get('publishedDate'),
                        'description': volume.get('description'),
                        'page_count': volume.get('pageCount'),
                        'language': volume.get('language'),
                        'subjects': volume.get('categories', []),
                    }
                    console.print("[dim]Found in Google Books[/dim]")

            # Fallback to Open Library
            if not metadata:
                ol_url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
                response = client.get(ol_url)

                if response.status_code == 200:
                    data = response.json()
                    key = f"ISBN:{clean_isbn}"
                    if key in data:
                        book_data = data[key]
                        metadata = {
                            'title': book_data.get('title', 'Unknown'),
                            'subtitle': book_data.get('subtitle'),
                            'authors': [a.get('name') for a in book_data.get('authors', [])],
                            'publisher': book_data.get('publishers', [{}])[0].get('name') if book_data.get('publishers') else None,
                            'publication_date': book_data.get('publish_date'),
                            'page_count': book_data.get('number_of_pages'),
                            'subjects': [s.get('name') for s in book_data.get('subjects', [])],
                        }
                        console.print("[dim]Found in Open Library[/dim]")

        if not metadata:
            console.print(f"[red]Error: No book found for ISBN: {clean_isbn}[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Create book entry
        book = Book(
            title=metadata['title'],
            subtitle=metadata.get('subtitle'),
            publisher=metadata.get('publisher'),
            publication_date=metadata.get('publication_date'),
            description=metadata.get('description'),
            page_count=metadata.get('page_count'),
            language=metadata.get('language'),
        )

        # Add authors
        for author_name in metadata.get('authors', []):
            if author_name:
                author = lib.session.query(Author).filter_by(name=author_name).first()
                if not author:
                    author = Author(name=author_name, sort_name=get_sort_name(author_name))
                    lib.session.add(author)
                book.authors.append(author)

        # Add subjects
        for subject_name in metadata.get('subjects', []):
            if subject_name:
                subject = lib.session.query(Subject).filter_by(name=subject_name).first()
                if not subject:
                    subject = Subject(name=subject_name)
                    lib.session.add(subject)
                book.subjects.append(subject)

        # Add ISBN identifier
        identifier = Identifier(scheme='isbn', value=clean_isbn)
        book.identifiers.append(identifier)

        lib.session.add(book)
        lib.session.commit()

        console.print(f"[green]✓ Created: {book.title}[/green]")
        console.print(f"  ID: {book.id}")
        if book.authors:
            console.print(f"  Authors: {', '.join(a.name for a in book.authors)}")
        if book.publisher:
            console.print(f"  Publisher: {book.publisher}")
        if book.subjects:
            console.print(f"  Subjects: {', '.join(s.name for s in book.subjects[:5])}")
        console.print(f"  [dim]Note: This is a metadata-only entry (no file attached)[/dim]")

        lib.close()

    except httpx.HTTPError as e:
        console.print(f"[red]Error looking up ISBN: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error importing from ISBN: {e}[/red]")
        logger.exception("ISBN import error details:")
        raise typer.Exit(code=1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of results"),
    offset: int = typer.Option(0, "--offset", help="Skip first N results (for pagination)")
):
    """
    Search books in database-backed library using full-text search.

    Searches across titles, descriptions, and extracted text content using
    SQLite's FTS5 engine for fast, relevance-ranked results.
    If no library path is specified, uses the default from config.

    Examples:
        ebk search "python programming"                  # Uses config default
        ebk search "python programming" ~/my-library
        ebk search "machine learning" --limit 50
        ebk search "python" --offset 20 --limit 20       # Page 2
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)

        results = lib.search(query, limit=limit, offset=offset)

        if not results:
            if offset > 0:
                console.print(f"[yellow]No more results for: {query}[/yellow]")
            else:
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

            # Display pagination info
            start = offset + 1
            end = offset + len(results)
            if len(results) < limit:
                # We got fewer than requested, so we know the total
                total = offset + len(results)
                console.print(f"\n[dim]Showing {start}-{end} of {total} results[/dim]")
            else:
                # More results may exist
                console.print(f"\n[dim]Showing {start}-{end} (more results may exist, use --offset {end} for next page)[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error searching library: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def stats(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)")
):
    """
    Show statistics for database-backed library.

    Displays book counts, author counts, language distribution,
    format distribution, and reading progress.
    If no library path is specified, uses the default from config.

    Example:
        ebk stats                # Uses config default
        ebk stats ~/my-library
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

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


@app.command()
def sql(
    query: str = typer.Argument(..., help="SQL query to execute (SELECT only)"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json, csv"),
    limit: Optional[int] = typer.Option(None, "--limit", "-n", help="Limit number of rows (overrides LIMIT in query)"),
):
    """
    Execute raw SQL queries against the library database.

    Only SELECT queries are allowed for safety. This is a power-user feature
    for advanced filtering, aggregations, and custom reports.

    Available tables: books, authors, subjects, files, covers, tags,
    personal_metadata, annotations, books_fts (full-text search)

    Examples:
        ebk sql "SELECT title, language FROM books WHERE language = 'en'"
        ebk sql "SELECT COUNT(*) as count FROM books" --format json
        ebk sql "SELECT a.name, COUNT(*) as books FROM authors a JOIN book_authors ba ON a.id = ba.author_id GROUP BY a.name ORDER BY books DESC" --limit 10
        ebk sql "SELECT * FROM books_fts WHERE books_fts MATCH 'python'" --format csv
    """
    import io
    import sqlite3

    library_path = resolve_library_path(library_path)
    db_path = library_path / 'library.db'

    if not db_path.exists():
        console.print(f"[red]Error: Database not found at {db_path}[/red]")
        raise typer.Exit(code=1)

    # Security check: only allow SELECT queries
    query_stripped = query.strip().upper()
    if not query_stripped.startswith('SELECT'):
        console.print("[red]Error: Only SELECT queries are allowed[/red]")
        console.print("[yellow]Use other ebk commands to modify data[/yellow]")
        raise typer.Exit(code=1)

    # Check for potentially dangerous operations even in SELECT context
    dangerous_patterns = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'ATTACH', 'DETACH']
    for pattern in dangerous_patterns:
        if pattern in query_stripped:
            console.print(f"[red]Error: Query contains disallowed keyword: {pattern}[/red]")
            raise typer.Exit(code=1)

    # Apply limit if specified
    if limit is not None and 'LIMIT' not in query_stripped:
        query = f"{query.rstrip(';')} LIMIT {limit}"

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            console.print("[yellow]No results[/yellow]")
            conn.close()
            return

        # Get column names
        columns = [description[0] for description in cursor.description]

        if format == "json":
            # JSON output
            result = [dict(zip(columns, row)) for row in rows]
            console.print(json.dumps(result, indent=2, default=str))

        elif format == "csv":
            # CSV output
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)
            for row in rows:
                writer.writerow(row)
            console.print(output.getvalue())

        else:  # table format (default)
            table = Table(show_header=True, header_style="bold cyan")
            for col in columns:
                table.add_column(col)

            for row in rows:
                table.add_row(*[str(v) if v is not None else "" for v in row])

            console.print(table)

        console.print(f"\n[dim]{len(rows)} row(s) returned[/dim]")
        conn.close()

    except sqlite3.Error as e:
        console.print(f"[red]SQL Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error executing query: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="list")
def list_books(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    limit: int = typer.Option(50, "--limit", "-n", help="Maximum number of books to show"),
    offset: int = typer.Option(0, "--offset", help="Starting offset"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Filter by author"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language"),
    favorite: Optional[bool] = typer.Option(None, "--favorite", "-f", help="Filter by favorite status"),
    reading_status: Optional[str] = typer.Option(None, "--status", "-S", help="Filter by reading status (reading, completed, unread)"),
    view_name: Optional[str] = typer.Option(None, "--view", "-v", help="List books from a named view"),
):
    """
    List books in database-backed library with optional filtering.

    Supports pagination and filtering by author, subject, language,
    favorite status, and reading status. Can also list books from a view.
    If no library path is specified, uses the default from config.

    Examples:
        ebk list                           # Uses config default
        ebk list ~/my-library
        ebk list --author "Knuth"
        ebk list --subject "Python" --limit 20
        ebk list --favorite                # List favorites
        ebk list --status reading          # Currently reading
        ebk list --status completed        # Completed books
        ebk list --view favorites          # List from a view
        ebk list --view "programming"      # List from custom view
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)

        # If view specified, use view service
        if view_name:
            from .views.service import ViewService
            view_svc = ViewService(lib.session)

            try:
                transformed = view_svc.evaluate(view_name)
                books = [tb.book for tb in transformed]
                total = len(books)

                # Apply pagination manually
                books = books[offset:offset + limit]

            except ValueError as e:
                console.print(f"[red]Error: {e}[/red]")
                lib.close()
                raise typer.Exit(code=1)
        else:
            # Build query with filters
            query = lib.query()

            if author:
                query = query.filter_by_author(author)
            if subject:
                query = query.filter_by_subject(subject)
            if language:
                query = query.filter_by_language(language)
            if favorite is not None:
                query = query.filter_by_favorite(favorite)
            if reading_status:
                # Map 'completed' to 'read' for DB compatibility
                status = 'read' if reading_status == 'completed' else reading_status
                query = query.filter_by_reading_status(status)

            # Get total count before applying limit/offset
            total = query.count()

            query = query.order_by('title').limit(limit).offset(offset)
            books = query.all()

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

            # Display pagination info
            start = offset + 1
            end = offset + len(books)
            console.print(f"\n[dim]Showing {start}-{end} of {total} books[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error listing books: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Book Commands - Book-specific operations
# ============================================================================

@book_app.command(name="info")
def book_info(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
):
    """
    Show detailed information about a book.

    Examples:
        ebk book info 42
        ebk book info 42 --format json
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        if format == "json":
            data = {
                "id": book.id,
                "title": book.title,
                "authors": [a.name for a in book.authors],
                "subjects": [s.name for s in book.subjects],
                "language": book.language,
                "publisher": book.publisher,
                "publication_date": book.publication_date,
                "series": book.series,
                "series_index": book.series_index,
                "description": book.description,
                "files": [{"format": f.format, "size": f.size_bytes, "path": f.path} for f in book.files],
                "tags": [t.path for t in book.tags],
            }
            if book.personal:
                pm = book.personal
                data["personal"] = {
                    "rating": pm.rating,
                    "favorite": pm.favorite,
                    "reading_status": pm.reading_status,
                    "progress": pm.reading_progress,
                    "personal_tags": pm.personal_tags,
                }
            console.print(json.dumps(data, indent=2, default=str))
        else:
            table = Table(title=f"Book #{book.id}", show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value")

            table.add_row("Title", book.title)
            table.add_row("Authors", ", ".join(a.name for a in book.authors))
            table.add_row("Language", book.language or "")
            table.add_row("Subjects", ", ".join(s.name for s in book.subjects))
            table.add_row("Publisher", book.publisher or "")
            table.add_row("Published", book.publication_date or "")
            if book.series:
                series_info = book.series
                if book.series_index:
                    series_info += f" #{book.series_index}"
                table.add_row("Series", series_info)
            table.add_row("Tags", ", ".join(t.path for t in book.tags))

            if book.files:
                files_str = ", ".join(f"{f.format} ({f.size_bytes or 0:,} bytes)" for f in book.files)
                table.add_row("Files", files_str)

            if book.personal:
                pm = book.personal
                table.add_row("Rating", f"{pm.rating}/5" if pm.rating else "Not rated")
                table.add_row("Favorite", "Yes" if pm.favorite else "No")
                table.add_row("Status", pm.reading_status or "unread")
                if pm.reading_progress:
                    table.add_row("Progress", f"{pm.reading_progress}%")

            console.print(table)

            if book.description:
                console.print("\n[bold]Description:[/bold]")
                desc = book.description[:500] + ("..." if len(book.description) > 500 else "")
                console.print(desc)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error getting book info: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="status")
def book_status(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    status: Optional[str] = typer.Option(None, "--set", "-s", help="Set reading status: unread, reading, completed"),
):
    """
    Get or set the reading status of a book.

    Examples:
        ebk book status 42                    # Show current status
        ebk book status 42 --set reading      # Mark as currently reading
        ebk book status 42 --set completed    # Mark as completed
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    valid_statuses = ["unread", "reading", "completed"]

    if status and status not in valid_statuses:
        console.print(f"[red]Error: Invalid status. Must be one of: {', '.join(valid_statuses)}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        if status:
            lib.update_reading_status(book_id, status)
            console.print(f"[green]✓ Set status of '{book.title}' to: {status}[/green]")
        else:
            current = book.personal.reading_status if book.personal else "unread"
            console.print(f"[cyan]{book.title}[/cyan]: {current}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error updating status: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="progress")
def book_progress(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    progress: Optional[int] = typer.Option(None, "--set", "-s", help="Set progress percentage (0-100)"),
):
    """
    Get or set the reading progress of a book.

    Examples:
        ebk book progress 42                # Show current progress
        ebk book progress 42 --set 50       # Set to 50%
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    if progress is not None and not (0 <= progress <= 100):
        console.print(f"[red]Error: Progress must be between 0 and 100[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        if progress is not None:
            # Use update_reading_status with progress parameter (keeps current status)
            current_status = book.personal.reading_status if book.personal else "reading"
            lib.update_reading_status(book_id, current_status, progress=progress)
            console.print(f"[green]✓ Set progress of '{book.title}' to: {progress}%[/green]")
        else:
            current = book.personal.reading_progress if book.personal and book.personal.reading_progress else 0
            console.print(f"[cyan]{book.title}[/cyan]: {current}%")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error updating progress: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="open")
def book_open(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Preferred format (pdf, epub, etc.)"),
):
    """
    Open a book file in the default application.

    Examples:
        ebk book open 42                # Open first available file
        ebk book open 42 --format pdf   # Open PDF version
    """
    import subprocess
    import platform
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        if not book.files:
            console.print(f"[yellow]Book has no files attached[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        # Find the file to open
        file_to_open = None
        if format:
            for f in book.files:
                if f.format and f.format.lower() == format.lower():
                    file_to_open = f
                    break
            if not file_to_open:
                console.print(f"[yellow]No {format} file found for this book[/yellow]")
                available = ", ".join(f.format for f in book.files if f.format)
                console.print(f"[dim]Available formats: {available}[/dim]")
                lib.close()
                raise typer.Exit(code=1)
        else:
            # Prefer PDF, then EPUB, then first available
            for preferred in ["pdf", "epub", "mobi"]:
                for f in book.files:
                    if f.format and f.format.lower() == preferred:
                        file_to_open = f
                        break
                if file_to_open:
                    break
            if not file_to_open:
                file_to_open = book.files[0]

        # Build the full file path
        file_path = library_path / "files" / file_to_open.path
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Open the file
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(file_path)])
        elif system == "Windows":
            subprocess.run(["start", "", str(file_path)], shell=True)
        else:  # Linux and others
            subprocess.run(["xdg-open", str(file_path)])

        console.print(f"[green]Opened: {file_to_open.format} ({book.title})[/green]")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error opening book: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="rate")
def book_rate(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    rating: float = typer.Option(..., "--rating", "-r", help="Rating (0-5 stars)")
):
    """
    Rate a book (0-5 stars).

    Example:
        ebk book rate 42 --rating 4.5
        ebk book rate 42 ~/my-library --rating 4.5
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

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


@book_app.command(name="favorite")
def book_favorite(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    unfavorite: bool = typer.Option(False, "--unfavorite", "-u", help="Remove from favorites")
):
    """
    Mark/unmark a book as favorite.

    Examples:
        ebk book favorite 42
        ebk book favorite 42 --unfavorite
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

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


@book_app.command(name="tag")
def book_tag(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    tags: str = typer.Option(..., "--tags", "-t", help="Tags (comma-separated)"),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove tags instead of adding")
):
    """
    Add or remove personal tags from a specific book.

    Use 'ebk tag' for database-wide hierarchical tag management.

    Examples:
        ebk book tag 42 --tags "to-read,programming"
        ebk book tag 42 --tags "to-read" --remove
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

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


@book_app.command(name="delete")
def book_delete(
    book_id: int = typer.Argument(..., help="Book ID to delete"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    delete_files: bool = typer.Option(False, "--delete-files", "-f", help="Also delete associated files from disk"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Delete a book from the library.

    By default, only removes the database entry. Use --delete-files to also
    remove the physical files from disk.

    Examples:
        ebk book delete 42                    # Delete book, keep files
        ebk book delete 42 --delete-files    # Delete book and files
        ebk book delete 42 -y                 # Skip confirmation
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        # Show book info before deletion
        console.print(f"[cyan]Book to delete:[/cyan]")
        console.print(f"  ID: {book.id}")
        console.print(f"  Title: {book.title}")
        console.print(f"  Authors: {', '.join(a.name for a in book.authors)}")
        if book.files:
            console.print(f"  Files: {len(book.files)}")

        if delete_files:
            console.print(f"[yellow]  ⚠ Files will also be deleted from disk[/yellow]")

        # Confirm deletion
        if not yes:
            if not Confirm.ask("\nDelete this book?"):
                console.print("[dim]Cancelled[/dim]")
                lib.close()
                return

        lib.delete_book(book_id, delete_files=delete_files)
        console.print(f"[green]✓ Deleted book: {book.title}[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error deleting book: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="edit")
def book_edit(
    book_id: int = typer.Argument(..., help="Book ID to edit"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="New title"),
    authors: Optional[str] = typer.Option(None, "--authors", "-a", help="New authors (comma-separated, replaces existing)"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="New language code"),
    publisher: Optional[str] = typer.Option(None, "--publisher", "-p", help="New publisher"),
    series: Optional[str] = typer.Option(None, "--series", "-s", help="Series name"),
    series_index: Optional[float] = typer.Option(None, "--series-index", help="Series index/number"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description"),
    add_subject: Optional[str] = typer.Option(None, "--add-subject", help="Add a subject/category"),
    remove_subject: Optional[str] = typer.Option(None, "--remove-subject", help="Remove a subject/category"),
):
    """
    Edit book metadata.

    Only specified fields are updated; others remain unchanged.

    Examples:
        ebk book edit 42 --title "New Title"
        ebk book edit 42 --authors "John Doe, Jane Smith"
        ebk book edit 42 --series "My Series" --series-index 3
        ebk book edit 42 --add-subject "Programming"
    """
    from .library_db import Library
    from .db.models import Author, Subject

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        changes = []

        # Update simple fields
        if title is not None:
            book.title = title
            changes.append(f"title → '{title}'")

        if language is not None:
            book.language = language
            changes.append(f"language → '{language}'")

        if publisher is not None:
            book.publisher = publisher
            changes.append(f"publisher → '{publisher}'")

        if series is not None:
            book.series = series
            changes.append(f"series → '{series}'")

        if series_index is not None:
            book.series_index = series_index
            changes.append(f"series_index → {series_index}")

        if description is not None:
            book.description = description
            changes.append(f"description updated")

        # Update authors (replaces all)
        if authors is not None:
            author_names = [a.strip() for a in authors.split(',')]
            book.authors.clear()
            for name in author_names:
                author = lib.session.query(Author).filter_by(name=name).first()
                if not author:
                    author = Author(name=name)
                    lib.session.add(author)
                book.authors.append(author)
            changes.append(f"authors → {author_names}")

        # Add subject
        if add_subject:
            lib.add_subject(book_id, add_subject)
            changes.append(f"added subject '{add_subject}'")

        # Remove subject
        if remove_subject:
            subject = lib.session.query(Subject).filter_by(name=remove_subject).first()
            if subject and subject in book.subjects:
                book.subjects.remove(subject)
                changes.append(f"removed subject '{remove_subject}'")

        if not changes:
            console.print("[yellow]No changes specified[/yellow]")
            lib.close()
            return

        lib.session.commit()
        console.print(f"[green]✓ Updated '{book.title}':[/green]")
        for change in changes:
            console.print(f"  • {change}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error editing book: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="merge")
def book_merge(
    primary_id: int = typer.Argument(..., help="Book ID to keep (receives merged data)"),
    secondary_ids: str = typer.Argument(..., help="Book IDs to merge into primary (comma-separated)"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    delete_duplicate_files: bool = typer.Option(False, "--delete-duplicates", help="Delete duplicate files from disk"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be merged without making changes"),
):
    """
    Merge multiple books into one.

    The primary book receives metadata and files from secondary books.
    Secondary books are deleted after merging.

    Merge strategy:
    - Scalar fields: Keep primary's value, use secondary's if primary is empty
    - Authors/subjects/tags: Combined from all books
    - Files: All files moved to primary (duplicates by hash are skipped)
    - Personal metadata: Keep higher rating, more advanced reading status

    Examples:
        ebk book merge 42 43         # Merge book 43 into book 42
        ebk book merge 42 43,44,45   # Merge multiple books into 42
        ebk book merge 42 43 --dry-run  # Preview merge without changes
    """
    from .library_db import Library
    from rich.table import Table

    library_path = resolve_library_path(library_path)

    # Parse secondary IDs
    try:
        sec_ids = [int(x.strip()) for x in secondary_ids.split(",") if x.strip()]
    except ValueError:
        console.print("[red]Error: Secondary IDs must be comma-separated integers[/red]")
        raise typer.Exit(code=1)

    if not sec_ids:
        console.print("[red]Error: No secondary book IDs provided[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get primary book
        primary = lib.get_book(primary_id)
        if not primary:
            console.print(f"[red]Error: Primary book {primary_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Get secondary books
        secondaries = []
        for sid in sec_ids:
            if sid == primary_id:
                console.print(f"[yellow]Warning: Skipping {sid} (same as primary)[/yellow]")
                continue
            book = lib.get_book(sid)
            if book:
                secondaries.append(book)
            else:
                console.print(f"[yellow]Warning: Book {sid} not found, skipping[/yellow]")

        if not secondaries:
            console.print("[yellow]No valid secondary books to merge[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        # Show merge preview
        console.print(f"\n[bold cyan]Merge Preview[/bold cyan]\n")
        console.print(f"[green]Primary book (will keep):[/green]")
        console.print(f"  ID: {primary.id}")
        console.print(f"  Title: {primary.title}")
        console.print(f"  Authors: {', '.join(a.name for a in primary.authors)}")
        console.print(f"  Files: {len(primary.files)}")

        console.print(f"\n[yellow]Books to merge (will be deleted):[/yellow]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Title")
        table.add_column("Authors")
        table.add_column("Files")

        total_files = len(primary.files)
        for book in secondaries:
            authors = ", ".join(a.name for a in book.authors[:2])
            if len(book.authors) > 2:
                authors += "..."
            table.add_row(
                str(book.id),
                book.title[:50] + ("..." if len(book.title) > 50 else ""),
                authors,
                str(len(book.files))
            )
            total_files += len(book.files)

        console.print(table)
        console.print(f"\n[dim]After merge: Primary will have up to {total_files} files[/dim]")

        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            lib.close()
            return

        # Confirm
        if not yes:
            from rich.prompt import Confirm
            if not Confirm.ask(f"\nMerge {len(secondaries)} book(s) into '{primary.title}'?"):
                console.print("[dim]Cancelled[/dim]")
                lib.close()
                return

        # Perform merge
        merged, deleted_ids = lib.merge_books(
            primary_id,
            [b.id for b in secondaries],
            delete_secondary_files=delete_duplicate_files
        )

        if merged:
            console.print(f"\n[green]✓ Merged {len(deleted_ids)} book(s) into '{merged.title}'[/green]")
            console.print(f"  Files: {len(merged.files)}")
            console.print(f"  Authors: {', '.join(a.name for a in merged.authors)}")
            if merged.subjects:
                console.print(f"  Subjects: {', '.join(s.name for s in merged.subjects[:5])}")
        else:
            console.print("[red]Merge failed[/red]")
            raise typer.Exit(code=1)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error merging books: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="bulk-edit")
def book_bulk_edit(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    ids: Optional[str] = typer.Option(None, "--ids", "-i", help="Comma-separated book IDs"),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Search query to select books"),
    view_name: Optional[str] = typer.Option(None, "--view", "-v", help="View name to select books from"),
    # Edit options
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Set language for all selected books"),
    publisher: Optional[str] = typer.Option(None, "--publisher", "-p", help="Set publisher for all selected books"),
    series: Optional[str] = typer.Option(None, "--series", help="Set series name"),
    add_tag: Optional[str] = typer.Option(None, "--add-tag", help="Add a tag to all selected books"),
    remove_tag: Optional[str] = typer.Option(None, "--remove-tag", help="Remove a tag from all selected books"),
    add_subject: Optional[str] = typer.Option(None, "--add-subject", help="Add a subject to all selected books"),
    rating: Optional[float] = typer.Option(None, "--rating", "-r", help="Set rating (0-5) for all selected books"),
    status: Optional[str] = typer.Option(None, "--status", help="Set reading status (unread, reading, read, abandoned)"),
    favorite: Optional[bool] = typer.Option(None, "--favorite/--no-favorite", help="Set favorite status"),
    # Control options
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be changed without making changes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Bulk edit multiple books at once.

    Select books using --ids, --search, or --view, then apply changes.

    Examples:
        ebk book bulk-edit --ids 1,2,3 --language en
        ebk book bulk-edit --search "python" --add-tag "Programming"
        ebk book bulk-edit --view favorites --rating 5
        ebk book bulk-edit --search "author:Knuth" --add-subject "Computer Science"
    """
    from .library_db import Library
    from rich.table import Table

    library_path = resolve_library_path(library_path)

    # Must have at least one selection criteria
    if not ids and not search and not view_name:
        console.print("[red]Error: Must specify --ids, --search, or --view to select books[/red]")
        raise typer.Exit(code=1)

    # Must have at least one edit option
    has_edit = any([
        language, publisher, series, add_tag, remove_tag,
        add_subject, rating is not None, status, favorite is not None
    ])
    if not has_edit:
        console.print("[red]Error: Must specify at least one edit option[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get selected books
        selected_books = []

        if ids:
            # Parse IDs
            try:
                book_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
            except ValueError:
                console.print("[red]Error: IDs must be comma-separated integers[/red]")
                lib.close()
                raise typer.Exit(code=1)

            for book_id in book_ids:
                book = lib.get_book(book_id)
                if book:
                    selected_books.append(book)
                else:
                    console.print(f"[yellow]Warning: Book {book_id} not found[/yellow]")

        elif search:
            # Search for books
            results = lib.search(search)
            selected_books = results

        elif view_name:
            # Get books from view
            from .views.service import ViewService
            view_service = ViewService(lib.session, lib.library_path)
            book_ids = view_service.evaluate_view(view_name)
            for book_id in book_ids:
                book = lib.get_book(book_id)
                if book:
                    selected_books.append(book)

        if not selected_books:
            console.print("[yellow]No books selected[/yellow]")
            lib.close()
            return

        # Show preview
        console.print(f"\n[bold cyan]Bulk Edit Preview[/bold cyan]")
        console.print(f"\n[dim]Selected {len(selected_books)} book(s)[/dim]\n")

        # Show first 10 books
        table = Table(show_header=True, header_style="bold")
        table.add_column("ID", style="dim")
        table.add_column("Title")

        for book in selected_books[:10]:
            table.add_row(str(book.id), book.title[:50] + ("..." if len(book.title) > 50 else ""))

        if len(selected_books) > 10:
            table.add_row("...", f"and {len(selected_books) - 10} more")

        console.print(table)

        # Show changes
        console.print("\n[bold]Changes to apply:[/bold]")
        if language:
            console.print(f"  • Language: {language}")
        if publisher:
            console.print(f"  • Publisher: {publisher}")
        if series:
            console.print(f"  • Series: {series}")
        if add_tag:
            console.print(f"  • Add tag: {add_tag}")
        if remove_tag:
            console.print(f"  • Remove tag: {remove_tag}")
        if add_subject:
            console.print(f"  • Add subject: {add_subject}")
        if rating is not None:
            console.print(f"  • Rating: {rating}")
        if status:
            console.print(f"  • Reading status: {status}")
        if favorite is not None:
            console.print(f"  • Favorite: {favorite}")

        if dry_run:
            console.print("\n[yellow]Dry run - no changes made[/yellow]")
            lib.close()
            return

        # Confirm
        if not yes:
            from rich.prompt import Confirm
            if not Confirm.ask(f"\nApply changes to {len(selected_books)} book(s)?"):
                console.print("[dim]Cancelled[/dim]")
                lib.close()
                return

        # Apply changes
        from .db.models import Subject, Tag, PersonalMetadata

        changed = 0
        for book in selected_books:
            if language:
                book.language = language
            if publisher:
                book.publisher = publisher
            if series:
                book.series = series

            if add_subject:
                # Find or create subject
                subject = lib.session.query(Subject).filter_by(name=add_subject).first()
                if not subject:
                    subject = Subject(name=add_subject)
                    lib.session.add(subject)
                if subject not in book.subjects:
                    book.subjects.append(subject)

            if add_tag:
                # Find or create tag
                tag = lib.session.query(Tag).filter_by(path=add_tag).first()
                if not tag:
                    # Create tag with path
                    tag = Tag(name=add_tag.split("/")[-1], path=add_tag)
                    lib.session.add(tag)
                if tag not in book.tags:
                    book.tags.append(tag)

            if remove_tag:
                tag = lib.session.query(Tag).filter_by(path=remove_tag).first()
                if tag and tag in book.tags:
                    book.tags.remove(tag)

            # Personal metadata changes
            if rating is not None or status or favorite is not None:
                if not book.personal:
                    book.personal = PersonalMetadata(book_id=book.id)
                    lib.session.add(book.personal)

                if rating is not None:
                    book.personal.rating = rating
                if status:
                    book.personal.reading_status = status
                if favorite is not None:
                    book.personal.favorite = favorite

            changed += 1

        lib.session.commit()
        console.print(f"\n[green]✓ Updated {changed} book(s)[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error in bulk edit: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="similar")
def book_similar(
    book_id: int = typer.Argument(..., help="Book ID to find similar books for"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of similar books to show"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, json"),
    mode: str = typer.Option("auto", "--mode", "-m", help="Similarity mode: auto, balanced, metadata, sparse"),
):
    """
    Find books similar to a given book.

    Uses text similarity, subject overlap, and author matching to find
    related books in your library.

    Modes:
    - auto: Automatically choose based on available data (default)
    - balanced: Use content + metadata (requires extracted text)
    - metadata: Use only metadata (authors, subjects, etc.)
    - sparse: Optimized for books with limited data

    Examples:
        ebk book similar 42
        ebk book similar 42 --limit 20
        ebk book similar 42 --mode metadata
    """
    from .library_db import Library
    from .similarity import BookSimilarity

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[yellow]Book {book_id} not found[/yellow]")
            lib.close()
            raise typer.Exit(code=1)

        # Configure similarity based on mode
        similarity_config = None
        mode_name = mode
        if mode != "auto":
            if mode == "balanced":
                similarity_config = BookSimilarity().balanced()
            elif mode == "metadata":
                similarity_config = BookSimilarity().metadata_only()
            elif mode == "sparse":
                similarity_config = BookSimilarity().sparse_friendly()
            else:
                console.print(f"[yellow]Unknown mode '{mode}', using auto[/yellow]")
                mode_name = "auto"

        similar = lib.find_similar(book_id, top_k=limit, similarity_config=similarity_config)

        if not similar:
            console.print(f"[yellow]No similar books found for '{book.title}'[/yellow]")
            lib.close()
            return

        if format == "json":
            result = [
                {
                    "id": b.id,
                    "title": b.title,
                    "authors": [a.name for a in b.authors],
                    "similarity": round(score, 3)
                }
                for b, score in similar
            ]
            console.print(json.dumps(result, indent=2))
        else:
            console.print(f"\n[bold]Books similar to '{book.title}':[/bold]\n")

            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Authors")
            table.add_column("Score", justify="right")

            for sim_book, score in similar:
                authors = ", ".join(a.name for a in sim_book.authors[:2])
                if len(sim_book.authors) > 2:
                    authors += "..."
                table.add_row(
                    str(sim_book.id),
                    sim_book.title[:50] + ("..." if len(sim_book.title) > 50 else ""),
                    authors,
                    f"{score:.2f}"
                )

            console.print(table)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error finding similar books: {e}[/red]")
        raise typer.Exit(code=1)


@book_app.command(name="export")
def book_export(
    book_id: int = typer.Argument(..., help="Book ID to export"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file or directory"),
    format: str = typer.Option("json", "--format", "-f", help="Export format: json, bibtex, opds, files"),
    include_files: bool = typer.Option(False, "--include-files", help="Copy book files to output directory"),
):
    """
    Export a single book's metadata or files.

    Formats:
      json   - Full metadata as JSON
      bibtex - BibTeX citation format
      opds   - OPDS Atom entry
      files  - Copy book files only (requires --output directory)

    Examples:
        ebk book export 42                          # Print JSON to stdout
        ebk book export 42 -f bibtex                # Print BibTeX citation
        ebk book export 42 -o book.json             # Save JSON to file
        ebk book export 42 -f files -o ./exports/   # Copy files to directory
        ebk book export 42 -o ./exports/ --include-files  # JSON + files
    """
    from .library_db import Library
    import shutil

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        if format == "json":
            data = {
                "id": book.id,
                "title": book.title,
                "authors": [a.name for a in book.authors],
                "subjects": [s.name for s in book.subjects],
                "language": book.language,
                "publisher": book.publisher,
                "publication_date": str(book.publication_date) if book.publication_date else None,
                "series": book.series,
                "series_index": book.series_index,
                "description": book.description,
                "unique_id": book.unique_id,
                "tags": [t.path for t in book.tags],
                "files": [{"format": f.format, "size": f.size_bytes, "path": f.path} for f in book.files],
            }
            if book.personal:
                pm = book.personal
                data["personal"] = {
                    "rating": pm.rating,
                    "favorite": pm.favorite,
                    "reading_status": pm.reading_status,
                    "reading_progress": pm.reading_progress,
                }

            result = json.dumps(data, indent=2, default=str, ensure_ascii=False)

            if output:
                output.write_text(result)
                console.print(f"[green]✓ Exported to {output}[/green]")
            else:
                console.print(result)

        elif format == "bibtex":
            # Generate BibTeX entry
            authors = " and ".join(a.name for a in book.authors)
            year = str(book.publication_date)[:4] if book.publication_date else ""
            key = f"book{book.id}"

            # Create a clean key from author surname and year
            if book.authors:
                surname = book.authors[0].name.split()[-1].lower()
                surname = ''.join(c for c in surname if c.isalnum())
                key = f"{surname}{year}"

            bibtex = f"""@book{{{key},
  title = {{{book.title or ''}}},
  author = {{{authors}}},
  year = {{{year}}},
  publisher = {{{book.publisher or ''}}},
  language = {{{book.language or ''}}}
}}"""

            if output:
                output.write_text(bibtex)
                console.print(f"[green]✓ Exported BibTeX to {output}[/green]")
            else:
                console.print(bibtex)

        elif format == "opds":
            from .exports.opds_export import build_entry
            entry = build_entry(book, base_url="file://", files_dir="files", covers_dir="covers")

            if output:
                output.write_text(entry)
                console.print(f"[green]✓ Exported OPDS entry to {output}[/green]")
            else:
                console.print(entry)

        elif format == "files":
            if not output:
                console.print("[red]Error: --output directory required for 'files' format[/red]")
                lib.close()
                raise typer.Exit(code=1)

            output.mkdir(parents=True, exist_ok=True)

            if not book.files:
                console.print(f"[yellow]No files attached to book '{book.title}'[/yellow]")
            else:
                for f in book.files:
                    src = library_path / f.path
                    if src.exists():
                        dst = output / src.name
                        shutil.copy2(src, dst)
                        console.print(f"[green]✓ Copied {src.name}[/green]")
                    else:
                        console.print(f"[yellow]File not found: {f.path}[/yellow]")

        else:
            console.print(f"[red]Unknown format: {format}[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Copy files if requested (for non-files formats)
        if include_files and format != "files" and output:
            files_dir = output.parent if output.is_file() else output
            files_dir = files_dir / "files"
            files_dir.mkdir(parents=True, exist_ok=True)

            for f in book.files:
                src = library_path / f.path
                if src.exists():
                    dst = files_dir / src.name
                    shutil.copy2(src, dst)
                    console.print(f"[dim]Copied {src.name}[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting book: {e}[/red]")
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


@note_app.command(name="extract")
def note_extract(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
    format_filter: Optional[str] = typer.Option(None, "--format", "-f", help="Extract from specific format (pdf, epub)")
):
    """
    Extract annotations/highlights from book files (PDF, EPUB).

    This extracts highlights, notes, and bookmarks embedded in the actual
    ebook files by reading apps and saves them to the library database.

    Examples:
        ebk note extract 42                    # Extract from all formats
        ebk note extract 42 --format pdf       # Extract only from PDF
    """
    from .library_db import Library
    from .services.annotation_extraction import extract_and_save_annotations

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        console.print(f"[cyan]Extracting annotations from: {book.title}[/cyan]")

        # Show available files
        for f in book.files:
            filename = Path(f.path).name if f.path else "unknown"
            console.print(f"  [dim]- {f.format.upper()}: {filename}[/dim]")

        count = extract_and_save_annotations(lib, book_id, format_filter)

        if count > 0:
            console.print(f"[green]✓ Extracted and saved {count} annotation(s)[/green]")
        else:
            console.print("[yellow]No new annotations found to extract[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error extracting annotations: {e}[/red]")
        raise typer.Exit(code=1)


@note_app.command(name="export")
def note_export(
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    format_type: str = typer.Option("markdown", "--format", "-f", help="Output format (markdown, json, txt)")
):
    """
    Export annotations for a book.

    Examples:
        ebk note export 42                          # Print to stdout as markdown
        ebk note export 42 -o notes.md              # Save as markdown
        ebk note export 42 -o notes.json -f json    # Save as JSON
    """
    from .library_db import Library
    import json

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        annotations = lib.get_annotations(book_id)

        if not annotations:
            console.print(f"[yellow]No annotations for '{book.title}'[/yellow]")
            lib.close()
            return

        # Format output
        if format_type == "json":
            data = {
                "book": {
                    "id": book.id,
                    "title": book.title,
                    "authors": [a.name for a in book.authors]
                },
                "annotations": [
                    {
                        "type": a.annotation_type,
                        "content": a.content,
                        "page": a.page_number,
                        "color": a.color,
                        "created_at": a.created_at.isoformat()
                    }
                    for a in annotations
                ]
            }
            result = json.dumps(data, indent=2)

        elif format_type == "txt":
            lines = [f"Annotations: {book.title}", "=" * 50, ""]
            for a in annotations:
                page = f" (p.{a.page_number})" if a.page_number else ""
                lines.append(f"[{a.annotation_type}]{page}")
                lines.append(a.content)
                lines.append("")
            result = "\n".join(lines)

        else:  # markdown
            authors = ", ".join(a.name for a in book.authors) or "Unknown"
            lines = [f"# Annotations: {book.title}", f"*{authors}*", ""]

            # Group by type
            by_type = {}
            for a in annotations:
                by_type.setdefault(a.annotation_type, []).append(a)

            for atype, items in by_type.items():
                lines.append(f"## {atype.title()}s")
                lines.append("")
                for a in items:
                    page = f" *(page {a.page_number})*" if a.page_number else ""
                    lines.append(f"- {a.content}{page}")
                lines.append("")

            result = "\n".join(lines)

        # Output
        if output:
            output.write_text(result)
            console.print(f"[green]✓ Exported {len(annotations)} annotations to {output}[/green]")
        else:
            console.print(result)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting annotations: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Export Commands
# ============================================================================

@export_app.command(name="json")
def export_json(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output JSON file"),
    include_annotations: bool = typer.Option(True, "--annotations/--no-annotations", help="Include annotations"),
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
):
    """
    Export library to JSON format.

    Examples:
        ebk export json ~/my-library ~/backup.json
        ebk export json ~/my-library ~/favorites.json --view favorites
    """
    from .library_db import Library
    import json

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get books from view or all books
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' ({len(books)} books)...[/blue]")
        else:
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
    output_file: Path = typer.Argument(..., help="Output CSV file"),
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
):
    """
    Export library to CSV format.

    Examples:
        ebk export csv ~/my-library ~/books.csv
        ebk export csv ~/my-library ~/programming.csv --view programming
    """
    from .library_db import Library
    import csv

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get books from view or all books
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' ({len(books)} books)...[/blue]")
        else:
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
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
    # Filtering options (ignored if --view is specified)
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

        # Export a view
        ebk export html ~/my-library ~/favorites.html --view favorites

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
        lib = Library.open(library_path)

        # Get books from view or apply filters
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' to HTML ({len(books)} books)...[/blue]")
        else:
            console.print("[blue]Exporting library to HTML...[/blue]")
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

        # Gather views data for sidebar navigation
        from .views import ViewService
        views_svc = ViewService(lib.session)
        all_views = views_svc.list(include_builtin=True)

        # Build book_ids for each view based on current books
        book_ids_set = {b.id for b in books}
        views_data = []
        for v in all_views:
            try:
                view_books = views_svc.evaluate(v['name'])
                view_book_ids = [tb.book.id for tb in view_books if tb.book.id in book_ids_set]
                if view_book_ids:  # Only include views with matching books
                    views_data.append({
                        'name': v['name'],
                        'description': v.get('description', ''),
                        'book_ids': view_book_ids,
                        'builtin': v.get('builtin', False)
                    })
            except Exception:
                pass  # Skip views that fail to evaluate

        export_to_html(books, output_file, include_stats=include_stats, base_url=base_url, views=views_data)

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


@export_app.command(name="opds")
def export_opds(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output OPDS catalog file (e.g., catalog.xml)"),
    title: str = typer.Option("ebk Library", "--title", "-t", help="Catalog title"),
    subtitle: str = typer.Option("", "--subtitle", help="Catalog subtitle/description"),
    base_url: str = typer.Option("", "--base-url", help="Base URL for file/cover links"),
    copy_files: bool = typer.Option(False, "--copy-files", help="Copy ebook files to output directory"),
    copy_covers: bool = typer.Option(False, "--copy-covers", help="Copy cover images to output directory"),
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
    # Filtering options (ignored if --view is specified)
    language: Optional[str] = typer.Option(None, "--language", help="Filter by language code"),
    author: Optional[str] = typer.Option(None, "--author", help="Filter by author name"),
    subject: Optional[str] = typer.Option(None, "--subject", help="Filter by subject/tag"),
    format_filter: Optional[str] = typer.Option(None, "--format", help="Filter by file format"),
    has_files: bool = typer.Option(True, "--has-files/--no-files", help="Only include books with files"),
    favorite: Optional[bool] = typer.Option(None, "--favorite", help="Filter by favorite status"),
    min_rating: Optional[int] = typer.Option(None, "--min-rating", help="Minimum rating (1-5)"),
):
    """
    Export library to an OPDS catalog file.

    Creates an OPDS 1.2 compatible Atom feed that can be served from any
    static file host or used with OPDS reader apps (Foliate, KOReader, etc.).

    The catalog includes metadata, cover images, and download links for all books.
    Use --copy-files and --copy-covers to create a self-contained export.

    Examples:
        # Basic catalog export
        ebk export opds ~/my-library ~/public/catalog.xml

        # Export a view
        ebk export opds ~/my-library ~/public/favorites.xml --view favorites

        # Full export with files for static hosting
        ebk export opds ~/my-library ~/public/catalog.xml \\
            --base-url https://example.com/library \\
            --copy-files --copy-covers

        # Export only favorites
        ebk export opds ~/my-library ~/catalog.xml --favorite
    """
    from .library_db import Library
    from .exports.opds_export import export_to_opds

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get books from view or apply filters
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' to OPDS catalog ({len(books)} books)...[/blue]")
        else:
            console.print("[blue]Exporting library to OPDS catalog...[/blue]")
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

        console.print(f"  Exporting {len(books)} books...")

        stats = export_to_opds(
            books=books,
            output_path=output_file,
            library_path=library_path,
            title=title,
            subtitle=subtitle,
            base_url=base_url,
            copy_files=copy_files,
            copy_covers=copy_covers,
        )

        console.print(f"[green]✓ Exported {stats['books']} books to {output_file}[/green]")

        if copy_files:
            console.print(f"  Files copied: {stats['files_copied']}")
        if copy_covers:
            console.print(f"  Covers copied: {stats['covers_copied']}")
        if stats['errors']:
            console.print(f"[yellow]  Warnings: {len(stats['errors'])} errors during export[/yellow]")
            for error in stats['errors'][:5]:
                console.print(f"    - {error}")

        if base_url:
            console.print(f"  Links use base URL: {base_url}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to OPDS: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(code=1)


@export_app.command(name="goodreads")
def export_goodreads(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output CSV file"),
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
):
    """
    Export library to Goodreads-compatible CSV format.

    Creates a CSV file that can be imported into Goodreads using their
    import feature at https://www.goodreads.com/review/import

    The export includes:
    - Title, Author, Additional Authors
    - ISBN/ISBN13
    - Rating (converted to 1-5 stars)
    - Reading status (read, currently-reading, to-read)
    - Bookshelves (from tags)
    - Page count, Publisher, Publication year

    Examples:
        ebk export goodreads ~/my-library ~/goodreads.csv
        ebk export goodreads ~/my-library ~/favorites.csv --view favorites
    """
    from .library_db import Library
    from .services.export_service import ExportService

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get books from view or all books
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' to Goodreads format ({len(books)} books)...[/blue]")
        else:
            books = lib.get_all_books()
            console.print(f"[blue]Exporting {len(books)} books to Goodreads format...[/blue]")

        export_svc = ExportService(lib.session, library_path)
        csv_content = export_svc.export_goodreads_csv(books)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        console.print(f"[green]✓ Exported {len(books)} books to {output_file}[/green]")
        console.print("  Import this file at: https://www.goodreads.com/review/import")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to Goodreads format: {e}[/red]")
        raise typer.Exit(code=1)


@export_app.command(name="calibre")
def export_calibre(
    library_path: Path = typer.Argument(..., help="Path to library"),
    output_file: Path = typer.Argument(..., help="Output CSV file"),
    view: Optional[str] = typer.Option(None, "--view", "-V", help="Export only books from this view"),
):
    """
    Export library to Calibre-compatible CSV format.

    Creates a CSV file that can be used with Calibre's import features
    or the calibredb command-line tool.

    The export includes:
    - Title, Authors, Author Sort
    - Publisher, Publication Date
    - Languages, Rating (converted to 0-10 scale)
    - Tags (subjects, hierarchical tags, reading status)
    - Series and Series Index
    - Identifiers (ISBN, ASIN, etc.)
    - Comments/Description

    Examples:
        ebk export calibre ~/my-library ~/calibre.csv
        ebk export calibre ~/my-library ~/programming.csv --view programming
    """
    from .library_db import Library
    from .services.export_service import ExportService

    if not library_path.exists():
        console.print(f"[red]Error: Library not found: {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)

        # Get books from view or all books
        if view:
            from .views import ViewService
            svc = ViewService(lib.session)
            transformed = svc.evaluate(view)
            books = [tb.book for tb in transformed]
            console.print(f"[blue]Exporting view '{view}' to Calibre format ({len(books)} books)...[/blue]")
        else:
            books = lib.get_all_books()
            console.print(f"[blue]Exporting {len(books)} books to Calibre format...[/blue]")

        export_svc = ExportService(lib.session, library_path)
        csv_content = export_svc.export_calibre_csv(books)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(csv_content)

        console.print(f"[green]✓ Exported {len(books)} books to {output_file}[/green]")
        console.print("  Use with: calibredb add --from-csv <file>")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error exporting to Calibre format: {e}[/red]")
        raise typer.Exit(code=1)


@app.command(name="read")
def read_book(
    book_id: int = typer.Argument(..., help="Book ID to read"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library (uses config default if not specified)"),
    text: bool = typer.Option(False, "--text", help="Display extracted text in console"),
    page: Optional[int] = typer.Option(None, "--page", help="View specific page (for text mode)"),
    format_choice: Optional[str] = typer.Option(None, "--format", help="Choose specific format (pdf, epub, txt, etc.)")
):
    """
    Read/view a book's content.

    Without --text: Opens the ebook file in the default application.
    With --text: Displays extracted text in the console with paging.
    If no library path is specified, uses the default from config.
    """
    import subprocess
    import platform
    from .library_db import Library
    from .db.models import ExtractedText

    library_path = resolve_library_path(library_path)

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


# ============================================================================
# Tag Management Commands
# ============================================================================

@tag_app.command(name="list")
def tag_list(
    library_path: Path = typer.Argument(..., help="Path to library"),
    tag_path: Optional[str] = typer.Option(None, "--tag", "-t", help="List books with specific tag"),
    include_subtags: bool = typer.Option(False, "--subtags", "-s", help="Include books from subtags"),
):
    """
    List all tags or books with a specific tag.

    Examples:
        ebk tag list ~/my-library              - List all tags
        ebk tag list ~/my-library -t Work      - List books tagged with "Work"
        ebk tag list ~/my-library -t Work -s   - Include books from Work/* subtags
    """
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        if tag_path:
            # List books with specific tag
            books = tag_service.get_books_with_tag(tag_path, include_subtags=include_subtags)

            if not books:
                console.print(f"[yellow]No books found with tag '{tag_path}'[/yellow]")
                lib.close()
                raise typer.Exit(code=0)

            table = Table(title=f"Books with tag '{tag_path}'", show_header=True, header_style="bold magenta")
            table.add_column("ID", style="cyan", width=6)
            table.add_column("Title", style="white")
            table.add_column("Authors", style="green")

            for book in books:
                authors = ", ".join([a.name for a in book.authors]) if book.authors else "Unknown"
                table.add_row(str(book.id), book.title or "Untitled", authors)

            console.print(table)
            console.print(f"\n[cyan]Total:[/cyan] {len(books)} books")

        else:
            # List all tags
            tags = tag_service.get_all_tags()

            if not tags:
                console.print("[yellow]No tags found in library[/yellow]")
                lib.close()
                raise typer.Exit(code=0)

            table = Table(title="All Tags", show_header=True, header_style="bold magenta")
            table.add_column("Path", style="cyan")
            table.add_column("Books", style="white", justify="right")
            table.add_column("Subtags", style="green", justify="right")
            table.add_column("Description", style="yellow")

            for tag in tags:
                stats = tag_service.get_tag_stats(tag.path)
                desc = tag.description[:50] + "..." if tag.description and len(tag.description) > 50 else tag.description or ""
                table.add_row(
                    tag.path,
                    str(stats.get('book_count', 0)),
                    str(stats.get('subtag_count', 0)),
                    desc
                )

            console.print(table)
            console.print(f"\n[cyan]Total:[/cyan] {len(tags)} tags")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error listing tags: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="tree")
def tag_tree(
    library_path: Path = typer.Argument(..., help="Path to library"),
    root: Optional[str] = typer.Option(None, "--root", "-r", help="Root tag to display (default: all)"),
):
    """
    Display hierarchical tag tree.

    Examples:
        ebk tag tree ~/my-library              - Show all tags as tree
        ebk tag tree ~/my-library -r Work      - Show Work tag subtree
    """
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    def print_tree(tag, tag_service, prefix="", is_last=True):
        """Recursively print tag tree."""
        # Tree characters
        connector = "└── " if is_last else "├── "
        extension = "    " if is_last else "│   "

        # Get stats
        stats = tag_service.get_tag_stats(tag.path)
        book_count = stats.get('book_count', 0)

        # Format tag name with book count
        tag_display = f"[cyan]{tag.name}[/cyan]"
        if book_count > 0:
            tag_display += f" [dim]({book_count} books)[/dim]"

        console.print(f"{prefix}{connector}{tag_display}")

        # Get and print children
        children = tag_service.get_children(tag)
        for i, child in enumerate(children):
            is_last_child = (i == len(children) - 1)
            print_tree(child, tag_service, prefix + extension, is_last_child)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        if root:
            # Display specific subtree
            root_tag = tag_service.get_tag(root)
            if not root_tag:
                console.print(f"[red]Tag '{root}' not found[/red]")
                lib.close()
                raise typer.Exit(code=1)

            console.print(f"[bold]Tag Tree: {root}[/bold]\n")
            print_tree(root_tag, tag_service, "", True)

        else:
            # Display entire tree
            root_tags = tag_service.get_root_tags()

            if not root_tags:
                console.print("[yellow]No tags found in library[/yellow]")
                lib.close()
                raise typer.Exit(code=0)

            console.print("[bold]Tag Tree[/bold]\n")
            for i, tag in enumerate(root_tags):
                is_last = (i == len(root_tags) - 1)
                print_tree(tag, tag_service, "", is_last)

        lib.close()

    except Exception as e:
        console.print(f"[red]Error displaying tag tree: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="add")
def tag_add(
    book_id: int = typer.Argument(..., help="Book ID"),
    tag_path: str = typer.Argument(..., help="Tag path (e.g., 'Work/Project-2024')"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Tag description (for new tags)"),
    color: Optional[str] = typer.Option(None, "--color", "-c", help="Tag color in hex (e.g., '#FF5733')"),
):
    """
    [DEPRECATED] Add a tag to a book.

    This command is deprecated. Use VFS commands instead:
        ebk vfs ln <library> /books/<id> /tags/<tag-path>/

    Creates tag hierarchy automatically if it doesn't exist.

    Examples:
        ebk tag add 42 Work ~/my-library
        ebk tag add 42 Work/Project-2024 ~/my-library -d "2024 project books"
        ebk tag add 42 Reading-List ~/my-library -c "#3498db"

    Migrating to VFS:
        ebk vfs ln ~/my-library /books/42 /tags/Work/
        ebk vfs mkdir ~/my-library /tags/Work/Project-2024/
        ebk vfs ln ~/my-library /books/42 /tags/Work/Project-2024/
    """
    console.print("[yellow]⚠ Warning: 'ebk tag add' is deprecated. Use 'ebk vfs ln' instead.[/yellow]")
    console.print(f"[yellow]  Example: ebk vfs ln {library_path} /books/{book_id} /tags/{tag_path}/[/yellow]\n")
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService
    from ebk.db.models import Book

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        # Get book
        book = lib.session.query(Book).filter_by(id=book_id).first()
        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Add tag to book
        tag = tag_service.add_tag_to_book(book, tag_path)

        # Update tag metadata if provided (only for leaf tag)
        if description and tag.description != description:
            tag.description = description
            lib.session.commit()

        if color and tag.color != color:
            tag.color = color
            lib.session.commit()

        console.print(f"[green]✓ Added tag '{tag.path}' to book {book.id}[/green]")
        if book.title:
            console.print(f"  Book: {book.title}")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error adding tag: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="remove")
def tag_remove(
    book_id: int = typer.Argument(..., help="Book ID"),
    tag_path: str = typer.Argument(..., help="Tag path (e.g., 'Work/Project-2024')"),
    library_path: Path = typer.Argument(..., help="Path to library"),
):
    """
    [DEPRECATED] Remove a tag from a book.

    This command is deprecated. Use VFS commands instead:
        ebk vfs rm <library> /tags/<tag-path>/<book-id>

    Examples:
        ebk tag remove 42 Work ~/my-library
        ebk tag remove 42 Work/Project-2024 ~/my-library

    Migrating to VFS:
        ebk vfs rm ~/my-library /tags/Work/42
        ebk vfs rm ~/my-library /tags/Work/Project-2024/42
    """
    console.print("[yellow]⚠ Warning: 'ebk tag remove' is deprecated. Use 'ebk vfs rm' instead.[/yellow]")
    console.print(f"[yellow]  Example: ebk vfs rm {library_path} /tags/{tag_path}/{book_id}[/yellow]\n")
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService
    from ebk.db.models import Book

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        # Get book
        book = lib.session.query(Book).filter_by(id=book_id).first()
        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        # Remove tag from book
        removed = tag_service.remove_tag_from_book(book, tag_path)

        if removed:
            console.print(f"[green]✓ Removed tag '{tag_path}' from book {book.id}[/green]")
            if book.title:
                console.print(f"  Book: {book.title}")
        else:
            console.print(f"[yellow]Book {book.id} didn't have tag '{tag_path}'[/yellow]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error removing tag: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="rename")
def tag_rename(
    old_path: str = typer.Argument(..., help="Current tag path"),
    new_path: str = typer.Argument(..., help="New tag path"),
    library_path: Path = typer.Argument(..., help="Path to library"),
):
    """
    Rename a tag and update all descendant paths.

    Examples:
        ebk tag rename Work Archive ~/my-library
        ebk tag rename Work/Old Work/Completed ~/my-library
    """
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        # Get tag stats before rename
        old_tag = tag_service.get_tag(old_path)
        if not old_tag:
            console.print(f"[red]Tag '{old_path}' not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        stats = tag_service.get_tag_stats(old_path)
        book_count = stats.get('book_count', 0)
        subtag_count = stats.get('subtag_count', 0)

        # Rename tag
        tag = tag_service.rename_tag(old_path, new_path)

        console.print(f"[green]✓ Renamed tag '{old_path}' → '{new_path}'[/green]")
        if book_count > 0:
            console.print(f"  Books: {book_count}")
        if subtag_count > 0:
            console.print(f"  Subtags updated: {subtag_count}")

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error renaming tag: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="delete")
def tag_delete(
    tag_path: str = typer.Argument(..., help="Tag path to delete"),
    library_path: Path = typer.Argument(..., help="Path to library"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Delete tag and all children"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
):
    """
    [DEPRECATED] Delete a tag.

    This command is deprecated. Use VFS commands instead:
        ebk vfs rm <library> /tags/<tag-path>/ [-r]

    Examples:
        ebk tag delete OldTag ~/my-library
        ebk tag delete OldProject ~/my-library -r     - Delete with children
        ebk tag delete Archive ~/my-library -r -f     - Delete without confirmation

    Migrating to VFS:
        ebk vfs rm ~/my-library /tags/OldTag/
        ebk vfs rm ~/my-library /tags/OldProject/ -r
    """
    console.print("[yellow]⚠ Warning: 'ebk tag delete' is deprecated. Use 'ebk vfs rm' instead.[/yellow]")
    console.print(f"[yellow]  Example: ebk vfs rm {library_path} /tags/{tag_path}/{ ' -r' if recursive else ''}[/yellow]\n")
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        # Get tag stats
        tag = tag_service.get_tag(tag_path)
        if not tag:
            console.print(f"[red]Tag '{tag_path}' not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        stats = tag_service.get_tag_stats(tag_path)
        book_count = stats.get('book_count', 0)
        subtag_count = stats.get('subtag_count', 0)

        # Confirm deletion if not forced
        if not force:
            console.print(f"[yellow]About to delete tag:[/yellow] {tag_path}")
            if book_count > 0:
                console.print(f"  Books: {book_count}")
            if subtag_count > 0:
                console.print(f"  Subtags: {subtag_count}")
                if not recursive:
                    console.print(f"[red]Error: Tag has {subtag_count} children. Use -r to delete recursively.[/red]")
                    lib.close()
                    raise typer.Exit(code=1)

            if not Confirm.ask("Are you sure?"):
                console.print("[cyan]Cancelled[/cyan]")
                lib.close()
                raise typer.Exit(code=0)

        # Delete tag
        deleted = tag_service.delete_tag(tag_path, delete_children=recursive)

        if deleted:
            console.print(f"[green]✓ Deleted tag '{tag_path}'[/green]")
        else:
            console.print(f"[yellow]Tag '{tag_path}' not found[/yellow]")

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print(f"[yellow]Hint: Use -r flag to delete tag with children[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error deleting tag: {e}[/red]")
        raise typer.Exit(code=1)


@tag_app.command(name="stats")
def tag_stats(
    library_path: Path = typer.Argument(..., help="Path to library"),
    tag_path: Optional[str] = typer.Option(None, "--tag", "-t", help="Specific tag to show stats for"),
):
    """
    Show tag statistics.

    Examples:
        ebk tag stats ~/my-library              - Overall tag statistics
        ebk tag stats ~/my-library -t Work      - Stats for specific tag
    """
    from ebk.library_db import Library
    from ebk.services.tag_service import TagService
    from ebk.db.models import Tag

    library_path = Path(library_path)
    if not library_path.exists():
        console.print(f"[red]Error: Library not found at {library_path}[/red]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        tag_service = TagService(lib.session)

        if tag_path:
            # Show stats for specific tag
            tag = tag_service.get_tag(tag_path)
            if not tag:
                console.print(f"[red]Tag '{tag_path}' not found[/red]")
                lib.close()
                raise typer.Exit(code=1)

            stats = tag_service.get_tag_stats(tag_path)

            console.print(f"[bold cyan]Tag Statistics: {tag_path}[/bold cyan]\n")
            console.print(f"Name:        {tag.name}")
            console.print(f"Path:        {tag.path}")
            console.print(f"Depth:       {stats.get('depth', 0)}")
            console.print(f"Books:       {stats.get('book_count', 0)}")
            console.print(f"Subtags:     {stats.get('subtag_count', 0)}")

            if tag.description:
                console.print(f"Description: {tag.description}")

            if tag.color:
                console.print(f"Color:       {tag.color}")

            if stats.get('created_at'):
                console.print(f"Created:     {stats['created_at']}")

        else:
            # Show overall statistics
            total_tags = lib.session.query(Tag).count()
            root_tags = len(tag_service.get_root_tags())

            # Count tagged books
            from ebk.db.models import book_tags
            tagged_books = lib.session.query(book_tags.c.book_id).distinct().count()

            console.print("[bold cyan]Tag Statistics[/bold cyan]\n")
            console.print(f"Total tags:    {total_tags}")
            console.print(f"Root tags:     {root_tags}")
            console.print(f"Tagged books:  {tagged_books}")

            if total_tags > 0:
                # Find most popular tags
                all_tags = tag_service.get_all_tags()
                tags_with_counts = [(tag, len(tag.books)) for tag in all_tags]
                tags_with_counts.sort(key=lambda x: x[1], reverse=True)

                console.print("\n[bold]Most Popular Tags:[/bold]")
                for tag, count in tags_with_counts[:10]:
                    if count > 0:
                        console.print(f"  {tag.path:<40} {count:>3} books")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error getting tag statistics: {e}[/red]")
        raise typer.Exit(code=1)


# ==============================================================================
# VFS Commands - Operate on VFS paths
# ==============================================================================

@vfs_app.command(name="ln")
def vfs_ln(
    source: str = typer.Argument(..., help="Source path (e.g., /books/42 or /tags/Work/42)"),
    dest: str = typer.Argument(..., help="Destination tag path (e.g., /tags/Archive/)"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Link a book to a tag.

    Examples:
        ebk vfs ln /books/42 /tags/Work/
        ebk vfs ln /tags/Work/42 /tags/Archive/
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)
        shell.cmd_ln([source, dest], silent=False)
        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="mv")
def vfs_mv(
    source: str = typer.Argument(..., help="Source path (e.g., /tags/Work/42)"),
    dest: str = typer.Argument(..., help="Destination tag path (e.g., /tags/Archive/)"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Move a book between tags.

    Examples:
        ebk vfs mv /tags/Work/42 /tags/Archive/
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)
        shell.cmd_mv([source, dest], silent=False)
        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="rm")
def vfs_rm(
    path: str = typer.Argument(..., help="Path to remove (e.g., /tags/Work/42 or /books/42/)"),
    recursive: bool = typer.Option(False, "-r", "--recursive", help="Recursively delete tag and children"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Remove tag from book, delete tag, or DELETE book.

    Examples:
        ebk vfs rm /tags/Work/42          # Remove tag from book
        ebk vfs rm /tags/Work/            # Delete tag
        ebk vfs rm /tags/Work/ -r         # Delete tag recursively
        ebk vfs rm /books/42/             # DELETE book (with confirmation)
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)

        args = [path]
        if recursive:
            args.insert(0, '-r')

        shell.cmd_rm(args, silent=False)
        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="mkdir")
def vfs_mkdir(
    path: str = typer.Argument(..., help="Tag path to create (e.g., /tags/Work/Project-2024/)"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Create a new tag directory.

    Examples:
        ebk vfs mkdir /tags/Work/
        ebk vfs mkdir /tags/Work/Project-2024/
        ebk vfs mkdir /tags/Reading/Fiction/Sci-Fi/
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)
        shell.cmd_mkdir([path], silent=False)
        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="ls")
def vfs_ls(
    path: str = typer.Argument("/", help="VFS path to list (e.g., /books/ or /tags/Work/)"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """List contents of a VFS directory.

    Examples:
        ebk vfs ls                      # List root, uses config default library
        ebk vfs ls /books/
        ebk vfs ls /tags/Work/
        ebk vfs ls /books/42/ -L ~/library
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)

        shell.cmd_ls([path], silent=False)

        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="cat")
def vfs_cat(
    path: str = typer.Argument(..., help="VFS file path (e.g., /books/42/title or /tags/Work/description)"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Read contents of a VFS file.

    Examples:
        ebk vfs cat /books/42/title
        ebk vfs cat /tags/Work/description
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)

        shell.cmd_cat([path], silent=False)

        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@vfs_app.command(name="exec")
def vfs_exec(
    command: str = typer.Argument(..., help="Shell command to execute"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library (uses config default if not specified)"),
):
    """Execute a shell command with VFS context.

    This runs a command in the shell environment, allowing you to use
    shell syntax like pipes, redirection, and multiple commands.

    Examples:
        ebk vfs exec "ls /tags/"
        ebk vfs exec "cat /books/42/title"
        ebk vfs exec "find author:Knuth | wc -l"
    """
    from .repl.shell import LibraryShell

    library_path = resolve_library_path(library_path)

    try:
        shell = LibraryShell(library_path)

        # Execute the command
        shell.execute(command)

        shell.cleanup()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# Queue Commands
# ============================================================================

@queue_app.command(name="list")
def queue_list(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
):
    """
    Show the current reading queue.

    Examples:
        ebk queue list
        ebk queue list ~/my-library
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        queue = lib.get_reading_queue()

        if not queue:
            console.print("[yellow]Reading queue is empty[/yellow]")
            console.print("Add books with: ebk queue add <book_id>")
            lib.close()
            return

        table = Table(title="Reading Queue", show_header=True)
        table.add_column("#", style="cyan", width=4)
        table.add_column("ID", style="dim", width=6)
        table.add_column("Title", style="green")
        table.add_column("Authors")
        table.add_column("Progress", width=10)

        for book in queue:
            progress = ""
            if book.personal:
                if book.personal.reading_progress:
                    progress = f"{book.personal.reading_progress}%"
                if book.personal.reading_status == "reading":
                    progress = f"📖 {progress}" if progress else "📖"

            table.add_row(
                str(book.personal.queue_position),
                str(book.id),
                book.title[:50] + "..." if len(book.title) > 50 else book.title,
                ", ".join(a.name for a in book.authors[:2]) or "-",
                progress
            )

        console.print(table)
        console.print(f"\n[dim]{len(queue)} book(s) in queue[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@queue_app.command(name="add")
def queue_add(
    book_id: int = typer.Argument(..., help="Book ID to add"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
    position: Optional[int] = typer.Option(None, "--position", "-p", help="Position (1=top)"),
):
    """
    Add a book to the reading queue.

    Examples:
        ebk queue add 42                    # Add to end of queue
        ebk queue add 42 --position 1       # Add to top of queue
        ebk queue add 42 -p 3               # Add at position 3
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        lib.add_to_queue(book_id, position)

        pos = position or len(lib.get_reading_queue())
        console.print(f"[green]✓ Added to queue at #{pos}: '{book.title}'[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@queue_app.command(name="remove")
def queue_remove(
    book_id: int = typer.Argument(..., help="Book ID to remove"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
):
    """
    Remove a book from the reading queue.

    Examples:
        ebk queue remove 42
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        lib.remove_from_queue(book_id)
        console.print(f"[green]✓ Removed from queue: '{book.title}'[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@queue_app.command(name="move")
def queue_move(
    book_id: int = typer.Argument(..., help="Book ID to move"),
    position: int = typer.Argument(..., help="New position (1=top)"),
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
):
    """
    Move a book to a different position in the queue.

    Examples:
        ebk queue move 42 1         # Move to top
        ebk queue move 42 3         # Move to position 3
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        book = lib.get_book(book_id)

        if not book:
            console.print(f"[red]Book {book_id} not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        lib.reorder_queue(book_id, position)
        console.print(f"[green]✓ Moved '{book.title}' to position #{position}[/green]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@queue_app.command(name="clear")
def queue_clear(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
):
    """
    Clear all books from the reading queue.

    Examples:
        ebk queue clear
        ebk queue clear --yes
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    if not yes:
        confirm = typer.confirm("Clear the entire reading queue?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit()

    try:
        lib = Library.open(library_path)
        lib.clear_queue()
        console.print("[green]✓ Reading queue cleared[/green]")
        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@queue_app.command(name="next")
def queue_next(
    library_path: Optional[Path] = typer.Argument(None, help="Path to library"),
):
    """
    Show the next book in the reading queue.

    Examples:
        ebk queue next
    """
    from .library_db import Library

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        queue = lib.get_reading_queue()

        if not queue:
            console.print("[yellow]Reading queue is empty[/yellow]")
            lib.close()
            return

        book = queue[0]
        console.print(f"\n[bold cyan]Up Next:[/bold cyan]")
        console.print(f"  [green]{book.title}[/green]")
        if book.authors:
            console.print(f"  by {', '.join(a.name for a in book.authors)}")
        if book.personal and book.personal.reading_progress:
            console.print(f"  Progress: {book.personal.reading_progress}%")
        console.print(f"\n  [dim]Book ID: {book.id}[/dim]")

        if len(queue) > 1:
            console.print(f"\n[dim]{len(queue) - 1} more book(s) in queue[/dim]")

        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


# ============================================================================
# View Commands - Composable, named subsets of the library
# ============================================================================

@view_app.command(name="create")
def view_create(
    name: str = typer.Argument(..., help="Name for the view"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="View description"),
    subject: Optional[str] = typer.Option(None, "--subject", "-s", help="Filter by subject"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Filter by author"),
    language: Optional[str] = typer.Option(None, "--language", "-l", help="Filter by language"),
    favorite: Optional[bool] = typer.Option(None, "--favorite", "-f", help="Filter by favorite"),
    status: Optional[str] = typer.Option(None, "--status", "-S", help="Filter by reading status"),
    rating_gte: Optional[int] = typer.Option(None, "--rating-gte", help="Filter by rating >= value"),
    definition_file: Optional[Path] = typer.Option(None, "--from-file", help="Load definition from YAML file"),
    sql_query: Optional[str] = typer.Option(None, "--sql", help="SQL query returning book IDs (SELECT only)"),
):
    """
    Create a new view.

    Views are named, composable subsets of your library. Create views from
    simple filters, SQL queries, or complex YAML definitions.

    Examples:
        ebk view create favorites --favorite
        ebk view create programming --subject programming
        ebk view create top-rated --rating-gte 4 --description "My best books"
        ebk view create complex --from-file my-view.yaml
        ebk view create english --sql "SELECT id FROM books WHERE language = 'en'"
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        if definition_file:
            view = svc.import_file(definition_file)
            # Override name if different
            if view.name != name:
                svc.rename(view.name, name)
            if description:
                svc.update(name, description=description)
        elif sql_query:
            # SQL-based view
            definition = {
                'select': {'sql': sql_query},
                'order': {'by': 'title'}
            }
            view = svc.create(name, definition=definition, description=description)
        else:
            # Build definition from filters
            filter_pred = {}
            if subject:
                filter_pred['subject'] = subject
            if author:
                filter_pred['author'] = author
            if language:
                filter_pred['language'] = language
            if favorite is not None:
                filter_pred['favorite'] = favorite
            if status:
                filter_pred['reading_status'] = status
            if rating_gte:
                filter_pred['rating'] = {'gte': rating_gte}

            definition = {'select': {'filter': filter_pred}} if filter_pred else {'select': 'all'}
            definition['order'] = {'by': 'title'}

            view = svc.create(name, definition=definition, description=description)

        # Show count
        count = svc.count(name)
        console.print(f"[green]✓ Created view '{name}' ({count} books)[/green]")

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="list")
def view_list(
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    include_builtin: bool = typer.Option(True, "--builtin/--no-builtin", help="Include built-in views"),
):
    """
    List all views.

    Shows both user-defined views and built-in virtual views.

    Examples:
        ebk view list
        ebk view list --no-builtin
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        views = svc.list(include_builtin=include_builtin)

        if not views:
            console.print("[yellow]No views defined[/yellow]")
            lib.close()
            return

        table = Table(title="Views")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Books", justify="right", style="green")
        table.add_column("Type", style="dim")

        for v in views:
            count = v.get('count')
            count_str = str(count) if count is not None else "-"
            view_type = "built-in" if v.get('builtin') else "user"
            table.add_row(v['name'], v.get('description', ''), count_str, view_type)

        console.print(table)
        lib.close()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="show")
def view_show(
    name: str = typer.Argument(..., help="View name"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum books to show"),
    show_definition: bool = typer.Option(False, "--definition", help="Show YAML definition"),
):
    """
    Show books in a view.

    Examples:
        ebk view show favorites
        ebk view show programming --limit 50
        ebk view show my-view --definition
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        if show_definition:
            yaml_content = svc.export_yaml(name)
            console.print(f"[bold cyan]View: {name}[/bold cyan]\n")
            console.print(yaml_content)
            lib.close()
            return

        books = svc.evaluate(name)

        if not books:
            console.print(f"[yellow]View '{name}' is empty[/yellow]")
            lib.close()
            return

        console.print(f"[bold cyan]View: {name}[/bold cyan] ({len(books)} books)\n")

        table = Table()
        table.add_column("ID", style="dim", justify="right")
        table.add_column("Title", style="green")
        table.add_column("Authors", style="cyan")
        table.add_column("Modified", style="yellow", justify="center")

        for tb in books[:limit]:
            authors = ", ".join(a.name for a in tb.authors[:2])
            if len(tb.authors) > 2:
                authors += f" +{len(tb.authors) - 2}"

            # Mark overridden books
            modified = "*" if tb.title_override or tb.description_override else ""

            table.add_row(str(tb.id), tb.title[:60], authors, modified)

        console.print(table)

        if len(books) > limit:
            console.print(f"\n[dim]... and {len(books) - limit} more books[/dim]")

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="delete")
def view_delete(
    name: str = typer.Argument(..., help="View name"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """
    Delete a view.

    Examples:
        ebk view delete old-view
        ebk view delete old-view --force
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        view = svc.get(name)
        if not view:
            console.print(f"[red]View '{name}' not found[/red]")
            lib.close()
            raise typer.Exit(code=1)

        if not force:
            if not Confirm.ask(f"Delete view '{name}'?"):
                console.print("[yellow]Cancelled[/yellow]")
                lib.close()
                return

        svc.delete(name)
        console.print(f"[green]✓ Deleted view '{name}'[/green]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="add")
def view_add(
    name: str = typer.Argument(..., help="View name"),
    book_id: int = typer.Argument(..., help="Book ID to add"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
):
    """
    Add a book to a view.

    Examples:
        ebk view add favorites 42
        ebk view add my-collection 17
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        svc.add_book(name, book_id)
        console.print(f"[green]✓ Added book {book_id} to view '{name}'[/green]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="remove")
def view_remove(
    name: str = typer.Argument(..., help="View name"),
    book_id: int = typer.Argument(..., help="Book ID to remove"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
):
    """
    Remove a book from a view.

    Examples:
        ebk view remove favorites 42
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        svc.remove_book(name, book_id)
        console.print(f"[green]✓ Removed book {book_id} from view '{name}'[/green]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="set")
def view_set(
    name: str = typer.Argument(..., help="View name"),
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Override title"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Override description"),
    position: Optional[int] = typer.Option(None, "--position", "-p", help="Custom position for ordering"),
):
    """
    Set metadata overrides for a book within a view.

    Overrides are view-specific and non-destructive - the original
    book metadata is unchanged.

    Examples:
        ebk view set my-view 42 --title "Better Title"
        ebk view set my-view 42 --description "My notes about this book"
        ebk view set my-view 42 --position 1
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    if not any([title, description, position is not None]):
        console.print("[yellow]No overrides specified. Use --title, --description, or --position[/yellow]")
        raise typer.Exit(code=1)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        svc.set_override(name, book_id, title=title, description=description, position=position)
        console.print(f"[green]✓ Set override for book {book_id} in view '{name}'[/green]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="unset")
def view_unset(
    name: str = typer.Argument(..., help="View name"),
    book_id: int = typer.Argument(..., help="Book ID"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    field: Optional[str] = typer.Option(None, "--field", "-f", help="Specific field to unset (title, description, position)"),
):
    """
    Remove overrides for a book within a view.

    Examples:
        ebk view unset my-view 42                    # Remove all overrides
        ebk view unset my-view 42 --field title     # Remove only title override
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        if svc.unset_override(name, book_id, field=field):
            console.print(f"[green]✓ Removed override for book {book_id} in view '{name}'[/green]")
        else:
            console.print(f"[yellow]No override found for book {book_id} in view '{name}'[/yellow]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="export")
def view_export(
    name: str = typer.Argument(..., help="View name"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Export a view definition to YAML.

    Examples:
        ebk view export my-view                     # Print to stdout
        ebk view export my-view -o my-view.yaml    # Save to file
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        yaml_content = svc.export_yaml(name)

        if output:
            svc.export_file(name, output)
            console.print(f"[green]✓ Exported view '{name}' to {output}[/green]")
        else:
            console.print(yaml_content)

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="import")
def view_import(
    file_path: Path = typer.Argument(..., help="YAML file to import"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing view"),
):
    """
    Import a view definition from YAML.

    Examples:
        ebk view import my-view.yaml
        ebk view import my-view.yaml --overwrite
    """
    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        view = svc.import_file(file_path, overwrite=overwrite)
        count = svc.count(view.name)
        console.print(f"[green]✓ Imported view '{view.name}' ({count} books)[/green]")
        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


@view_app.command(name="edit")
def view_edit(
    name: str = typer.Argument(..., help="View name"),
    library_path: Optional[Path] = typer.Option(None, "--library", "-L", help="Path to library"),
):
    """
    Edit a view definition in your default editor.

    Opens the view's YAML definition in $EDITOR for editing.

    Examples:
        ebk view edit my-view
    """
    import tempfile
    import subprocess

    from .library_db import Library
    from .views import ViewService

    library_path = resolve_library_path(library_path)

    editor = os.environ.get('EDITOR', 'nano')

    try:
        lib = Library.open(library_path)
        svc = ViewService(lib.session)

        # Export current definition
        yaml_content = svc.export_yaml(name)

        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        # Open in editor
        result = subprocess.run([editor, temp_path])

        if result.returncode != 0:
            console.print(f"[red]Editor exited with error[/red]")
            os.unlink(temp_path)
            lib.close()
            raise typer.Exit(code=1)

        # Read edited content
        with open(temp_path) as f:
            new_content = f.read()

        os.unlink(temp_path)

        # Import if changed
        if new_content != yaml_content:
            svc.import_yaml(new_content, overwrite=True)
            count = svc.count(name)
            console.print(f"[green]✓ Updated view '{name}' ({count} books)[/green]")
        else:
            console.print("[yellow]No changes made[/yellow]")

        lib.close()

    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
