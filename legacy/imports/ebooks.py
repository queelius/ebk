import os
import json
import shutil

from pathlib import Path

import fitz
from PIL import Image
from io import BytesIO

from rich.console import Console

from typing import Dict
from slugify import slugify
from ..extract_metadata import extract_metadata_from_pdf
from ..ident import add_unique_id
from ..utils import get_unique_filename

import logging

def import_ebooks(ebooks_dir, output_dir, output_formats):
    """
    Import ebooks from a directory into the library.

    Args:
        ebooks_dir (str): Path to the directory containing the ebooks
        output_dir (str): Path to the output directory
        output_formats (list): List of output formats to convert the ebooks to
    """

    logger = logging.getLogger(__name__)

    if os.path.exists(output_dir):
        logger.error(f"Output directory already exists: {output_dir}")
        return
    os.makedirs(output_dir)

    metadata_list = []
    for root, _, files in os.walk(ebooks_dir):
        for file in files:            
            try:
                # create the dictionary item for file
                item = {
                    "title": file
                }
                path = Path(root) / Path(file)

                # infer the format of the file
                _, ext = os.path.splitext(file)
                ext = ext.lower().strip(".")
                if ext not in output_formats:
                    continue

                cover_image = None  
                if ext == "pdf":
                    metadata = extract_metadata_from_pdf(path)
                    cover_image = extract_cover_from_pdf(path)
                else:
                    continue

                logger.debug(f"Importing ebook {file} in {root}")
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
                    with open(cover_image_file, "wb") as cover:
                        cover.write(cover_image)

                    item["cover_path"] = os.path.relpath(cover_image_file, output_dir)
                metadata_list.append(item)

            except Exception as e:
                logger.error(f"Error processing file {file} in {root}: {e}")

        for entry in metadata_list:
            add_unique_id(entry)

        metadata_file = os.path.join(output_dir, "metadata.json")
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
