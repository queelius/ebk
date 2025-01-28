import os
import networkx as nx
import subprocess
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
from .imports import ebooks, calibre
from .merge import merge_libraries
from .utils import enumerate_ebooks, load_library, get_unique_filename, search_regex, search_jmes, get_library_statistics, get_index_by_unique_id, print_json_as_table
from .ident import add_unique_id
from .llm import query_llm

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
    """
    output_dir = output_dir or f"{calibre_dir.rstrip('/')}-ebk"
    with Progress(console=console) as progress:
        task = progress.add_task("[cyan]Importing Calibre library...", total=None)
        try:
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
            ebooks.import_ebooks(ebooks_dir, output_dir, ebook_formats)
        except Exception as e:
            logger.error(f"Error importing raw ebooks: {e}")
            raise typer.Exit(code=1)

@app.command()
def export(
    format: str = typer.Argument(..., help="Export format (e.g., 'hugo', 'zip')"),
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to export (contains `metadata.json` and ebook-related files)"),
    destination: Optional[str] = typer.Argument(
        None,
        help="Destination path (Hugo site directory or Zip file path). If not provided for 'zip' format, defaults to '<lib_dir>.zip' or '<lib_dir> (j).zip' to avoid overwriting."
    )
):
    """
    Export the ebk library to the specified format.
    """
    format = format.lower()
    lib_path = Path(lib_dir)
    
    if not lib_path.exists() or not lib_path.is_dir():
        console.print(f"[red]Library directory '{lib_dir}' does not exist or is not a directory.[/red]")
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
                export_zipfile(str(lib_path), str(dest_path))
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
            task = progress.add_task("[cyan]Exporting to Hugo...", total=None)
            try:
                export_hugo(str(lib_path), str(dest_path))
                progress.update(task, description="[green]Exported to Hugo successfully!")
                logger.info(f"Library exported to Hugo at {dest_path}")
                console.print(f"[bold green]Exported library to Hugo directory '{dest_path}'.[/bold green]")
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
    metadata_list = load_library(lib_dir)
    if not metadata_list:
        console.print("[red]Failed to load library.[/red]")
        raise typer.Exit(code=1)
    
    total_books = len(metadata_list)
    for index in indices:
        if index < 0 or index >= total_books:
            console.print(f"[red]Index {index} is out of range (0-{total_books - 1}).[/red]")
            raise typer.Exit(code=1)

    for index in indices: 
        entry = metadata_list[index]
        if output_json:
            console.print_json(json.dumps(entry, indent=2))
        else:
            # Create a table
            table = Table(title="ebk Ebook Entry", show_lines=True)

            # Add column headers dynamically based on JSON keys
            columns = entry.keys()  # Assuming all objects have the same structure
            for column in columns:
                table.add_column(column, justify="center", style="bold cyan")

            # Add rows dynamically
            for item in entry:
                table.add_row(*(str(entry[col]) for col in columns))

            # Print the table
            console.print(table)

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
            merge_libraries(libs, output_dir, operation)
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
        stats = get_library_statistics(lib_dir, keywords)
        console.print_json(json.dumps(stats, indent=2))
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
    lib_path = Path(lib_dir)
    if not lib_path.exists():
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        sys.exit(1)

    if not lib_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] The path '{lib_dir}' is not a directory.")
        sys.exit(1)

    try:
        metadata_list = load_library(lib_dir)
        if output_json:
            console.print_json(json.dumps(metadata_list, indent=2))
        else:
            enumerate_ebooks(metadata_list, lib_path, indices, detailed)
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
    
    lib_path = Path(lib_dir)

    if not lib_path.exists():
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        sys.exit(1)

    if not lib_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] The path '{lib_dir}' is not a directory.")
        sys.exit(1)

    try:
        metadata_list = load_library(lib_dir)
        if output_json:
            console.print_json(json.dumps(metadata_list, indent=2))
        else:
            enumerate_ebooks(metadata_list, lib_path)
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
        metadata_list = load_library(lib_dir)
        if not metadata_list:
            console.print("[red]Failed to load library.[/red]")
            raise typer.Exit(code=1)
        console.print(f"Loaded [bold]{len(metadata_list)}[/bold] entries from [green]{lib_dir}[/green]")
        
        if json_file:
            with open(json_file, "r") as f:
                new_entries = json.load(f)
            for entry in new_entries:
                add_unique_id(entry)
                metadata_list.append(entry)
            console.print(f"[green]Added {len(new_entries)} entries from {json_file}[/green]")
        else:
            if not title or not creators:
                console.print("[red]Title and creators are required when not using a JSON file.[/red]")
                raise typer.Exit(code=1)
            new_entry = {
                "title": title,
                "creators": creators,
                "file_paths": ebooks or [],
                "cover_path": cover,
            }
            add_unique_id(new_entry)
            metadata_list.append(new_entry)
            console.print(f"Adding new entry: [bold]{new_entry['title']}[/bold]")
    
        # Save updated metadata
        with open(Path(lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)
    
        # Use Rich's Progress to copy files
        with Progress(console=console) as progress:
            if ebooks:
                task = progress.add_task("[cyan]Copying ebook files...", total=len(ebooks))
                for ebook in ebooks:
                    shutil.copy(ebook, lib_dir)
                    progress.advance(task)
                    logger.debug(f"Copied ebook file: {ebook}")
            if cover:
                task = progress.add_task("[cyan]Copying cover image...", total=1)
                shutil.copy(cover, lib_dir)
                progress.advance(task)
                logger.debug(f"Copied cover image: {cover}")
    
        console.print(f"[bold green]Added new entry: {new_entry['title']}[/bold green]")
    
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
        metadata_list = load_library(lib_dir)
        if not metadata_list:
            console.print("[red]Failed to load library.[/red]")
            raise typer.Exit(code=1)
        console.print(f"Loaded [bold]{len(metadata_list)}[/bold] entries from [green]{lib_dir}[/green]")
    
        rem_list = []
        if "title" in apply_to:
            rem_list += [entry for entry in metadata_list if re.search(regex, entry.get("title", ""))]
        if "creators" in apply_to:
            rem_list += [entry for entry in metadata_list if any(re.search(regex, creator) for creator in entry.get("creators", []))]
        if "identifiers" in apply_to:
            rem_list += [entry for entry in metadata_list if any(re.search(regex, identifier) for identifier in entry.get("identifiers", {}).values())]
        
        # Remove duplicates based on unique_id
        rem_list = list({entry['unique_id']: entry for entry in rem_list}.values())

        if not rem_list:
            console.print("[yellow]No matching entries found for removal.[/yellow]")
            raise typer.Exit()

        for entry in rem_list:
            if not force:
                console.print(f"Remove entry: [bold]{entry.get('title', 'No Title')}[/bold]")
                confirm = Confirm.ask("Confirm removal?")
                if not confirm:
                    continue

            metadata_list.remove(entry)
            console.print(f"[green]Removed entry: {entry.get('title', 'No Title')}[/green]")
            logger.debug(f"Removed entry: {entry}")

        with open(Path(lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)
        
        console.print(f"[bold green]Removed {len(rem_list)} entries from {lib_dir}[/bold green]")
    
    except Exception as e:
        logger.error(f"Error removing entries: {e}")
        console.print(f"[bold red]Failed to remove entries: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def remove_id(lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
              unique_id: str = typer.Argument(..., help="Unique ID of the entry to remove")):
    """
    Remove an entry from the ebk library by unique ID.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        unique_id (str): Unique ID of the entry to remove
    """
    id = get_index_by_unique_id(lib_dir, unique_id)
    remove_index(lib_dir, [id])

    
@app.command()
def update_index(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    index: int = typer.Argument(..., help="Index of the entry to update"),
    json_file: str = typer.Option(None, "--json", help="JSON file containing updated entry info"),
    title: str = typer.Option(None, "--title", help="New title for the entry"),
    creators: List[str] = typer.Option(None, "--creators", help="New creators for the entry"),
    ebooks: List[str] = typer.Option(None, "--ebooks", help="Paths to the new ebook files"),
    cover: str = typer.Option(None, "--cover", help="Path to the new cover image")
):
    """
    Update an entry in the ebk library by index.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        index (int): Index of the entry to update
        json_file (str): Path to a JSON file containing updated entry info
        title (str): New title for the entry
        creators (List[str]): New creators for the entry
        ebooks (List[str]): Paths to the new ebook files
        cover (str): Path to the new cover image
    """

    try:
        metadata_list = load_library(lib_dir)
        if not metadata_list:
            console.print("[red]Failed to load library.[/red]")
            raise typer.Exit(code=1)
        console.print(f"Loaded [bold]{len(metadata_list)}[/bold] entries from [green]{lib_dir}[/green]")

        if json_file:
            with open(json_file, "r") as f:
                updated_entry = json.load(f)
        else:
            updated_entry = metadata_list[index]
            if title:
                updated_entry["title"] = title
            if creators:
                updated_entry["creators"] = creators
            if ebooks:
                updated_entry["file_paths"] = ebooks
            if cover:
                updated_entry["cover_path"] = cover
        
        metadata_list[index] = updated_entry
        with open(Path(lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)

        console.print(f"[bold green]Updated entry at index {index} in {lib_dir}[/bold green]")
    except Exception as e:
        logger.error(f"Error updating entry by index: {e}")
        console.print(f"[bold red]Failed to update entry by index: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def update_id(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to modify"),
    unique_id: str = typer.Argument(..., help="Unique ID of the entry to update"),
    json_file: str = typer.Option(None, "--json", help="JSON file containing updated entry info"),
    title: str = typer.Option(None, "--title", help="New title for the entry"),
    creators: List[str] = typer.Option(None, "--creators", help="New creators for the entry"),
    ebooks: List[str] = typer.Option(None, "--ebooks", help="Paths to the new ebook files"),
    cover: str = typer.Option(None, "--cover", help="Path to the new cover image")
):
    """
    Update an entry in the ebk library by unique id.

    Args:
        lib_dir (str): Path to the ebk library directory to modify
        id: str: Unique ID of the entry to update
        json_file (str): Path to a JSON file containing updated entry info
        title (str): New title for the entry
        creators (List[str]): New creators for the entry
        ebooks (List[str]): Paths to the new ebook files
        cover (str): Path to the new cover image
    """

    id = lambda entry: entry.get("unique_id")
    index = get_index_by_unique_id(lib_dir, id)
    if index == -1:
        console.print(f"[red]Entry with unique ID [bold]{unique_id}[/bold] not found.[/red]")
        raise typer.Exit(code=1)
    
    update_index(lib_dir, index, json_file, title, creators, ebooks, cover)

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
        Removes the specified entries from the library and updates the metadata file in-place.
    """
    try:
        metadata_list = load_library(lib_dir)
        if not metadata_list:
            console.print("[red]Failed to load library.[/red]")
            raise typer.Exit(code=1)
        console.print(f"Loaded [bold]{len(metadata_list)}[/bold] entries from [green]{lib_dir}[/green]")

        indices = sorted(indices, reverse=True)
        with Progress(console=console) as progress:
            task = progress.add_task("[cyan]Removing entries...", total=len(indices))
            removed_count = 0
            for i in indices:
                if 0 <= i < len(metadata_list):
                    del metadata_list[i]
                    progress.advance(task)
                    logger.debug(f"Removed entry at index {i}")
                    removed_count += 1
                else:
                    console.print(f"[yellow]Index {i} is out of range.[/yellow]")

        with open(Path(lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)

        console.print(f"[bold green]Removed {removed_count} entries from {lib_dir}[/bold green]")

    except Exception as e:
        logger.error(f"Error removing entries by index: {e}")
        console.print(f"[bold red]Failed to remove entries: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def dash(
    lib_dir: str = typer.Option(None, "--lib-dir", help="Path to the ebk library directory"),
    port: int = typer.Option(8501, "--port", help="Port to run the Streamlit app (default: 8501)")
):
    """
    Launch the Streamlit dashboard.
    """
    try:
        app_path = Path(__file__).parent / 'streamlit' / 'app.py'
    
        if not app_path.exists():
            print(f"[bold red]Streamlit app not found at {app_path}[/bold red]")
            raise typer.Exit(code=1)

        # Construct the command
        cmd = ['streamlit', 'run', str(app_path), "--server.port", str(port), "--"]
    
        if lib_dir:
            cmd.extend(["--lib-dir", lib_dir])

        subprocess.run(cmd, check=True)
        if lib_dir:
            logger.info(f"Streamlit dashboard launched on port {port} for ebk library {lib_dir}.")
        else:
            logger.info(f"Streamlit dashboard launched on port {port}")
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] Streamlit is not installed. Please install it with `pip install streamlit`.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error launching Streamlit dashboard: {e}")
        console.print(f"[bold red]Failed to launch Streamlit dashboard: {e}[/bold red]")
        raise typer.Exit(code=e.returncode)
    except Exception as e:
        logger.error(f"Unexpected error launching Streamlit dashboard: {e}")
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def regex(
    query: str = typer.Argument(..., help="Regex search expression."),
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to search"),
    json_out: bool = typer.Option(False, "--json", "-j", help="Output search results as JSON"),
    fields: List[str] = typer.Option(["title"], "--fields", "-f", help="Fields to search in (default: title)")):
    """
    Search entries in an ebk library using a regex expression on specified fields.

    Args:
        query (str): Regex search expression
        lib_dir (str): Path to the ebk library directory to search
        json_out (bool): Output search results as JSON
        fields (List[str]): Fields to search in (default: title)

    Returns:
        Search results as a table or JSON
    """
    try:
        results = search_regex(lib_dir, query, fields)
        if json_out:
            console.print_json(json.dumps(results, indent=2))
        else:
            enumerate_ebooks(results, Path(lib_dir))
    except Exception as e:
        logger.error(f"Error searching library with regex: {e}")
        console.print(f"[bold red]Failed to search library with regex: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def jmespath(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to query"),
    query: str = typer.Argument(..., help="JMESPath query string to search in the library"),
    json_out: bool = typer.Option(False, "--json", "-j", help="Output search results as JSON")):
    """
    Query the ebk library using JMESPath.

    Args:
        lib_dir (str): Path to the ebk library directory to query
        query (str): JMESPath query string to search in the library
        output_json (bool): Output search results as JSON

    Returns:
        JMEPSath query results, either pretty printed or as JSON.
    """
    try:
        results = search_jmes(lib_dir, query)
        if json_out:
            console.print_json(json.dumps(results, indent=2))
        else:
            print_json_as_table(results)
    except Exception as e:
        logger.error(f"Error querying library with JMESPath: {e}")
        console.print(f"[bold red]Failed to query library with JMESPath: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def llm(
    lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to query"),
    query: str = typer.Argument(..., help="Query string to search in the library")
):
    """
    Query the ebk library using the LLM (Large Language Model) endpoint.

    Args:
        lib_dir (str): Path to the ebk library directory to query
        query (str): Natural language query to interact with the library

    Returns:
        LLM query results
    """
    try:
        query_llm(lib_dir, query)
    except Exception as e:
        logger.error(f"Error querying library with LLM: {e}")
        console.print(f"[bold red]Failed to query library with LLM: {e}[/bold red]")
        raise typer.Exit(code=1)

@app.command()
def visualize(lib_dir: str = typer.Argument(..., help="Path to the ebk library directory to generate a complex network"),
              output_file: str = typer.Option(None, "--output-file", "-o", help="Output file for the graph visualization"),
              pretty_stats: bool = typer.Option(True, "--stats", "-s", help="Pretty print complex network statistics"),
              json_stats: bool = typer.Option(False, "--json-stats", "-j", help="Output complex network statistics as JSON")):
    
    """
    Generate a complex network visualization from the ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory to generate a complex network
        output_file (str): Output file for the graph visualization
        pretty_stats (bool): Pretty print complex network statistics
        json_stats (bool): Output complex network statistics as JSON

    Returns:
        Complex network visualization and statistics
    """

    if output_file and not output_file.endswith(('.html', '.png', '.json')):
        logging.error("Output file must be either an HTML file, PNG file, or JSON file.")
        sys.exit(1)

    if not os.path.isdir(lib_dir):
        logging.error(f"The specified library directory '{lib_dir}' does not exist or is not a directory.")
        sys.exit(1)
    
    metadata_list = load_library(lib_dir)
    if not metadata_list:
        logging.error(f"No metadata found in the library directory '{lib_dir}'.")
        sys.exit(1)
    
    net = visualize.generate_complex_network(metadata_list)
    
    if output_file:
        if output_file.endswith('.html'):
            # Interactive visualization with pyvis
            visualize.as_pyvis(net, output_file)
        elif output_file.endswith('.json'):
            net_json = nx.node_link_data(net)  # Convert to node-link format
            console.print(JSON(json.dumps(net_json, indent=2)))
        elif output_file.endswith('.png'):
            visualize.as_png(net, output_file)
    
    if pretty_stats:
        console.print(nx.info(net))
        # console.print(f"[bold green]Complex network generated successfully![/bold green]")
        # console.print(f"Nodes: {net.number_of_nodes()}")
        # console.print(f"Edges: {net.number_of_edges()}")
        # console.print(f"Average Degree: {np.mean([d for n, d in net.degree()])}")
        # console.print(f"Average Clustering Coefficient: {nx.average_clustering(net)}")
        # console.print(f"Transitivity: {nx.transitivity(net)}")
        # console.print(f"Average Shortest Path Length: {nx.average_shortest_path_length(net)}")
        # console.print(f"Global Clustering Coefficient: {nx.transitivity(net)}")
        # console.print(f"Global Efficiency: {nx.global_efficiency(net)}")
        # console.print(f"Modularity: {community.modularity(community.best_partition(net), net)}")
    if json_stats:
        console.print_json(json.dumps(nx.info(net), indent=2))

if __name__ == "__main__":
    app()
