import os
import shutil
from slugify import slugify
import json
from .extract_metadata import opf_to_dublin_core

META_DATA_JSON_FILENAME = "metadata.json"
META_DATA_OPF_FILENAME = "metadata.opf"

def convert_calibre(calibre_folder: str,
                    output_folder: str):
    """Flatten a Calibre library into a single folder with JSON metadata."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    metadata_list = []

    for root, _, files in os.walk(calibre_folder):
        if "metadata.opf" in files:
            opf_file = os.path.join(root, META_DATA_OPF_FILENAME)
            try:
                # Extract metadata
                metadata = opf_to_dublin_core(opf_file)
                # Generate base file name
                title_slug = slugify(metadata.get("title", "unknown_title"))
                creator_slug = slugify(metadata["creators"][0]) if metadata["creators"] else "unknown_creator"
                identifier = metadata["identifiers"].get("calibre", metadata["identifiers"].get("uuid", "unknown_id"))
                base_name = f"{title_slug}__{creator_slug}__{identifier}"
                
                # Process ebook files
                ebook_files = [f for f in files if f.endswith(('.pdf', '.epub', '.mobi', '.azw3', '.txt'))]
                for ebook_file in ebook_files:
                    ext = os.path.splitext(ebook_file)[1]
                    target_path = os.path.join(output_folder, f"{base_name}{ext}")
                    shutil.copy(os.path.join(root, ebook_file), target_path)
                
                # Process cover file
                cover_file = next((f for f in files if f == "cover.jpg"), None)
                if cover_file:
                    cover_target_path = os.path.join(output_folder, f"{base_name}_cover.jpg")
                    shutil.copy(os.path.join(root, cover_file), cover_target_path)
                    metadata["cover_path"] = os.path.relpath(cover_target_path, output_folder)

                # Update file paths in metadata
                metadata["file_paths"] = [
                    os.path.relpath(os.path.join(output_folder, f"{base_name}{os.path.splitext(f)[1]}"), output_folder)
                    for f in ebook_files
                ]

                metadata_list.append(metadata)
            except Exception as e:
                print(f"Error processing {opf_file}: {e}")

    metadata_file_path = os.path.join(output_folder, META_DATA_JSON_FILENAME)
    with open(metadata_file_path, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=2)        
        

