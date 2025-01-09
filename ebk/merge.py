# merge.py
import os
import json
import shutil
from slugify import slugify

def load_all_metadata(source_folders):
    """
    Given a list of source folders, load all 'metadata.json' files and 
    return them as a list of (metadata_entry, source_folder).
    """
    all_entries = []
    for folder in source_folders:
        meta_path = os.path.join(folder, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Each item is one metadata dict
                for entry in data:
                    # Store both the entry and the folder it came from
                    all_entries.append((entry, folder))
        else:
            print(f"Warning: No metadata.json found in {folder}")

    return all_entries

def get_unique_filename(target_path):
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

def make_base_name(entry):
    """
    Construct a slug-based file prefix from the metadata entry 
    (similar to the approach used in convert_calibre).
    """
    title_slug = slugify(entry.get("title", "unknown_title"))
    creator_slug = "unknown_creator"
    if "creators" in entry and entry["creators"]:
        creator_slug = slugify(entry["creators"][0])

    # Pick a consistent identifier for deduping or naming
    # e.g., calibre, uuid, ISBN, etc.
    identifier = (entry.get("identifiers", {}).get("calibre") or
                  entry.get("identifiers", {}).get("uuid") or
                  "unknown_id")

    return f"{title_slug}__{creator_slug}__{identifier}"

def copy_entry_files(entry, src_folder, dst_folder):
    """
    Given one metadata entry and the source folder it belongs to,
    copy all relevant files (ebook files, cover, etc.) into dst_folder.
    
    Returns a *new* metadata dict that has updated file paths 
    relative to the merged folder.
    """
    base_name = make_base_name(entry)
    new_entry = dict(entry)  # shallow copy so we don't mutate the original

    # 1) Copy main ebook files
    old_file_paths = entry.get("file_paths", [])
    new_file_paths = []
    for old_rel_path in old_file_paths:
        _, ext = os.path.splitext(old_rel_path)
        target_file_name = base_name + ext  # e.g. "some-book__alice__uuid123.epub"
        target_path = os.path.join(dst_folder, target_file_name)

        target_path = get_unique_filename(target_path)
        src_full_path = os.path.join(src_folder, old_rel_path)

        if os.path.exists(src_full_path):
            shutil.copy(src_full_path, target_path)
            # In the new metadata, we typically store relative paths (basename)
            new_file_paths.append(os.path.basename(target_path))
        else:
            print(f"Warning: Source file missing '{src_full_path}'")

    new_entry["file_paths"] = new_file_paths

    # 2) Copy cover if relevant
    old_cover_path = entry.get("cover_path")
    if old_cover_path:
        _, cover_ext = os.path.splitext(old_cover_path)
        cover_target_name = f"{base_name}_cover{cover_ext}"
        cover_target_path = os.path.join(dst_folder, cover_target_name)

        cover_target_path = get_unique_filename(cover_target_path)
        src_cover_full_path = os.path.join(src_folder, old_cover_path)

        if os.path.exists(src_cover_full_path):
            shutil.copy(src_cover_full_path, cover_target_path)
            new_entry["cover_path"] = os.path.basename(cover_target_path)
        else:
            print(f"Warning: Cover file missing '{src_cover_full_path}'")
            new_entry["cover_path"] = None
    else:
        new_entry["cover_path"] = None  # or remove this key if you like

    return new_entry

def merge_outputs(source_folders, merged_folder):
    """
    Merges the outputs from multiple folders (each having metadata.json + files)
    into a new merged_folder with a single metadata.json + all files.

    Steps:
      1) Load all entries from each folder's metadata.json
      2) For each entry, copy files from its source folder to merged_folder
      3) Write a single metadata.json in merged_folder
    """
    if not os.path.exists(merged_folder):
        os.makedirs(merged_folder)

    # 1. Gather all (entry, source_folder) pairs
    entries_with_sources = load_all_metadata(source_folders)

    # We'll accumulate the new/merged metadata here
    merged_metadata = []

    # 2. Copy files for each entry
    for entry, src_folder in entries_with_sources:
        new_entry = copy_entry_files(entry, src_folder, merged_folder)
        merged_metadata.append(new_entry)

    # 3. Write a single merged metadata.json
    merged_meta_path = os.path.join(merged_folder, "metadata.json")
    with open(merged_meta_path, "w", encoding="utf-8") as f:
        json.dump(merged_metadata, f, indent=2)

    print(f"Merged {len(merged_metadata)} entries into {merged_folder}")
