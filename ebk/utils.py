import json
import os
from collections import Counter
from pathlib import Path
from typing import List, Dict
import logging
from jmespath import search

logger = logging.getLogger(__name__)

def search_entries(lib_dir: str, expression: str):
    """
    Search entries in an ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory
        expression (str): Search expression (regex)

    Returns:
        List[Dict]: List of matching entries
    """
    library = load_library(lib_dir)
    if not library:
        logger.error(f"Failed to load the library at {lib_dir}")
        return []
    
    result = search(expression, library)
    return result


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
