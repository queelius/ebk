import os
import shutil
import json
from slugify import slugify
from typing import Dict
import logging
from ..extract_metadata import extract_metadata
from ..ident import add_unique_id
from ..utils import get_unique_filename

logger = logging.getLogger(__name__)

ebook_exts = (".pdf", ".epub", ".mobi", ".azw3", ".txt", ".docx", ".odt",
              ".html", ".rtf", ".md", ".fb2", ".cbz", ".cbr", ".djvu",
              ".xps", ".ibooks", ".azw", ".lit", ".pdb", ".prc", ".lrf",
              ".pdb", ".pml", ".rb", ".snb", ".tcr", ".txtz", ".azw1")                

def import_calibre(calibre_dir: str,
                   output_dir: str,
                   ebook_exts: tuple = ebook_exts):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    metadata_list = []

    for root, _, files in os.walk(calibre_dir):
        # Look for OPF
        opf_file_path = os.path.join(root, "metadata.opf")
        
        # Gather valid ebook files
        ebook_files = [f for f in files if f.lower().endswith(ebook_exts)]
        
        if not ebook_files:
            logger.debug(f"No recognized ebook files found in {root}. Skipping.")
            continue  # skip if no recognized ebook files

        # Pick the "primary" ebook file. This is arbitrary and can be changed.
        primary_ebook_file = ebook_files[0]
        ebook_full_path = os.path.join(root, primary_ebook_file)

        # Extract metadata
        if os.path.exists(opf_file_path):
            logger.debug(f"Found metadata.opf in {root}. Extracting metadata from OPF.")
            metadata = extract_metadata(ebook_full_path, opf_file_path)
        else:
            logger.warning(f"No metadata.opf found in {root}. Inferring metadata from ebook files.")
            metadata = extract_metadata(ebook_full_path)  # Only ebook file path is provided

        # Extract metadata (OPF + ebook)
        metadata = extract_metadata(ebook_full_path, opf_file_path)
        metadata["root"] = root
        metadata["source_folder"] = calibre_dir
        metadata["output_folder"] = output_dir
        metadata["imported_from"] = "calibre"
        metadata["virtual_libs"] = [slugify(output_dir)]

        # Generate base name
        title_slug = slugify(metadata.get("title", "unknown_title"))
        creator_slug = slugify(
            metadata["creators"][0]) if metadata.get("creators") else "unknown_creator"

        base_name = f"{title_slug}__{creator_slug}"

        # Copy ebooks
        file_paths = []
        for ebook_file in ebook_files:
            _, ext = os.path.splitext(ebook_file)
            src = os.path.join(root, ebook_file)
            dst = os.path.join(output_dir, f"{base_name}{ext}")
            dst = get_unique_filename(dst)
            shutil.copy(src, dst)
            file_paths.append(os.path.relpath(dst, output_dir))

        # Optionally handle cover.jpg
        if "cover.jpg" in files:
            cover_src = os.path.join(root, "cover.jpg")
            cover_dst = os.path.join(output_dir, f"{base_name}_cover.jpg")
            shutil.copy(cover_src, cover_dst)
            metadata["cover_path"] = os.path.relpath(cover_dst, output_dir)

        # Store relative paths in metadata
        metadata["file_paths"] = file_paths
        metadata_list.append(metadata)

    for entry in metadata_list:
        add_unique_id(entry)

    # Write out metadata.json
    output_json = os.path.join(output_dir, "metadata.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)


def ensure_metadata_completeness(metadata: Dict) -> Dict:
    """
    Ensure that all required metadata fields are present.
    If a field is missing or empty, attempt to infer or set default values.
    
    Args:
        metadata (Dict): The metadata dictionary extracted from OPF or inferred.
    
    Returns:
        Dict: The updated metadata dictionary with all necessary fields.
    """
    required_fields = ["title", "creators",
                       "subjects", "description",
                       "language", "date", "identifiers",
                       "file_paths", "cover_path", "unique_id",
                       "source_folder", "output_folder",
                       "imported_from", "virtual_libs"]
    for field in required_fields:
        if field not in metadata:
            if field == "creators":
                metadata[field] = ["Unknown Author"]
                logger.debug(f"Set default value for '{field}'.")
            elif field == "subjects":
                metadata[field] = []
                logger.debug(f"Set default value for '{field}'.")
            elif field == "description":
                metadata[field] = "No description available."
                logger.debug(f"Set default value for '{field}'.")
            elif field == "language":
                metadata[field] = "en"  # Default to English
                logger.debug(f"Set default value for '{field}'.")
            elif field == "date":
                metadata[field] = None  # Unknown date
                logger.debug(f"Set default value for '{field}'.")
            elif field == "title":
                metadata[field] = "Unknown Title"
                logger.debug(f"Set default value for '{field}'.")
            elif field == "identifiers":
                metadata[field] = {}
                logger.debug(f"Set default value for '{field}'.")
            elif field == "file_paths":
                metadata[field] = []
                logger.debug(f"Set default value for '{field}'.")
            elif field == "cover_path":
                metadata[field] = None
                logger.debug(f"Set default value for '{field}'.")
            elif field == "unique_id":
                metadata[field] = None
                logger.debug(f"Set default value for '{field}'.")
    
    return metadata