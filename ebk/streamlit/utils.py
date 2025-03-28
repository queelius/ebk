import json
import os
import zipfile
from io import BytesIO
import streamlit as st
import logging
import streamlit as st
from typing import List, Dict
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

def load_metadata(metadata_content: BytesIO) -> list:
    """
    Loads metadata from the uploaded JSON file.
    Returns a list of dictionaries.
    """
    try:
        data = json.load(metadata_content)
        logger.debug("Metadata loaded successfully.")
        return data
    except json.JSONDecodeError as e:
        st.error(f"JSON decoding error: {e}")
        logger.error(f"JSONDecodeError: {e}")
        return []
    except Exception as e:
        st.error(f"Unexpected error loading metadata.json: {e}")
        logger.error(f"Unexpected error: {e}")
        return []

def extract_zip(zip_bytes: BytesIO) -> dict:
    """
    Extracts a ZIP file in-memory and returns a dictionary of its contents.
    Keys are file names, and values are BytesIO objects containing the file data.
    """
    extracted_files = {}
    try:
        with zipfile.ZipFile(zip_bytes) as z:
            for file_info in z.infolist():
                if not file_info.is_dir():
                    with z.open(file_info) as f:
                        normalized_path = os.path.normpath(file_info.filename)
                        # Prevent path traversal
                        if os.path.commonprefix([normalized_path, os.path.basename(normalized_path)]) != "":
                            extracted_files[normalized_path] = BytesIO(f.read())
                            logger.debug(f"Extracted: {normalized_path}")
        logger.debug("ZIP archive extracted successfully.")
        return extracted_files
    except zipfile.BadZipFile:
        st.error("The uploaded file is not a valid ZIP archive.")
        logger.error("BadZipFile encountered.")
        return {}
    except Exception as e:
        st.error(f"Error extracting ZIP file: {e}")
        logger.error(f"Exception during ZIP extraction: {e}")
        return {}



def get_files(lib_dir: str) -> dict:
    """
    Gets the files in lib_dir and returns a dictionary of its contents.
    Keys are file names, and values are BytesIO objects containing the file data.
    """
    files = {}
    try:
        for root, _, filenames in os.walk(lib_dir):
            for filename in filenames:
                file_path = os.path.join(root, filename)
                with open(file_path, "rb") as f:
                    data = f.read()
                    files[filename] = BytesIO(data)
                    # get byte length of file
                    #file_length = files[filename].getbuffer().nbytes
                    #if filename.endswith('.djvu'):
                    #    print(f"Read file: {filename}")
                    #    print(f"File length: {file_length}")
                    #logger.debug(f"Added file: {filename}")
        logger.debug("Files loaded successfully.")
        return files
    except Exception as e:
        st.error(f"Error loading files: {e}")
        logger.error(f"Exception during file loading: {e}")
        return {}