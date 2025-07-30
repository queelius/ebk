import os
import networkx as nx
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
    
    try:
        lib = Library.open(lib_dir)
    except FileNotFoundError:
        console.print(f"[red]Library directory '{lib_dir}' does not exist.[/red]")
        raise typer.Exit(code=1)
    
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
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error showing entry: {e}")
        console.print(f"[bold red]Failed to show entry: {e}[/bold red]")
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
    try:
        lib = Library.open(lib_dir)
        stats = lib.stats()
        
        # Add keyword counts
        keyword_counts = {}
        for keyword in keywords:
            count = len(lib.search(keyword, fields=["title"]))
            keyword_counts[keyword] = count
        stats["keyword_counts"] = keyword_counts
        
        console.print_json(json.dumps(stats, indent=2))
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error generating statistics: {e}")
        console.print(f"[bold red]Failed to generate statistics: {e}[/bold red]")
        raise typer.Exit(code=1)
    
@app.command()
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
    try:
        lib = Library.open(lib_dir)
        
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
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error listing ebooks: {e}")
        console.print(f"[bold red]Failed to list ebooks: {e}[/bold red]")
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
    
    try:
        lib = Library.open(lib_dir)
        if output_json:
            # Use to_dict() for proper serialization
            data = [entry.to_dict() for entry in lib]
            console.print_json(json.dumps(data, indent=2))
        else:
            # Use internal _entries for legacy enumerate_ebooks function
            enumerate_ebooks(lib._entries, lib.path)
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error listing ebooks: {e}")
        console.print(f"[bold red]Failed to list ebooks: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error adding entry: {e}")
        console.print(f"[bold red]Failed to add entry: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error removing entries: {e}")
        console.print(f"[bold red]Failed to remove entries: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error removing entries by index: {e}")
        console.print(f"[bold red]Failed to remove entries: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error removing entry by ID: {e}")
        console.print(f"[bold red]Failed to remove entry: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error updating entry: {e}")
        console.print(f"[bold red]Failed to update entry: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error updating entry by ID: {e}")
        console.print(f"[bold red]Failed to update entry: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error searching library: {e}")
        console.print(f"[bold red]Failed to search library: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def visualize(lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to generate a complex network"),
              output_file: str = typer.Option(None, "--output-file", "-o", help="Output file for the graph visualization"),
              graph_type: str = typer.Option("coauthor", "--type", "-t", help="Graph type: 'coauthor' or 'subject'"),
              min_connections: int = typer.Option(1, "--min-connections", "-m", help="Minimum connections to show edge"),
              pretty_stats: bool = typer.Option(True, "--stats", "-s", help="Pretty print complex network statistics"),
              json_stats: bool = typer.Option(False, "--json-stats", "-j", help="Output complex network statistics as JSON")):
    """
    Visualize the ebk library as a complex network.

    Args:
        lib_dir (str): Path to the ebk library directory to visualize
        output_file (str): Output file for the graph visualization
        graph_type (str): Type of graph to generate
        min_connections (int): Minimum edge weight to include
        stats (bool): Pretty print complex network statistics
        json_stats (bool): Output complex network statistics as JSON

    Raises:
        typer.Exit: If the library directory is invalid
    
    Output:
        Generates a complex network visualization of the library.
    """
    try:
        lib = Library.open(lib_dir)
        
        if output_file:
            # Export graph file
            lib.export_graph(output_file, graph_type=graph_type, min_connections=min_connections)
            console.print(f"[green]Saved graph to {output_file}[/green]")
            
            # If it's a visual format, also create an image
            if output_file.endswith(('.png', '.jpg', '.pdf', '.svg')):
                import networkx as nx
                import matplotlib.pyplot as plt
                
                # Build the graph same way as export_graph
                G = nx.Graph()
                
                if graph_type == "coauthor":
                    # Build co-authorship network
                    for i, entry in enumerate(lib._entries):
                        creators = entry.get("creators", [])
                        G.add_node(f"book_{i}", 
                                  type="book", 
                                  title=entry.get("title", "Unknown"),
                                  id=entry.get("unique_id"))
                        
                        for creator in creators:
                            if not G.has_node(creator):
                                G.add_node(creator, type="author")
                            G.add_edge(f"book_{i}", creator)
                    
                    # Create co-author edges
                    authors = [n for n, d in G.nodes(data=True) if d.get("type") == "author"]
                    for book_node in [n for n, d in G.nodes(data=True) if d.get("type") == "book"]:
                        book_authors = list(G.neighbors(book_node))
                        for i, author1 in enumerate(book_authors):
                            for author2 in book_authors[i+1:]:
                                if G.has_edge(author1, author2):
                                    G[author1][author2]["weight"] += 1
                                else:
                                    G.add_edge(author1, author2, weight=1)
                else:
                    # Subject network
                    for i, entry in enumerate(lib._entries):
                        subjects = entry.get("subjects", [])
                        for j, other_entry in enumerate(lib._entries[i+1:], i+1):
                            other_subjects = other_entry.get("subjects", [])
                            shared = set(subjects) & set(other_subjects)
                            if len(shared) >= min_connections:
                                G.add_edge(f"book_{i}", f"book_{j}", weight=len(shared))
                
                # Visualize
                plt.figure(figsize=(12, 8))
                pos = nx.spring_layout(G, k=2, iterations=50)
                nx.draw(G, pos, 
                       node_color='lightblue',
                       node_size=300,
                       with_labels=False,
                       edge_color='gray',
                       alpha=0.7)
                plt.title(f"Library {graph_type.title()} Network")
                plt.savefig(output_file, dpi=300, bbox_inches='tight')
        
        # Calculate and show statistics
        if pretty_stats or json_stats:
            basic_stats = lib.stats()
            analysis = lib.analyze_reading_patterns()
            
            stats = {
                "total_books": basic_stats["total_entries"],
                "unique_authors": len(basic_stats["creators"]),
                "unique_subjects": len(basic_stats["subjects"]),
                "languages": len(basic_stats["languages"]),
                "subject_diversity": analysis["reading_diversity"].get("subject_entropy", 0),
                "books_per_author": analysis["reading_diversity"].get("books_per_author", 0)
            }
            
            if json_stats:
                console.print_json(json.dumps(stats, indent=2))
            else:
                console.print("[bold]Library Statistics:[/bold]")
                console.print(f"  Total books: {stats['total_books']}")
                console.print(f"  Unique authors: {stats['unique_authors']}")
                console.print(f"  Unique subjects: {stats['unique_subjects']}")
                console.print(f"  Languages: {stats['languages']}")
                console.print(f"  Subject diversity (entropy): {stats['subject_diversity']:.2f}")
                console.print(f"  Books per author: {stats['books_per_author']:.2f}")
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error visualizing library: {e}")
        console.print(f"[bold red]Failed to visualize library: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def export_dag(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory"),
    output_dir: str = typer.Argument(..., help="Output directory for the symlink DAG structure"),
    tag_field: str = typer.Option("subjects", "--tag-field", "-t", help="Field to use for tags (e.g., subjects, creators)"),
    include_files: bool = typer.Option(True, "--include-files/--no-files", help="Copy actual ebook files"),
    create_index: bool = typer.Option(True, "--create-index/--no-index", help="Create HTML index files")
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
    try:
        lib = Library.open(lib_dir)
        
        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Creating symlink DAG structure...", total=None)
            
            lib.export_to_symlink_dag(
                output_dir,
                tag_field=tag_field,
                include_files=include_files,
                create_index=create_index
            )
            
            progress.update(task, description="[green]Symlink DAG created successfully!")
            
        console.print(f"[bold green]Created navigable library structure at: {output_dir}[/bold green]")
        console.print(f"\n[yellow]You can now:[/yellow]")
        console.print(f"  • Navigate with your file explorer")
        console.print(f"  • Use command line: cd {output_dir}")
        if create_index:
            console.print(f"  • Open in browser: file://{Path(output_dir).absolute()}/index.html")
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error creating symlink DAG: {e}")
        console.print(f"[bold red]Failed to create symlink DAG: {e}[/bold red]")
        if "symlink" in str(e).lower():
            console.print("[yellow]Note: On Windows, creating symlinks may require administrator privileges.[/yellow]")
        raise typer.Exit(code=1)


@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        console.print(f"[bold red]Failed to get recommendations: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
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
    try:
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
    
    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        raise typer.Exit(code=1)
    except Exception as e:
        logger.error(f"Error finding similar entries: {e}")
        console.print(f"[bold red]Failed to find similar entries: {e}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()