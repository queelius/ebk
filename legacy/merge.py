import os
import json
import shutil
from slugify import slugify
from typing import List, Dict, Tuple
from .ident import add_unique_id
import logging

logger = logging.getLogger(__name__)

def load_all_metadata(source_folders: List[str]) -> List[Tuple[Dict, str]]:
    """
    Given a list of source folders, load all 'metadata.json' files and 
    return them as a list of (metadata_entry, source_folder).
    """
    all_entries = []
    for folder in source_folders:
        meta_path = os.path.join(folder, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for entry in data:
                        all_entries.append((entry, folder))
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON from {meta_path}: {e}")
        else:
            logger.warning(f"No metadata.json found in {folder}")
    return all_entries

def perform_set_operation(
    entries: List[Dict], 
    operation: str, 
    source_counts: Dict[str, int]
) -> List[Dict]:
    """
    Perform the specified set operation on the list of entries.
    
    Args:
        entries (List[Dict]): List of eBook entries with 'unique_id'.
        operation (str): One of 'union', 'intersect', 'diff', 'symdiff'.
        source_counts (Dict[str, int]): Counts of how many sources each unique_id appears in.
    
    Returns:
        List[Dict]: Filtered list of entries based on the set operation.
    """
    if operation == "union":
        # All unique entries
        return entries
    elif operation == "intersect":
        # Entries present in all source libraries
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == len(source_counts)]
    elif operation == "diff":
        # Set difference: entries present in the first library but not in others
        # Assuming 'diff' is lib1 - lib2
        # Modify the function signature to pass specific libraries if needed
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == 1]
    elif operation == "symdiff":
        # Symmetric difference: entries present in one library but not in both
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == 1]
    else:
        logger.error(f"Unsupported set operation: {operation}")
        return []

def merge_libraries(
    source_folders: List[str], 
    merged_folder: str, 
    operation: str
):
    """
    Merges multiple ebook libraries (each in a separate folder) into a single library
    based on the specified set-theoretic operation.
    
    Args:
        source_folders (List[str]): List of source library folders to merge.
        merged_folder (str): Path to the folder where the merged library will be saved.
        operation (str): Set operation to apply ('union', 'intersect', 'diff', 'symdiff').
    """
    if not os.path.exists(merged_folder):
        os.makedirs(merged_folder)
        logger.info(f"Created merged folder at {merged_folder}")
    
    # Load all entries
    entries_with_sources = load_all_metadata(source_folders)
    
    # Index entries by unique_id
    unique_entries = {}
    source_counts = {}
    
    for entry, source in entries_with_sources:
        uid = entry['unique_id']
        if uid not in unique_entries:
            unique_entries[uid] = entry
            source_counts[uid] = 1
        else:
            source_counts[uid] += 1
            # Optionally, handle metadata conflicts here
            # For example, you could merge metadata fields or prioritize certain sources
            # Here, we'll assume the first occurrence is kept
            logger.debug(f"Duplicate entry found for unique_id {uid} in {source}. Ignoring.")
    
    all_unique_entries = list(unique_entries.values())
    
    # Perform the set operation
    filtered_entries = perform_set_operation(all_unique_entries, operation, source_counts)
    
    logger.info(f"Performing '{operation}' operation. {len(filtered_entries)} entries selected.")
    
    # **New Step:** Preprocess filenames to identify conflicts
    filename_counts = {}
    cover_filename_counts = {}
    
    for entry in filtered_entries:
        # Count ebook filenames
        for file_rel_path in entry.get('file_paths', []):
            filename = os.path.basename(file_rel_path)
            filename_counts[filename] = filename_counts.get(filename, 0) + 1
        # Count cover filenames
        cover_path = entry.get('cover_path')
        if cover_path:
            cover_filename = os.path.basename(cover_path)
            cover_filename_counts[cover_filename] = cover_filename_counts.get(cover_filename, 0) + 1
    
    logger.debug(f"Ebook filename counts: {filename_counts}")
    logger.debug(f"Cover filename counts: {cover_filename_counts}")
    
    # Copy files and prepare merged metadata
    merged_metadata = []
    
    for entry in filtered_entries:
        # Copy eBook files with awareness of filename uniqueness
        new_entry = copy_entry_files(entry, source_folders, merged_folder, filename_counts)
        # Copy cover image with awareness of filename uniqueness
        new_entry = copy_cover_image(new_entry, source_folders, merged_folder, cover_filename_counts)
        merged_metadata.append(new_entry)
    
    # Write merged metadata.json
    merged_meta_path = os.path.join(merged_folder, "metadata.json")
    with open(merged_meta_path, "w", encoding="utf-8") as f:
        json.dump(merged_metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Merged {len(merged_metadata)} entries into {merged_folder}")

def copy_entry_files(
    entry: Dict, 
    source_folders: List[str], 
    dst_folder: str,
    filename_counts: Dict[str, int]
) -> Dict:
    """
    Copies all relevant files for an entry from its source folder to the destination folder.
    
    Args:
        entry (Dict): The eBook entry metadata.
        source_folders (List[str]): List of source library folders.
        dst_folder (str): Destination folder to copy files to.
        filename_counts (Dict[str, int]): Counts of each ebook filename across all entries.
    
    Returns:
        Dict: The updated entry with new file paths.
    """
    new_entry = entry.copy()
    
    # Find the source folder containing this entry
    source_folder = find_source_folder(entry, source_folders)
    if not source_folder:
        logger.warning(f"Source folder not found for entry with unique_id {entry['unique_id']}")
        return new_entry
    
    # Copy eBook files
    new_file_paths = []
    for file_rel_path in entry.get('file_paths', []):
        src_path = os.path.join(source_folder, file_rel_path)
        if not os.path.exists(src_path):
            logger.warning(f"Ebook file '{src_path}' does not exist.")
            continue
        original_filename = os.path.basename(file_rel_path)
        
        if filename_counts.get(original_filename, 0) == 1:
            # Filename is unique; keep it as is
            dst_filename = original_filename
        else:
            # Filename is duplicated; append unique_id to disambiguate
            name, ext = os.path.splitext(original_filename)
            safe_name = slugify(name)
            safe_unique_id = slugify(entry['unique_id'])
            dst_filename = f"{safe_name}__{safe_unique_id}{ext}"
        
        dst_path = os.path.join(dst_folder, dst_filename)
        dst_path = get_unique_filename(dst_path)
        try:
            shutil.copy(src_path, dst_path)
        except OSError as e:
            logger.error(f"Error copying file '{src_path}' to '{dst_path}': {e}")
            continue
        new_file_paths.append(os.path.basename(dst_path))
        logger.debug(f"Copied ebook file '{src_path}' to '{dst_path}'")
    
    new_entry['file_paths'] = new_file_paths
    
    return new_entry

def copy_cover_image(
    entry: Dict, 
    source_folders: List[str], 
    dst_folder: str,
    cover_filename_counts: Dict[str, int]
) -> Dict:
    """
    Copies the cover image for an entry from its source folder to the destination folder.
    
    Args:
        entry (Dict): The eBook entry metadata.
        source_folders (List[str]): List of source library folders.
        dst_folder (str): Destination folder to copy files to.
        cover_filename_counts (Dict[str, int]): Counts of each cover filename across all entries.
    
    Returns:
        Dict: The updated entry with new cover path.
    """
    cover_path = entry.get('cover_path')
    if not cover_path:
        return entry  # No cover to copy
    
    new_entry = entry.copy()
    
    # Find the source folder containing this entry
    source_folder = find_source_folder(entry, source_folders)
    if not source_folder:
        logger.warning(f"Source folder not found for entry with unique_id {entry['unique_id']} (cover)")
        new_entry['cover_path'] = None
        return new_entry
    
    src_cover = os.path.join(source_folder, cover_path)
    if not os.path.exists(src_cover):
        logger.warning(f"Cover image '{src_cover}' does not exist.")
        new_entry['cover_path'] = None
        return new_entry
    
    original_cover_filename = os.path.basename(cover_path)
    
    if cover_filename_counts.get(original_cover_filename, 0) == 1:
        # Cover filename is unique; keep it as is
        dst_cover_filename = original_cover_filename
    else:
        # Cover filename is duplicated; append unique_id to disambiguate
        name, ext = os.path.splitext(original_cover_filename)
        safe_name = slugify(name)
        safe_unique_id = slugify(entry['unique_id'])
        dst_cover_filename = f"{safe_name}__{safe_unique_id}{ext}"
    
    dst_cover_path = os.path.join(dst_folder, dst_cover_filename)
    dst_cover_path = get_unique_filename(dst_cover_path)
    try:
        shutil.copy(src_cover, dst_cover_path)
    except OSError as e:
        logger.error(f"Error copying cover image '{src_cover}' to '{dst_cover_path}': {e}")
        new_entry['cover_path'] = None
        return new_entry
    new_entry['cover_path'] = os.path.basename(dst_cover_path)
    logger.debug(f"Copied cover image '{src_cover}' to '{dst_cover_path}'")
    
    return new_entry

def find_source_folder(entry: Dict, source_folders: List[str]) -> str:
    """
    Identifies the source folder where the entry's files are located.
    
    Args:
        entry (Dict): The eBook entry metadata.
        source_folders (List[str]): List of source library folders.
    
    Returns:
        str: The path to the source folder, or None if not found.
    """
    for folder in source_folders:
        meta_path = os.path.join(folder, "metadata.json")
        if not os.path.exists(meta_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for src_entry in data:
                    if src_entry.get('unique_id') == entry.get('unique_id'):
                        return folder
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from {meta_path}: {e}")
    return None

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
