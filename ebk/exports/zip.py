import os
import zipfile
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def export_zipfile(lib_dir, zip_file):
    """
    Export ebk library to a ZIP archive.

    Args:
        lib_dir (str): Path to the ebk library directory to export (contains `metadata.json` and ebook-related files)
        zip_file (str): Path to the output ZIP file
    """
    lib_dir = Path(lib_dir)

    # just want to take the entire directory and zip it

    with zipfile.ZipFile(zip_file, "w") as z:
        for root, _, files in os.walk(lib_dir):
            for file in files:
                file_path = Path(root) / file
                logging.debug(f"Adding file to zip: {file_path}")
                z.write(file_path, arcname=file_path.relative_to(lib_dir))
