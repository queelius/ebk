import os
import json
import shutil

from pathlib import Path

import fitz
from PIL import Image
from io import BytesIO

from typing import Dict
from slugify import slugify
from ..extract_metadata import extract_metadata_from_pdf
from ..ident import add_unique_id
from ..utils import get_unique_filename

def import_ebooks(ebooks_dir, output_dir):
    """
    Implement the logic to import raw ebook files.
    This could involve copying files, inferring metadata, etc.
    """

    # create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # create the metadata file in the output directory
    metadata_file = os.path.join(output_dir, "metadata.json")
    # open the metadata file in write mode
    with open(metadata_file, "w") as metadata:
        metadata_list = []
        # recursively get the list of files in the directory
        for root, _, files in os.walk(ebooks_dir):
            for file in files:

                try:
                    print(f"Processing file: {file} in {root}")

                    # create the dictionary item for file
                    item = {
                        "title": file
                    }
                    path = Path(root) / Path(file)

                    # infer the format of the file
                    _, ext = os.path.splitext(file)

                    cover_image = None  
                    if ext == ".pdf":
                        metadata = extract_metadata_from_pdf(path)
                        cover_image = extract_cover_from_pdf(path)
                    else:
                        continue

                    metadata = {key: item.get(key) or metadata.get(key) or value for key, value in metadata.items()}

                    item["root"] = root
                    item["source_folder"] = ebooks_dir
                    item["output_folder"] = output_dir
                    item["imported_from"] = "ebooks"
                    item["virtual_libs"] = [slugify(output_dir)]

                    title_slug = slugify(item.get("title", "unknown_title"))
                    creator_slug = slugify(item.get("creators", ["unknown_creator"])[0])
                    base_name = f"{title_slug}__{creator_slug}"

                    _, ext = os.path.splitext(file)
                    src = os.path.join(root, file)
                    dst = os.path.join(output_dir, f"{base_name}{ext}")
                    dst = get_unique_filename(dst)
                    shutil.copy(src, dst)
                    file_paths = [ os.path.relpath(dst, output_dir) ]
                    item["file_paths"] = file_paths

                    if cover_image:
                        cover_image_file = os.path.join(output_dir, f"{base_name}_cover.jpg")
                        print(f"Writing cover image to {cover_image_file}")
                        with open(cover_image_file, "wb") as cover:
                            cover.write(cover_image)

                        item["cover_path"] = os.path.relpath(cover_image_file, output_dir)





                    metadata_list.append(item)


                except Exception as e:
                    print(f"Error processing file: {file} in {root}: {e}")

        for entry in metadata_list:
            try:
                add_unique_id(entry)
            except Exception as e:
                print(f"Error adding unique ID to entry: {entry}: {e}")

        with open(metadata_file, "w") as f:
            json.dump(metadata_list, f, indent=2)
                    

def extract_cover_from_pdf(pdf_path):
    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    first_page = pdf_document[0]

    # Render the first page as a PNG image
    pix = first_page.get_pixmap()
    image = Image.open(BytesIO(pix.tobytes(output="png")))

    # Create a thumbnail
    image.thumbnail((256, 256))
    
    # Convert the image to JPEG bytes
    image_bytes = BytesIO()
    image.save(image_bytes, format="JPEG")
    return image_bytes.getvalue()
