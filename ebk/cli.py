import os
import sys
import json
import shutil
from pathlib import Path
import logging
import re
from typing import List, Optional
import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.prompt import Confirm
from rich.traceback import install
from rich.table import Table
from rich import print_json as print_json_as_table
from rich.json import JSON

from .exports.hugo import export_hugo
from .exports.zip import export_zipfile
from .exports.jinja_export import JinjaExporter
from .imports import ebooks, calibre
from .merge import merge_libraries
from .utils import enumerate_ebooks, load_library, get_unique_filename, search_regex, search_jmes, get_library_statistics, get_index_by_unique_id, print_json_as_table
from .ident import add_unique_id
from .library import Library
from .decorators import handle_library_errors

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

app = typer.Typer()

@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose mode"),
):
    """
    ebk - A lightweight tool for managing eBook metadata.
    """
    if verbose:
        logger.setLevel(logging.DEBUG)
        console.print("[bold green]Verbose mode enabled.[/bold green]")

@app.command()
def import_zip(
    zip_file: str = typer.Argument(..., help="Path to the Zip file containing the ebk library"),
    output_dir: str = typer.Option(None, "--output-dir", "-o", help="Output directory for the ebk library (default: <zip_file>_ebk)"),
):
    """
    Import an ebk library from a Zip file.
    """
    output_dir = output_dir or f"{zip_file.rstrip('.zip')}"
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Importing Zip file...", total=None)
        try:
            if Path(output_dir).exists():
                output_dir = get_unique_filename(output_dir)
            with progress:
                shutil.unpack_archive(zip_file, output_dir)
            progress.update(task, description="[green]Zip file imported successfully!")
            logger.info(f"Zip file imported to {output_dir}")
        except Exception as e:
            progress.update(task, description="[red]Failed to import Zip file.")
            logger.error(f"Error importing Zip file: {e}")
        raise typer.Exit(code=1)
        

@app.command()
def import_calibre(
    calibre_dir: str = typer.Argument(..., help="Path to the Calibre library directory"),
    output_dir: str = typer.Option(None, "--output-dir", "-o", help="Output directory for the ebk library (default: <calibre_dir>_ebk)")
):
    """
    Import a Calibre library.

    Args:
        calibre_dir (str): Path to the Calibre library directory
        output_dir (str): Output directory for the ebk library (default: <calibre_dir>_ebk)
    """
    output_dir = output_dir or f"{calibre_dir.rstrip('/')}-ebk"
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Importing Calibre library...", total=None)
        try:
            # Create library with fluent API
            lib = Library.create(output_dir)
            
            # Import using the library's method (to be implemented)
            # For now, use the existing import function
            calibre.import_calibre(calibre_dir, output_dir)
            
            progress.update(task, description="[green]Calibre library imported successfully!")
            logger.info(f"Calibre library imported to {output_dir}")
        except Exception as e:
            progress.update(task, description="[red]Failed to import Calibre library.")
            logger.error(f"Error importing Calibre library: {e}")
        raise typer.Exit(code=1)


@app.command()
def import_ebooks(
    ebooks_dir: str = typer.Argument(..., help="Path to the directory containing ebook files"),
    output_dir: str = typer.Option(None, "--output-dir", "-o", help="Output directory for the ebk library (default: <ebooks_dir>_ebk)"),
    ebook_formats: List[str] = typer.Option(
        ["pdf", "epub", "mobi", "azw3", "txt", "markdown", "html", "docx", "rtf", "djvu", "fb2", "cbz", "cbr"],
        "--ebook-formats", "-f",
        help="List of ebook formats to import"
    )
):
    """
    Recursively import a directory of ebooks. The metadata will be inferred from the file.
    """
    output_dir = output_dir or f"{ebooks_dir.rstrip('/')}-ebk"
    with Progress(console=console) as progress:
        progress.add_task("[cyan]Importing raw ebooks...", total=None)
        try:
            # Create library with fluent API
            lib = Library.create(output_dir)
            
            # Import using the existing function for now
            ebooks.import_ebooks(ebooks_dir, output_dir, ebook_formats)
        except Exception as e:
            logger.error(f"Error importing raw ebooks: {e}")
        raise typer.Exit(code=1)

@app.command()
@handle_library_errors
def export(
    format: str = typer.Argument(..., help="Export format (e.g., 'hugo', 'zip')"),
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to export"),
    destination: Optional[str] = typer.Argument(None, help="Destination path"),
    organize_by: str = typer.Option("flat", "--organize-by", "-o", 
                                   help="For Hugo: organize by 'flat', 'year', 'language', 'subject', or 'creator'"),
    template_dir: Optional[str] = typer.Option(None, "--template-dir", "-t",
                                              help="Custom template directory for Jinja-based exports"),
    use_jinja: bool = typer.Option(False, "--jinja", "-j",
                                  help="Use Jinja2 template system for Hugo export")
):
    """
    Export the ebk library to the specified format.
    
    Formats:
    - zip: Create a ZIP archive of the library
    - hugo: Export for Hugo static site (supports --jinja for flexible layouts)
    
    Hugo organization options (with --jinja):
    - flat: All books in one directory (default)
    - year: Organize by publication year
    - language: Organize by language
    - subject: Organize by subject/tag
    - creator: Organize by author/creator
    """
    format = format.lower()
    
    lib = Library.open(lib_dir)
    
    if format == "zip":
        # Determine the destination filename
        if destination:
            dest_path = Path(destination)
            if dest_path.exists():
                console.print(f"[yellow]Destination '{destination}' already exists. Finding an available filename...[/yellow]")
                dest_str = get_unique_filename(destination)
                dest_path = Path(dest_str)
                console.print(f"[green]Using '{dest_path.name}' as the destination.[/green]")
        else:
            dest_str = get_unique_filename(lib_dir + ".zip")
            dest_path = Path(dest_str)
            console.print(f"[bold]No destination provided[/bold]. Using default [bold green]{dest_path.name}.[/bold green]")

        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Exporting to Zip...", total=None)
            try:
                lib.export_to_zip(str(dest_path))
                progress.update(task, description="[green]Exported to Zip successfully!")
                console.print(f"[bold green]Exported library to '{dest_path}'.[/bold green]")
            except Exception as e:
                progress.update(task, description="[red]Failed to export to Zip.")
                logger.error(f"Error exporting to Zip: {e}")
                console.print(f"[bold red]Failed to export to Zip: {e}[/bold red]")
            raise typer.Exit(code=1)
    
    elif format == "hugo":
        if not destination:
            console.print(f"[red]Destination directory is required for 'hugo' export format.[/red]")
        raise typer.Exit(code=1)
        
        dest_path = Path(destination)
        if not dest_path.exists():
            try:
                dest_path.mkdir(parents=True, exist_ok=True)
                console.print(f"[green]Created destination directory '{destination}'.[/green]")
            except Exception as e:
                console.print(f"[red]Failed to create destination directory '{destination}': {e}[/red]")
            raise typer.Exit(code=1)
        elif not dest_path.is_dir():
            console.print(f"[red]Destination '{destination}' exists and is not a directory.[/red]")
        raise typer.Exit(code=1)

        with Progress(console=console) as progress:
            if use_jinja:
                task = progress.add_task(f"[cyan]Exporting to Hugo with Jinja (organize by {organize_by})...", total=None)
                try:
                    lib.export_to_hugo(str(dest_path), organize_by=organize_by)
                    progress.update(task, description="[green]Exported to Hugo with Jinja successfully!")
                    logger.info(f"Library exported to Hugo at {dest_path} (organized by {organize_by})")
                    console.print(f"[bold green]Exported library to Hugo directory '{dest_path}' (organized by {organize_by}).[/bold green]")
                except Exception as e:
                    progress.update(task, description="[red]Failed to export to Hugo.")
                    logger.error(f"Error exporting to Hugo with Jinja: {e}")
                    console.print(f"[bold red]Failed to export to Hugo: {e}[/bold red]")
                raise typer.Exit(code=1)
            else:
                task = progress.add_task("[cyan]Exporting to Hugo (legacy)...", total=None)
                try:
                    # Use legacy export for non-jinja
                    export_hugo(str(lib.path), str(dest_path))
                    progress.update(task, description="[green]Exported to Hugo successfully!")
                    logger.info(f"Library exported to Hugo at {dest_path}")
                    console.print(f"[bold green]Exported library to Hugo directory '{dest_path}'.[/bold green]")
                    console.print("[yellow]Tip: Use --jinja for more flexible export options![/yellow]")
                except Exception as e:
                    progress.update(task, description="[red]Failed to export to Hugo.")
                    logger.error(f"Error exporting to Hugo: {e}")
                    console.print(f"[bold red]Failed to export to Hugo: {e}[/bold red]")
                raise typer.Exit(code=1)

    else:
        console.print(f"[red]Unsupported export format: '{format}'. Supported formats are 'zip' and 'hugo'.[/red]")
        raise typer.Exit(code=1)
    
@app.command()
def show_index(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to display"),
    indices: list[int] = typer.Argument(..., help="Index of the entry to display"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON")
):
    """
    Display the index of the ebk library.

    Args:
    lib_dir (str): Path to the ebk library directory to display
    index (int): Index of the entry to display


    Raises:
    typer.Exit: If the library directory is invalid or the index is out of range
    """
    try:
        lib = Library.open(lib_dir)
        
        # Use library's get_by_indices method with validation
        entries = lib.get_by_indices(indices)
        
        for entry in entries:
            if output_json:
                console.print_json(json.dumps(entry.to_dict(), indent=2))
            else:
                # Create a table
                table = Table(title="ebk Ebook Entry", show_lines=True)

                # Add column headers dynamically based on JSON keys
                data = entry.to_dict()
                columns = data.keys()
                for column in columns:
                    table.add_column(column, justify="center", style="bold cyan")

                # Add single row for this entry
                table.add_row(*(str(data[col]) for col in columns))

                # Print the table
                console.print(table)
    except IndexError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)



@app.command()
def about():
    """
    Display information about ebk.
    """
    
    console.print("[bold green]Welcome to ebk![/bold green]\n")
    console.print("A lightweight and efficient tool for managing eBook metadata.\n")
    console.print("[bold]Usage:[/bold]")
    console.print("  - Run [bold]ebk --help[/bold] for general help.")
    console.print("  - Use [bold]ebk <command> --help[/bold] for detailed command-specific help.\n")
    console.print("[bold]More Information:[/bold]")
    console.print("  📖 GitHub: [link=https://github.com/queelius/ebk]github.com/queelius/ebk[/link]")
    console.print("  🌐 Website: [link=https://metafunctor.com]metafunctor.com[/link]")
    console.print("  📧 Contact: [link=mailto:lex@metafunctor.com]lex@metafunctor.com[/link]\n")
    console.print("Developed by [bold]Alex Towell[/bold]. Enjoy using ebk! 🚀")
    
@app.command()
def merge(
    operation: str = typer.Argument(..., help="Set-theoretic operation to apply (union, intersect, diff, symdiff)"),
    output_dir: str = typer.Argument(..., help="Output directory for the merged ebk library"),
    libs: List[str] = typer.Argument(..., help="Paths to the source ebk library directories", min=2)
):
    """
    Merge multiple ebk libraries using set-theoretic operations.

    Args:
        operation (str): Set-theoretic operation to apply (union, intersect, diff, symdiff)
        output_dir (str): Output directory for the merged ebk library
        libs (List[str]): Paths to the source ebk library directories

    Raises:
        typer.Exit: If the library directory is invalid or the index is out of range
    
    Output:
        Merges the specified libraries using the set-theoretic operation and saves the result in the output directory.
    """
    with Progress(console=console) as progress:
        task = progress.add_task(f"[cyan]Merging libraries with operation '{operation}'...", total=None)
        try:
            # Load first library
            merged = Library.open(libs[0])
            
            # Apply operation with remaining libraries
            for lib_path in libs[1:]:
                other = Library.open(lib_path)
                if operation == "union":
                    merged = merged.union(other)
                elif operation == "intersect":
                    merged = merged.intersect(other)
                elif operation == "diff":
                    merged = merged.difference(other)
                elif operation == "symdiff":
                    merged = merged.merge(other, operation="symdiff")
                else:
                    raise ValueError(f"Unknown operation: {operation}")
            
            # Save to output directory
            output = Library.create(output_dir)
            output._entries = merged._entries
            output.save()
            
            # Copy files from merged entries
            for entry in output._entries:
                # Find source library containing this entry
                for lib_path in libs:
                    src_lib = Library.open(lib_path)
                    if any(e.get("unique_id") == entry.get("unique_id") for e in src_lib._entries):
                        # Copy files from this library
                        for file_path in entry.get("file_paths", []):
                            src_file = src_lib.path / file_path
                            if src_file.exists():
                                shutil.copy2(src_file, output.path / file_path)
                        if entry.get("cover_path"):
                            src_cover = src_lib.path / entry["cover_path"]
                            if src_cover.exists():
                                shutil.copy2(src_cover, output.path / entry["cover_path"])
                        break
            
            progress.update(task, description=f"[green]Libraries merged into {output_dir}")
            console.print(f"[bold green]Libraries merged with operation '{operation}' into {output_dir}[/bold green]")
        except Exception as e:
            progress.update(task, description="[red]Failed to merge libraries.")
            logger.error(f"Error merging libraries: {e}")
            console.print(f"[bold red]Failed to merge libraries: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
@handle_library_errors
def stats(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to get stats"),
    keywords: List[str] = typer.Option(
        ["python", "data", "machine learning"],
        "--keywords",
        "-k",
        help="Keywords to search for in titles"
    )
):
    """
    Get statistics about the ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory to get stats
        keywords (List[str]): Keywords to search for in titles

    Raises:
        typer.Exit: If the library directory is invalid
    
    Output:
        Prints the statistics about the library.
    """
    lib = Library.open(lib_dir)
    stats = lib.stats()
    
    # Add keyword counts
    keyword_counts = {}
    for keyword in keywords:
        count = len(lib.search(keyword, fields=["title"]))
        keyword_counts[keyword] = count
    stats["keyword_counts"] = keyword_counts
    
    console.print_json(json.dumps(stats, indent=2))
    
@app.command()
@handle_library_errors
def list_indices(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to list"),
    indices: List[int] = typer.Argument(..., help="Indices of entries to list"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed information")):
    """
    List the entries in the ebk library directory by index.

    Args:
        lib_dir (str): Path to the ebk library directory to list
        indices (List[int]): Indices of entries to list
        output_json (bool): Output as JSON
        detailed (bool): Show detailed information

    Raises:
        typer.Exit: If the library directory is invalid or the index is out of range
    
    Output:
        Prints the list of entries in the library directory.
    """
    lib = Library.open(lib_dir)

    try:
        # Use library's get_by_indices method with validation
        entries = lib.get_by_indices(indices)

        if output_json:
            data = [e.to_dict() for e in entries]
            console.print_json(json.dumps(data, indent=2))
        else:
            # Convert to legacy format for enumerate_ebooks
            entry_data = [e._data for e in entries]
            enumerate_ebooks(entry_data, lib.path, indices, detailed)
    except IndexError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def list(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to list"),
    output_json: bool = typer.Option(False, "--json", "-j",  help="Output as JSON")):
    """
    List the entries in the ebk library directory.

    Args:
        lib_dir (str): Path to the ebk library directory to list
        output_json (bool): Output as JSON

    Raises:
        typer.Exit: If the library directory is invalid
    
    Output:
        Prints the list of entries in the library directory.
    """
    
    lib = Library.open(lib_dir)
    if output_json:
        # Use to_dict() for proper serialization
        data = [entry.to_dict() for entry in lib]
        console.print_json(json.dumps(data, indent=2))
    else:
        # Use internal _entries for legacy enumerate_ebooks function
        enumerate_ebooks(lib._entries, lib.path)


@app.command()
@handle_library_errors
def add(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    json_file: str = typer.Option(None, "--json", help="JSON file containing entry info to add"),
    title: str = typer.Option(None, "--title", help="Title of the entry to add"),
    creators: List[str] = typer.Option(None, "--creators", help="Creators of the entry to add"),
    ebooks: List[str] = typer.Option(None, "--ebooks", help="Paths to the ebook files to add"),
    cover: str = typer.Option(None, "--cover", help="Path to the cover image to add")
):
    """
    Add entries to the ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        json_file (str): Path to a JSON file containing entry info to add
        title (str): Title of the entry to add
        creators (List[str]): Creators of the entry to add
        ebooks (List[str]): Paths to the ebook files to add
        cover (str): Path to the cover image to add

    Raises:
        typer.Exit: If the library directory is invalid or the entry is invalid
    
    Output:
        Adds the specified entry to the library and updates the metadata file in-place.
    """
    lib = Library.open(lib_dir)
    console.print(f"Loaded [bold]{len(lib)}[/bold] entries from [green]{lib_dir}[/green]")
    
    if json_file:
        with open(json_file, "r") as f:
            new_entries = json.load(f)
        lib.add_entries(new_entries)
        console.print(f"[green]Added {len(new_entries)} entries from {json_file}[/green]")
    else:
        if not title or not creators:
            console.print("[red]Title and creators are required when not using a JSON file.[/red]")
        raise typer.Exit(code=1)
        
        # Copy files first if provided
        file_paths = []
        cover_path = None
        
        with Progress(console=console) as progress:
            if ebooks:
                task = progress.add_task("[cyan]Copying ebook files...", total=len(ebooks))
                for ebook in ebooks:
                    filename = Path(ebook).name
                    dest_path = Path(lib_dir) / filename
                    shutil.copy(ebook, dest_path)
                    file_paths.append(filename)
                    progress.advance(task)
                    logger.debug(f"Copied ebook file: {ebook}")
                    
            if cover:
                task = progress.add_task("[cyan]Copying cover image...", total=1)
                cover_filename = Path(cover).name
                cover_dest = Path(lib_dir) / cover_filename
                shutil.copy(cover, cover_dest)
                cover_path = cover_filename
                progress.advance(task)
                logger.debug(f"Copied cover image: {cover}")
        
        entry = lib.add_entry(
            title=title,
            creators=creators,
            file_paths=file_paths,
            cover_path=cover_path
        )
        console.print(f"Adding new entry: [bold]{entry.title}[/bold]")
    
    lib.save()
    console.print(f"[bold green]Successfully added entries to the library.[/bold green]")
    


@app.command()
@handle_library_errors
def remove(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    regex: str = typer.Argument(..., help="Regex search expression to remove entries"),
    force: bool = typer.Option(False, "--force", help="Force removal without confirmation"),
    apply_to: List[str] = typer.Option(
        ["title"],
        "--apply-to",
        help="Apply the removal to ebooks, covers, or all files",
        show_default=True
    )
):
    """
    Remove entries from the ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        regex (str): Regex search expression to remove entries
        force (bool): Force removal without confirmation
        apply_to (List[str]): Apply the removal to ebooks, covers, or all files

    Raises:
        typer.Exit: If the library directory is invalid or the index is out of range
    
    Output:
        Removed entries from the library directory and associated files in-place.
    """
    lib = Library.open(lib_dir)
    console.print(f"Loaded [bold]{len(lib)}[/bold] entries from [green]{lib_dir}[/green]")
    
    # Find matching entries
    matches = []
    for field in apply_to:
        results = lib.search(regex, fields=[field])
        matches.extend(results)
    
    # Remove duplicates by unique_id
    seen_ids = set()
    unique_matches = []
    for entry in matches:
        if entry.id not in seen_ids:
            seen_ids.add(entry.id)
            unique_matches.append(entry)
    
    if not unique_matches:
        console.print("[yellow]No matching entries found for removal.[/yellow]")
        return
    
    console.print(f"[yellow]Found {len(unique_matches)} entries matching the regex '{regex}':[/yellow]")
    enumerate_ebooks([e._data for e in unique_matches], lib.path)
    
    if not force:
        confirm = Confirm.ask(f"[bold red]Are you sure you want to remove {len(unique_matches)} entries?[/bold red]")
        if not confirm:
            console.print("[green]Removal cancelled.[/green]")
            return
    
    # Remove associated files and entries
    for entry in unique_matches:
        # Remove ebook files
        for file_path in entry.get('file_paths', []):
            full_path = lib.path / file_path
            if full_path.exists():
                full_path.unlink()
                logger.info(f"Removed ebook file: {full_path}")
        
        # Remove cover image
        if entry.get('cover_path'):
            cover_path = lib.path / entry.get('cover_path')
            if cover_path.exists():
                cover_path.unlink()
                logger.info(f"Removed cover image: {cover_path}")
        
        # Remove from library
        lib.remove(entry.id)
    
    lib.save()
    console.print(f"[bold green]Removed {len(unique_matches)} entries from the library.[/bold green]")
    


@app.command()
@handle_library_errors
def remove_index(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    indices: List[int] = typer.Argument(..., help="Indices of entries to remove")
):
    """
    Remove entries from the ebk library by index.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        indices (List[int]): Indices of entries to remove

    Raises:
        typer.Exit: If the library directory is invalid or the index is out of range
    
    Output:
        Removes the specified entries from the library.
    """
    lib = Library.open(lib_dir)
    
    # Validate indices
    total_books = len(lib)
    for index in indices:
        if index < 0 or index >= total_books:
            console.print(f"[red]Index {index} is out of range (0-{total_books - 1}).[/red]")
        raise typer.Exit(code=1)
    
    # Get entries to remove
    entries_to_remove = [lib[i] for i in indices]
    
    console.print(f"[yellow]Removing {len(entries_to_remove)} entries:[/yellow]")
    for entry in entries_to_remove:
        console.print(f"  - {entry.title}")
    
    # Remove files and entries
    for entry in entries_to_remove:
        # Remove ebook files
        for file_path in entry.get('file_paths', []):
            full_path = lib.path / file_path
            if full_path.exists():
                full_path.unlink()
        
        # Remove cover image
        if entry.get('cover_path'):
            cover_path = lib.path / entry.get('cover_path')
            if cover_path.exists():
                cover_path.unlink()
        
        # Remove from library
        lib.remove(entry.id)
    
    lib.save()
    console.print(f"[bold green]Removed {len(entries_to_remove)} entries.[/bold green]")
    


@app.command()
@handle_library_errors
def remove_id(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    unique_id: str = typer.Argument(..., help="Unique ID of the entry to remove")
):
    """
    Remove an entry from the ebk library by unique ID.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        unique_id (str): Unique ID of the entry to remove

    Raises:
        typer.Exit: If the library directory is invalid or the ID is not found
    
    Output:
        Removes the specified entry from the library.
    """
    lib = Library.open(lib_dir)
    
    # Find entry with unique ID
    entry_to_remove = lib.find(unique_id)
    
    if not entry_to_remove:
        console.print(f"[red]No entry found with unique ID: {unique_id}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[yellow]Removing entry: {entry_to_remove.title}[/yellow]")
    
    # Remove files
    for file_path in entry_to_remove.get('file_paths', []):
        full_path = lib.path / file_path
        if full_path.exists():
            full_path.unlink()
    
    if entry_to_remove.get('cover_path'):
        cover_path = lib.path / entry_to_remove.get('cover_path')
        if cover_path.exists():
            cover_path.unlink()
    
    # Remove from library
    lib.remove(unique_id)
    lib.save()
    
    console.print(f"[bold green]Removed entry with ID: {unique_id}[/bold green]")
    


@app.command()
@handle_library_errors
def update_index(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    index: int = typer.Argument(..., help="Index of the entry to update"),
    title: str = typer.Option(None, "--title", help="New title"),
    creators: List[str] = typer.Option(None, "--creators", help="New creators"),
    ebooks: List[str] = typer.Option(None, "--ebooks", help="New ebook file paths"),
    cover: str = typer.Option(None, "--cover", help="New cover image path")
):
    """
    Update an entry in the ebk library by index.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        index (int): Index of the entry to update
        title (str): New title
        creators (List[str]): New creators
        ebooks (List[str]): New ebook file paths
        cover (str): New cover image path

    Raises:
        typer.Exit: If the library directory is invalid or the index is out of range
    
    Output:
        Updates the specified entry in the library.
    """
    lib = Library.open(lib_dir)
    
    total_books = len(lib)
    if index < 0 or index >= total_books:
        console.print(f"[red]Index {index} is out of range (0-{total_books - 1}).[/red]")
        raise typer.Exit(code=1)
    
    entry = lib[index]
    
    # Update fields if provided
    if title:
        entry.title = title
    if creators:
        entry.creators = creators
    if ebooks:
        entry.set("file_paths", ebooks)
    if cover:
        entry.set("cover_path", cover)
    
    lib.save()
    console.print(f"[bold green]Updated entry at index {index}.[/bold green]")
    


@app.command()
@handle_library_errors
def update_id(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    unique_id: str = typer.Argument(..., help="Unique ID of the entry to update"),
    title: str = typer.Option(None, "--title", help="New title"),
    creators: List[str] = typer.Option(None, "--creators", help="New creators"),
    ebooks: List[str] = typer.Option(None, "--ebooks", help="New ebook file paths"),
    cover: str = typer.Option(None, "--cover", help="New cover image path")
):
    """
    Update an entry in the ebk library by unique ID.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        unique_id (str): Unique ID of the entry to update
        title (str): New title
        creators (List[str]): New creators
        ebooks (List[str]): New ebook file paths
        cover (str): New cover image path

    Raises:
        typer.Exit: If the library directory is invalid or the ID is not found
    
    Output:
        Updates the specified entry in the library.
    """
    lib = Library.open(lib_dir)
    
    # Find entry
    entry = lib.find(unique_id)
    if not entry:
        console.print(f"[red]No entry found with unique ID: {unique_id}[/red]")
        raise typer.Exit(code=1)
    
    # Update fields if provided
    if title:
        entry.title = title
    if creators:
        entry.creators = creators
    if ebooks:
        entry.set("file_paths", ebooks)
    if cover:
        entry.set("cover_path", cover)
    
    lib.save()
    console.print(f"[bold green]Updated entry with ID: {unique_id}[/bold green]")
    


@app.command()
@handle_library_errors
def search(
    expression: str = typer.Argument(..., help="Search expression (regex or JMESPath)"),
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to search"),
    jmespath: bool = typer.Option(False, "--jmespath", help="Use JMESPath query instead of regex"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    regex_fields: List[str] = typer.Option(
        ["title"],
        "--regex-fields",
        help="Fields to apply regex search to",
        show_default=True
    )
):
    """
    Search the ebk library using regex or JMESPath.

    Args:
        expression (str): Search expression (regex or JMESPath)
        lib_dir (str): Path to the ebk library directory to search
        jmespath (bool): Use JMESPath query instead of regex
        output_json (bool): Output as JSON
        regex_fields (List[str]): Fields to apply regex search to (for regex mode)

    Raises:
        typer.Exit: If the library directory is invalid
    
    Output:
        Displays matching entries from the library.
    """
    lib = Library.open(lib_dir)
    
    if jmespath:
        # Use JMESPath query
        results = lib.query().jmespath(expression).execute()
    else:
        # Use simple search for regex across fields
        results = lib.search(expression, fields=regex_fields)
        # Convert Entry objects to dicts for compatibility
        results = [entry._data for entry in results]
    
    if not results:
        console.print(f"[yellow]No entries found matching '{expression}'.[/yellow]")
        return
    
    console.print(f"[green]Found {len(results)} matching entries.[/green]")
    
    if output_json:
        console.print_json(json.dumps(results, indent=2))
    else:
        enumerate_ebooks(results, lib.path)
    




@app.command()
@handle_library_errors
def export_dag(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    output_dir: str = typer.Argument(..., help="Output directory for the symlink DAG structure"),
    tag_field: str = typer.Option("subjects", "--tag-field", "-t", help="Field to use for tags (e.g., subjects, creators)"),
    include_files: bool = typer.Option(False, "--copy-files/--no-copy", help="Copy actual ebook files (default: no-copy)"),
    create_index: bool = typer.Option(True, "--create-index/--no-index", help="Create HTML index files"),
    flatten: bool = typer.Option(False, "--flatten", help="Create direct symlinks to files instead of _books structure"),
    min_books: int = typer.Option(0, "--min-books", "-m", help="Minimum books per tag folder (smaller tags go to _misc)")
):
    """
    Export library as a navigable directory structure using symlinks.
    
    This creates a filesystem view where:
    - Tags become directories in a hierarchy
    - Books appear in relevant tag directories via symlinks
    - The DAG structure of hierarchical tags is preserved
    
    Example:
        ebk export-dag /path/to/library /path/to/output
        
    With hierarchical tags like "Programming/Python/Web", creates:
        Programming/
          Python/
            Web/
              (books tagged with Programming/Python/Web)
            (books tagged with Programming/Python)
          (books tagged with Programming)
    """
    lib = Library.open(lib_dir)
    
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Creating symlink DAG structure...", total=None)
        
        lib.export_to_symlink_dag(
            output_dir,
            tag_field=tag_field,
            include_files=include_files,
            create_index=create_index,
            flatten=flatten,
            min_books=min_books
        )
        
        progress.update(task, description="[green]Symlink DAG created successfully!")
        
    console.print(f"[bold green]Created navigable library structure at: {output_dir}[/bold green]")
    console.print(f"\n[yellow]You can now:[/yellow]")
    console.print(f"  • Navigate with your file explorer")
    console.print(f"  • Use command line: cd {output_dir}")
    if create_index:
        console.print(f"  • Open in browser: file://{Path(output_dir).absolute()}/index.html")
    



@app.command()
@handle_library_errors
def export_multi(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    output_dir: str = typer.Argument(..., help="Output directory for the multi-faceted view"),
    facets: Optional[List[str]] = typer.Option(
        None, "--facet", "-f", 
        help="Facets to include (format: 'DisplayName:field'), e.g., 'Authors:creators'"
    ),
    include_files: bool = typer.Option(False, "--copy-files/--no-copy", help="Copy actual ebook files (default: no-copy)"),
    create_index: bool = typer.Option(True, "--create-index/--no-index", help="Create HTML index file")
):
    """
    Export library with multi-faceted navigation interface.
    
    Creates a modern web interface with:
    - Sidebar navigation for multiple facets (subjects, authors, etc.)
    - Real-time search and filtering
    - Pagination for large libraries
    - Grid and list views
    
    Example:
        ebk export-multi /path/to/library /path/to/output
        
        # Custom facets
        ebk export-multi library/ output/ -f "Topics:subjects" -f "Writers:creators" -f "Years:date"
    """
    try:
        # Parse custom facets if provided
        custom_facets = None
        if facets:
            custom_facets = {}
            for facet in facets:
                if ':' in facet:
                    display_name, field_name = facet.split(':', 1)
                    custom_facets[display_name] = field_name
                else:
                    console.print(f"[yellow]Warning: Invalid facet format '{facet}', skipping[/yellow]")
        
        # Import here to avoid circular imports
        from ebk.exports.multi_facet_export import MultiFacetExporter
        
        lib = Library.open(lib_dir)
        
        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Creating multi-faceted export...", total=None)
            
            exporter = MultiFacetExporter(facets=custom_facets)
            exporter.export(
                Path(lib_dir),
                Path(output_dir),
                include_files=include_files,
                create_index=create_index
            )
            
            progress.update(task, description="[green]Multi-faceted export created successfully!")
            
        console.print(f"[bold green]Created multi-faceted view at: {output_dir}[/bold green]")
        console.print(f"\n[yellow]You can now:[/yellow]")
        console.print(f"  • Open in browser: file://{Path(output_dir).absolute()}/index.html")
        console.print(f"  • Navigate by subjects, authors, and more")
        console.print(f"  • Search and filter in real-time")
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error creating multi-faceted export: {e}")
        console.print(f"[bold red]Failed to create export: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
@handle_library_errors
def rate(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    entry_id: str = typer.Argument(..., help="Entry ID or title pattern to rate"),
    rating: float = typer.Argument(..., help="Rating (0-5 stars)"),
):
    """Rate a book in your library."""
    lib = Library.open(lib_dir)
    
    # Find entry by ID or title
    entry = lib.get(entry_id)
    if not entry:
        # Try to find by title pattern
        results = lib.query().where_title_contains(entry_id).execute()
        if not results:
            console.print(f"[red]No entry found matching '{entry_id}'[/red]")
            raise typer.Exit(code=1)
        elif len(results) > 1:
            console.print(f"[yellow]Multiple entries found:[/yellow]")
            for e in results[:5]:
                console.print(f"  • {e['unique_id']}: {e.get('title', 'Unknown')}")
            console.print("[yellow]Please use a more specific ID[/yellow]")
            raise typer.Exit(code=1)
        entry = Entry(results[0], lib)
    
    entry.rate(rating)
    console.print(f"[green]✓[/green] Rated '{entry.title}' with {rating} stars")


@app.command()
@handle_library_errors
def comment(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    entry_id: str = typer.Argument(..., help="Entry ID or title pattern"),
    text: str = typer.Argument(..., help="Comment text"),
):
    """Add a comment to a book."""
    lib = Library.open(lib_dir)

    # Find entry
    entry = lib.get(entry_id)
    if not entry:
        results = lib.query().where_title_contains(entry_id).execute()
        if not results:
            console.print(f"[red]No entry found matching '{entry_id}'[/red]")
            raise typer.Exit(code=1)
        elif len(results) > 1:
            console.print(f"[yellow]Multiple entries found. Please be more specific.[/yellow]")
            raise typer.Exit(code=1)
        entry = Entry(results[0], lib)

    entry.comment(text)
    console.print(f"[green]✓[/green] Added comment to '{entry.title}'")


@app.command()
@handle_library_errors
def mark(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    entry_id: str = typer.Argument(..., help="Entry ID or title pattern"),
    status: str = typer.Argument(..., help="Status: read, reading, unread, abandoned"),
    progress: Optional[int] = typer.Option(None, "--progress", "-p", help="Reading progress (0-100)"),
):
    """Mark reading status of a book."""
    lib = Library.open(lib_dir)

    # Find entry
    entry = lib.get(entry_id)
    if not entry:
        results = lib.query().where_title_contains(entry_id).execute()
        if not results:
            console.print(f"[red]No entry found matching '{entry_id}'[/red]")
            raise typer.Exit(code=1)
        elif len(results) > 1:
            console.print(f"[yellow]Multiple entries found. Please be more specific.[/yellow]")
            raise typer.Exit(code=1)
        entry = Entry(results[0], lib)
    
    # Apply status
    if status == "read":
        entry.mark_read(progress)
    elif status == "reading":
        entry.mark_reading(progress)
    elif status == "unread":
        entry.mark_unread()
    elif status == "abandoned":
        entry.mark_abandoned(progress)
    else:
        console.print(f"[red]Invalid status: {status}[/red]")
        console.print("Valid statuses: read, reading, unread, abandoned")
        raise typer.Exit(code=1)
    
    progress_str = f" ({progress}%)" if progress is not None else ""
    console.print(f"[green]✓[/green] Marked '{entry.title}' as {status}{progress_str}")


@app.command()
@handle_library_errors
def personal_stats(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
):
    """Show personal library statistics."""
    lib = Library.open(lib_dir)
    stats = lib.personal.get_statistics()
    
    console.print("[bold]Personal Library Statistics[/bold]\n")
    
    # Reading status
    total_tracked = (stats["total_read"] + stats["total_reading"] + 
                    stats["total_unread"] + stats["total_abandoned"])
    
    if total_tracked > 0:
        console.print("[cyan]Reading Status:[/cyan]")
        console.print(f"  📚 Read: {stats['total_read']}")
        console.print(f"  📖 Currently Reading: {stats['total_reading']}")
        console.print(f"  📘 Unread: {stats['total_unread']}")
        console.print(f"  ❌ Abandoned: {stats['total_abandoned']}")
        console.print()
    
    # Ratings
    if stats["total_rated"] > 0:
        console.print("[cyan]Ratings:[/cyan]")
        console.print(f"  ⭐ Average Rating: {stats['average_rating']:.1f}")
        console.print(f"  📊 Total Rated: {stats['total_rated']}")
        console.print("  Distribution:")
        for stars in range(5, 0, -1):
            count = stats["rating_distribution"].get(stars, 0)
            bar = "█" * (count // 5) if count > 0 else ""
            console.print(f"    {stars}⭐ {count:3d} {bar}")
        console.print()
    
    # Other metadata
    console.print("[cyan]Other:[/cyan]")
    console.print(f"  ❤️  Favorites: {stats['total_favorites']}")
    console.print(f"  💬 With Comments: {stats['total_with_comments']}")
    console.print(f"  🏷️  With Personal Tags: {stats['total_with_tags']}")


@app.command()
@handle_library_errors
def recommend(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    based_on: Optional[List[str]] = typer.Option(None, "--based-on", "-b", help="Book IDs to base recommendations on"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of recommendations"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON")
):
    """
    Get book recommendations based on similarity.
    
    Examples:
    # Random recommendations from highly-rated books
    ebk recommend /path/to/library
    
    # Recommendations based on specific books
    ebk recommend /path/to/library --based-on book_id_1 --based-on book_id_2
    """
    lib = Library.open(lib_dir)

    recommendations = lib.recommend(based_on=based_on, limit=limit)
    
    if not recommendations:
        console.print("[yellow]No recommendations found.[/yellow]")
        return
    
    console.print(f"[green]Found {len(recommendations)} recommendations:[/green]\n")
    
    if output_json:
        data = [r.to_dict() for r in recommendations]
        console.print_json(json.dumps(data, indent=2))
    else:
        for i, entry in enumerate(recommendations, 1):
            console.print(f"[bold]{i}. {entry.title}[/bold]")
            if entry.creators:
                console.print(f"   by {', '.join(entry.creators)}")
            if entry.subjects:
                console.print(f"   Tags: {', '.join(entry.subjects[:5])}")
            console.print()
    



@app.command()
@handle_library_errors
def similar(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    entry_id: str = typer.Argument(..., help="Entry ID to find similar books for"),
    threshold: float = typer.Option(0.7, "--threshold", "-t", help="Similarity threshold (0-1)"),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of results"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON")
):
    """
    Find books similar to a given entry.
    
    Similarity is based on:
    - Shared subjects/tags (40% weight)
    - Shared authors (30% weight)  
    - Same language (20% weight)
    - Title similarity (10% weight)
    """
    lib = Library.open(lib_dir)
    
    # Find the reference entry
    ref_entry = lib.find(entry_id)
    if not ref_entry:
        console.print(f"[red]No entry found with ID: {entry_id}[/red]")
        raise typer.Exit(code=1)
    
    console.print(f"[cyan]Finding books similar to:[/cyan] {ref_entry.title}\n")
    
    similar_entries = lib.find_similar(entry_id, threshold=threshold)
    similar_entries = similar_entries[:limit]
    
    if not similar_entries:
        console.print(f"[yellow]No similar entries found with threshold {threshold}.[/yellow]")
        console.print("Try lowering the threshold with --threshold 0.5")
        return
    
    console.print(f"[green]Found {len(similar_entries)} similar books:[/green]\n")
    
    if output_json:
        data = [e.to_dict() for e in similar_entries]
        console.print_json(json.dumps(data, indent=2))
    else:
        for i, entry in enumerate(similar_entries, 1):
            console.print(f"[bold]{i}. {entry.title}[/bold]")
            if entry.creators:
                console.print(f"   by {', '.join(entry.creators)}")
            if entry.subjects:
                console.print(f"   Tags: {', '.join(entry.subjects[:5])}")
            console.print()
    



@app.command()
@handle_library_errors
def build_knowledge(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    book_ids: Optional[List[str]] = typer.Option(None, "--book", "-b", help="Specific book IDs to process"),
    force: bool = typer.Option(False, "--force", "-f", help="Force rebuild even if graph exists"),
    extract_concepts: bool = typer.Option(True, "--concepts/--no-concepts", help="Extract concepts from books"),
    build_relations: bool = typer.Option(True, "--relations/--no-relations", help="Build concept relations"),
):
    """
    Build a knowledge graph from your library.

    Extracts concepts, ideas, and relationships from all books in your library
    and builds a connected knowledge graph for intelligent searching.

    Examples:
    # Build knowledge graph for entire library
    ebk build-knowledge /path/to/library

    # Build for specific books only
    ebk build-knowledge /path/to/library --book book_id_1 --book book_id_2

    # Force rebuild
    ebk build-knowledge /path/to/library --force
    """
    from .ai.knowledge_graph import KnowledgeGraph
    from .ai.text_extractor import TextExtractor

    console.print("[cyan]Building knowledge graph...[/cyan]")

    # Initialize components
    kg = KnowledgeGraph(Path(lib_dir))
    extractor = TextExtractor()

    # Check if graph exists
    if kg.concepts and not force:
        console.print(f"[yellow]Knowledge graph already exists with {len(kg.concepts)} concepts.[/yellow]")
        if not Confirm.ask("Do you want to rebuild?"):
            return

    # Load library
    lib = Library.open(lib_dir)
    entries = lib.entries

    # Filter by book IDs if specified
    if book_ids:
        entries = [e for e in entries if e.unique_id in book_ids]
        console.print(f"Processing {len(entries)} specified books...")
    else:
        console.print(f"Processing {len(entries)} books in library...")

    with Progress() as progress:
        task = progress.add_task("[green]Extracting concepts...", total=len(entries))

        for entry in entries:
            # Get the first ebook file
            if not entry.file_paths:
                progress.advance(task)
                continue

            file_path = Path(lib_dir) / entry.file_paths[0]
            if not file_path.exists():
                progress.advance(task)
                continue

            try:
                # Extract key passages and concepts
                if extract_concepts:
                    passages = extractor.extract_key_passages(file_path)
                    for passage in passages[:20]:  # Top 20 passages per book
                        kg.add_concept(
                            name=f"Key idea from {entry.title[:30]}",
                            description=passage['sentence'],
                            book_id=entry.unique_id,
                            page=passage.get('page'),
                            quote=passage['context']
                        )

                # Extract definitions
                definitions = extractor.extract_definitions(file_path)
                for defn in definitions[:10]:  # Top 10 definitions per book
                    kg.add_concept(
                        name=defn['term'],
                        description=defn['definition'],
                        book_id=entry.unique_id
                    )

            except Exception as e:
                logger.warning(f"Failed to process {entry.title}: {e}")

            progress.advance(task)

    # Calculate importance scores
    kg.calculate_concept_importance()

    # Save the graph
    kg.save_graph()

    console.print(f"[green]✓ Knowledge graph built successfully![/green]")
    console.print(f"  - Total concepts: {len(kg.concepts)}")
    console.print(f"  - Total relations: {kg.graph.number_of_edges()}")
    console.print(f"  - Books indexed: {len(kg.book_concepts)}")


@app.command()
@handle_library_errors
def ask(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    query: str = typer.Argument(..., help="Your question about the library"),
    use_graph: bool = typer.Option(True, "--graph/--no-graph", help="Use knowledge graph"),
    use_semantic: bool = typer.Option(True, "--semantic/--no-semantic", help="Use semantic search"),
    max_results: int = typer.Option(5, "--max", "-n", help="Maximum number of results"),
):
    """
    Ask questions about your library using AI.

    Uses knowledge graph and semantic search to find answers from your books.

    Examples:
    # Ask about a topic
    ebk ask /path/to/library "What do my books say about habit formation?"

    # Ask for connections
    ebk ask /path/to/library "How does stoicism relate to modern psychology?"

    # Find specific information
    ebk ask /path/to/library "What are the key principles of machine learning?"
    """
    from .ai.knowledge_graph import KnowledgeGraph
    from .ai.semantic_search import SemanticSearch

    results = []

    # Use knowledge graph
    if use_graph:
        kg = KnowledgeGraph(Path(lib_dir))
        if kg.concepts:
            console.print("[cyan]Searching knowledge graph...[/cyan]")

            # Find relevant concepts
            keywords = query.lower().split()
            relevant_concepts = []

            for keyword in keywords:
                for concept_id in kg.concept_index.get(keyword, []):
                    concept = kg.concepts[concept_id]
                    relevant_concepts.append(concept)

            # Sort by importance
            relevant_concepts.sort(key=lambda c: c.importance_score, reverse=True)

            for concept in relevant_concepts[:max_results]:
                results.append({
                    'source': 'Knowledge Graph',
                    'concept': concept.name,
                    'description': concept.description,
                    'books': concept.source_books[:3]
                })

    # Use semantic search
    if use_semantic:
        search = SemanticSearch(Path(lib_dir))
        console.print("[cyan]Performing semantic search...[/cyan]")

        semantic_results = search.search_library(query, top_k=max_results)

        for result in semantic_results:
            results.append({
                'source': 'Semantic Search',
                'text': result['text'][:200] + '...',
                'similarity': f"{result['similarity']:.2f}",
                'book_id': result['book_id']
            })

    # Display results
    if not results:
        console.print("[yellow]No relevant information found. Try building the knowledge graph first.[/yellow]")
        console.print("Run: ebk build-knowledge /path/to/library")
        return

    console.print(f"\n[green]Found {len(results)} relevant results:[/green]\n")

    for i, result in enumerate(results, 1):
        console.print(f"[bold]{i}. [{result['source']}][/bold]")
        if 'concept' in result:
            console.print(f"   Concept: {result['concept']}")
            console.print(f"   {result['description']}")
        else:
            console.print(f"   {result['text']}")
        if 'book_id' in result:
            console.print(f"   From: {result['book_id']}")
        console.print()


@app.command()
@handle_library_errors
def learning_path(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    start_topic: str = typer.Argument(..., help="Starting topic/concept"),
    end_topic: str = typer.Argument(..., help="Goal topic/concept to understand"),
    max_steps: int = typer.Option(10, "--max-steps", "-n", help="Maximum books in path"),
):
    """
    Generate a personalized learning path between topics.

    Creates a reading sequence that bridges from your current knowledge
    to your learning goal using books in your library.

    Examples:
    # Learn quantum computing starting from basic math
    ebk learning-path /path/to/library "linear algebra" "quantum computing"

    # Bridge from psychology to neuroscience
    ebk learning-path /path/to/library "cognitive psychology" "neuroscience"
    """
    from .ai.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph(Path(lib_dir))

    if not kg.concepts:
        console.print("[red]Knowledge graph not built. Run 'ebk build-knowledge' first.[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Finding learning path from '{start_topic}' to '{end_topic}'...[/cyan]\n")

    # Get available books
    lib = Library.open(lib_dir)
    available_books = [e.unique_id for e in lib.entries]

    # Generate path
    path = kg.generate_reading_path(start_topic, end_topic, available_books)

    if not path:
        console.print(f"[yellow]No path found between '{start_topic}' and '{end_topic}'.[/yellow]")
        console.print("Try more general terms or ensure your library covers both topics.")
        return

    # Limit path length
    path = path[:max_steps]

    console.print(f"[green]Generated learning path with {len(path)} steps:[/green]\n")

    for i, step in enumerate(path, 1):
        # Find book details
        entry = lib.find(step['book_id'])
        if entry:
            console.print(f"[bold]Step {i}: {entry.title}[/bold]")
            if entry.creators:
                console.print(f"   by {', '.join(entry.creators)}")
        else:
            console.print(f"[bold]Step {i}: Book {step['book_id']}[/bold]")

        console.print(f"   Concept: {step['concept']}")
        console.print(f"   Why: {step['why']}")
        console.print()


@app.command()
@handle_library_errors
def index_semantic(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    book_ids: Optional[List[str]] = typer.Option(None, "--book", "-b", help="Specific book IDs to index"),
    chunk_size: int = typer.Option(500, "--chunk-size", help="Size of text chunks for indexing"),
    force: bool = typer.Option(False, "--force", "-f", help="Force reindex"),
):
    """
    Build semantic search index for intelligent content discovery.

    Creates vector embeddings for all books to enable semantic search
    across your library.

    Examples:
    # Index entire library
    ebk index-semantic /path/to/library

    # Index specific books
    ebk index-semantic /path/to/library --book id1 --book id2
    """
    from .ai.semantic_search import SemanticSearch
    from .ai.text_extractor import TextExtractor

    console.print("[cyan]Building semantic search index...[/cyan]")

    search = SemanticSearch(Path(lib_dir))
    extractor = TextExtractor()

    # Check existing index
    if search.book_chunks and not force:
        console.print(f"[yellow]Semantic index exists for {len(search.book_chunks)} books.[/yellow]")
        if not Confirm.ask("Do you want to rebuild?"):
            return

    # Load library
    lib = Library.open(lib_dir)
    entries = lib.entries

    # Filter by book IDs if specified
    if book_ids:
        entries = [e for e in entries if e.unique_id in book_ids]

    console.print(f"Indexing {len(entries)} books...")

    with Progress() as progress:
        task = progress.add_task("[green]Indexing books...", total=len(entries))

        for entry in entries:
            if not entry.file_paths:
                progress.advance(task)
                continue

            file_path = Path(lib_dir) / entry.file_paths[0]
            if not file_path.exists():
                progress.advance(task)
                continue

            try:
                # Extract text
                text = extractor.extract_full_text(file_path)
                if text:
                    # Index the book
                    search.index_book(entry.unique_id, text, chunk_size)
            except Exception as e:
                logger.warning(f"Failed to index {entry.title}: {e}")

            progress.advance(task)

    console.print(f"[green]✓ Semantic index built successfully![/green]")
    console.print(f"  - Books indexed: {len(search.book_chunks)}")


if __name__ == "__main__":
    app()