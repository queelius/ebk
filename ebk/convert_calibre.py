import os
import shutil
import json
from slugify import slugify
from .extract_metadata import extract_metadata

def convert_calibre(calibre_folder: str, output_folder: str):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    metadata_list = []

    for root, _, files in os.walk(calibre_folder):
        # Look for OPF
        opf_file_path = os.path.join(root, "metadata.opf")
        
        # Gather valid ebook files
        ebook_files = [
            f for f in files
            if f.lower().endswith((".pdf", ".epub", ".mobi", ".azw3", ".txt"))
        ]
        
        if not ebook_files:
            continue  # skip if no recognized ebook files

        # Pick the "primary" ebook file (first one, or whichever logic you like)
        primary_ebook_file = ebook_files[0]
        ebook_full_path = os.path.join(root, primary_ebook_file)

        # Extract metadata (OPF + ebook)
        metadata = extract_metadata(ebook_full_path, opf_file_path)

        # Generate base name
        title_slug = slugify(metadata.get("title", "unknown_title"))
        creator_slug = slugify(metadata["creators"][0]) if metadata.get("creators") else "unknown_creator"
        # Try to grab an identifier from 'identifiers', or fallback
        identifier = (metadata["identifiers"].get("calibre")
                      or metadata["identifiers"].get("uuid")
                      or "unknown_id")

        base_name = f"{title_slug}__{creator_slug}__{identifier}"

        # Copy ebooks
        file_paths = []
        for ebook_file in ebook_files:
            _, ext = os.path.splitext(ebook_file)
            src = os.path.join(root, ebook_file)
            dst = os.path.join(output_folder, f"{base_name}{ext}")
            shutil.copy(src, dst)
            file_paths.append(os.path.relpath(dst, output_folder))

        # Optionally handle cover.jpg
        if "cover.jpg" in files:
            cover_src = os.path.join(root, "cover.jpg")
            cover_dst = os.path.join(output_folder, f"{base_name}_cover.jpg")
            shutil.copy(cover_src, cover_dst)
            metadata["cover_path"] = os.path.relpath(cover_dst, output_folder)

        # Store relative paths in metadata
        metadata["file_paths"] = file_paths
        metadata_list.append(metadata)

    # Write out metadata.json
    output_json = os.path.join(output_folder, "metadata.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("calibre_folder", help="Path to your Calibre library")
    parser.add_argument("output_folder", help="Path to the output folder")
    args = parser.parse_args()

    convert_calibre(args.calibre_folder, args.output_folder)
