import json
import os
import zipfile
from io import BytesIO
import streamlit as st
import logging
import streamlit as st
import base64
from ebooklib import epub
from bs4 import BeautifulSoup

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


def display_pdf(pdf_data):
    # Encode PDF data as base64
    base64_pdf = base64.b64encode(pdf_data).decode('utf-8')
    pdf_display = f"""
    <iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="500" style="border: none;"></iframe>
    """
    st.markdown(pdf_display, unsafe_allow_html=True)

def display_epub(epub_data):
    # Parse EPUB file
    book = epub.read_epub(epub_data)
    content = ""
    for item in book.items:
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Extract HTML content
            soup = BeautifulSoup(item.content, 'html.parser')
            content += str(soup)
    # Display the extracted content
    st.markdown(content, unsafe_allow_html=True)

