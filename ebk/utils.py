import json
import os
from collections import Counter
from pathlib import Path
from typing import List, Dict, Optional
import logging
from jmespath import search as jmes_search
import sys
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich import print
import re

RICH_AVAILABLE = True

logger = logging.getLogger(__name__)

def search_jmes(lib_dir: str, expression: str):
    """
    Search entries in an ebk library using a JMESPath expression. This is a
    very flexible way to search for entries in the library, but may have a
    steep learning curve.

    Args:
        lib_dir (str): Path to the ebk library directory
        expression (str): Search expression (JMESPath)

    Returns:
        Any: Result of the JMESPath search
    """
    library = load_library(lib_dir)
    if not library:
        logger.error(f"Failed to load the library at {lib_dir}")
        return []
    
    result = jmes_search(expression, library)
 
    return result

def search_regex(lib_dir: str, expression: str, fields: List[str] = ["title"]):

    library = load_library(lib_dir)
    results = []
    for entry in library:
        for key, value in entry.items():
            if key in fields and value:
                if isinstance(value, str) and re.search(expression, value):
                    results.append(entry)
                    break

    return results


def load_library(lib_dir: str) -> List[Dict]:
    """
    Load an ebk library from the specified directory.

    Args:
        lib_dir (str): Path to the ebk library directory

    Returns:
        List[Dict]: List of entries in the library
    """
    lib_dir = Path(lib_dir)
    metadata_path = lib_dir / "metadata.json"
    if not metadata_path.exists():
        logger.error(f"Metadata file not found at {metadata_path}")
        return []

    with open(metadata_path, "r") as f:
        try:
            library = json.load(f)
            return library
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {metadata_path}: {e}")
            return []

def get_library_statistics(lib_dir: str,
                           keywords: List[str] = None) -> Dict:
    """
    Compute statistics for an ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory.
        keywords (List[str]): Keywords to search for in titles (default: None).

    Returns:
        dict: A dictionary or markdown with statistics about the library.
    """

    # Load the library
    library = load_library(lib_dir)
    if not library:
        logger.error(f"Failed to load the library at {lib_dir}")
        return {}

    # Initialize counters and statistics
    stats = {
        "total_entries": 0,
        "languages": Counter(),
        "creators_count": 0,
        "average_creators_per_entry": 0,
        "most_creators_in_entry": 0,
        "least_creators_in_entry": 0,
        "top_creators": Counter(),
        "subjects": Counter(),
        "most_common_subjects": [],
        "average_title_length": 0,
        "longest_title": "",
        "shortest_title": "",
        "virtual_libs": Counter(),
        "titles_with_keywords": Counter(),
    }

    title_lengths = []

    for entry in library:
        # Total entries
        stats["total_entries"] += 1

        # Languages
        language = entry.get("language", "unknown")
        stats["languages"][language] += 1

        # Creators
        creators = entry.get("creators", [])
        stats["creators_count"] += len(creators)
        stats["top_creators"].update(creators)
        stats["most_creators_in_entry"] = max(stats["most_creators_in_entry"], len(creators))
        if stats["least_creators_in_entry"] == 0 or len(creators) < stats["least_creators_in_entry"]:
            stats["least_creators_in_entry"] = len(creators)

        # Subjects
        subjects = entry.get("subjects", [])
        stats["subjects"].update(subjects)

        # Titles
        title = entry.get("title", "")
        if title:
            title_lengths.append(len(title))
            if len(title) > len(stats["longest_title"]):
                stats["longest_title"] = title
            if not stats["shortest_title"] or len(title) < len(stats["shortest_title"]):
                stats["shortest_title"] = title

        # Keywords
        for keyword in keywords:
            if keyword.lower() in title.lower():
                stats["titles_with_keywords"][keyword] += 1

        # Virtual Libraries
        virtual_libs = entry.get("virtual_libs", [])
        stats["virtual_libs"].update(virtual_libs)

    # Post-process statistics
    stats["average_creators_per_entry"] = round(stats["creators_count"] / stats["total_entries"], 2)
    stats["average_title_length"] = round(sum(title_lengths) / len(title_lengths), 2) if title_lengths else 0
    stats["most_common_subjects"] = stats["subjects"].most_common(5)
    stats["languages"] = dict(stats["languages"])
    stats["top_creators"] = dict(stats["top_creators"].most_common(5))
    stats["titles_with_keywords"] = dict(stats["titles_with_keywords"])
    stats["virtual_libs"] = dict(stats["virtual_libs"])

    return stats

def get_unique_filename(target_path: str) -> str:
    """
    If target_path already exists, generate a new path with (1), (2), etc.
    Otherwise just return target_path.
    
    Example:
       'myfile.pdf' -> if it exists -> 'myfile (1).pdf' -> if that exists -> 'myfile (2).pdf'
    """
    if not os.path.exists(target_path):
        return target_path

    base, ext = os.path.splitext(target_path)
    counter = 1
    new_path = f"{base} ({counter}){ext}"
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{base} ({counter}){ext}"

    return new_path

def enumerate_ebooks(metadata_list: List[Dict],
                     lib_path: Path,
                     indices: Optional[List[int]] = None,
                     detailed: Optional[bool] = False) -> None:
    """
    Enumerates and displays the ebooks in the specified library directory.

    For each ebook, displays its index, title, creators, and a clickable link to the first PDF file.

    Args:
        metadata_list (List[Dict]): List of metadata dictionaries for each ebook.
        indices (List[int]): List of indices to display (default: None).
    """
    console = Console()

    total_books = len(metadata_list)
    if total_books == 0:
        console.print("[yellow]No ebooks found in the library.[/yellow]")
        return
    
    if indices is None:
        indices = range(total_books)

    console.print(f"📚 [bold]Found {total_books} ebook(s) in the library:[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim")
    table.add_column("Title")
    table.add_column("Creators")
    table.add_column("Link")

    if detailed:
        table.add_column("Subjects")
        table.add_column("Language")
        table.add_column("Date")
        table.add_column("Identifiers")
        table.add_column("Publisher")
        table.add_column("File Size")
        table.add_column("Virtual Libraries")
        table.add_column("UID")

    for i, book in enumerate(metadata_list, start=0):

        if i not in indices:
            continue

        title = book.get('title', '-')
        creators = book.get('creators', ['-'])
        if not isinstance(creators, list):
            creators = [str(creators)]
        creators_str = ', '.join(creators)

        ebook_paths = book.get('file_paths', [])
        ebook_path = ebook_paths[0] if ebook_paths else None

        if ebook_path:
            ebook_full_path = lib_path / ebook_path
            if ebook_full_path.exists():
                # Resolve the path to an absolute path
                resolved_path = ebook_full_path.resolve()
                # Convert Windows paths to URL format if necessary
                if sys.platform.startswith('win'):
                    ebook_link = resolved_path.as_uri()
                else:
                    ebook_link = f"file://{resolved_path}"
                link_display = f"[link={ebook_link}]🔗 Open[/link]"
            else:
                ebook_link = "File not found"
                link_display = "[red]🔗 Not Found[/red]"
        else:
            ebook_link = "Unknown"
            link_display = "[red]🔗 Unknown[/red]"

        table.add_row(str(i), title, creators_str, link_display)

    console.print(table)
    console.print("\n")  # Add some spacing

def get_index_by_unique_id(lib_dir: str, id: str) -> int:
    """
    Get the index of an entry in the library by its unique ID.

    Args:
        lib_dir (str): Path to the ebk library directory.
        id (str): Unique ID to search for.

    Returns:
        int: Index of the entry with the specified unique ID. -1 if not found.

    Raises:
        ValueError: If the library cannot be loaded.
    """

    library = load_library(lib_dir)
    if not library:
       raise ValueError("Failed to load the library.")

    for i, entry in enumerate(library):
        if entry.get('unique_id') == id:
            return i

    return -1

def print_json_as_table(data):
    """
    Pretty print JSON data as a table using Rich.

    Args:
        data: JSON data to print
    """
    if not RICH_AVAILABLE:
        print(json.dumps(data, indent=2))
        return

    if isinstance(data, dict):
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Key", style="dim", width=20)
        table.add_column("Value", width=80)
        for key, value in data.items():
            table.add_row(str(key), str(value))
        console = Console()
        console.print(table)
    else:
        print(data)

