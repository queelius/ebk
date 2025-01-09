import os
from PyPDF2 import PdfReader
from ebooklib import epub
import re
import xmltodict

def opf_to_dublin_core(opf_file: str) -> dict:
    """Parse a Calibre OPF file into a simplified structure for metadata."""
    with open(opf_file, "r", encoding="utf-8") as f:
        opf_dict = xmltodict.parse(f.read(), process_namespaces=False)

    # Extract metadata section
    package = opf_dict.get("package", {})
    metadata = package.get("metadata", {})

    # Extract core metadata fields
    simplified = {
        "title": metadata.get("dc:title", metadata.get("title")),
        "creators": [],
        "subjects": [],
        "description": metadata.get("dc:description", metadata.get("description")),
        "language": metadata.get("dc:language", metadata.get("language")),
        "date": metadata.get("dc:date", metadata.get("date")),
        "publisher": metadata.get("dc:publisher", metadata.get("publisher")),
        "rights": metadata.get("dc:rights", metadata.get("rights")),
        "identifiers": {},
    }

    # Extract creators (handles single and multiple entries)
    creators = metadata.get("dc:creator", metadata.get("creator", []))
    if isinstance(creators, list):
        simplified["creators"] = [creator.get("#text", "").strip() if isinstance(creator, dict) else creator for creator in creators]
    elif isinstance(creators, dict):
        simplified["creators"] = [creators.get("#text", "").strip()]
    elif isinstance(creators, str):
        simplified["creators"] = [creators.strip()]

    # Extract subjects (handles single and multiple entries)
    subjects = metadata.get("dc:subject", metadata.get("subject", []))
    if isinstance(subjects, list):
        simplified["subjects"] = [subject.strip() for subject in subjects]
    elif isinstance(subjects, str):
        simplified["subjects"] = [subjects.strip()]

    # Extract identifiers (handles single and multiple entries)
    identifiers = metadata.get("dc:identifier", metadata.get("identifier", []))
    if isinstance(identifiers, list):
        for identifier in identifiers:
            scheme = identifier.get("@opf:scheme", "unknown") if isinstance(identifier, dict) else "unknown"
            simplified["identifiers"][scheme] = identifier.get("#text", "").strip() if isinstance(identifier, dict) else identifier
    elif isinstance(identifiers, dict):
        scheme = identifiers.get("@opf:scheme", "unknown")
        simplified["identifiers"][scheme] = identifiers.get("#text", "").strip()

    return simplified


def extract_metadata_from_ebook(ebook_path: str) -> dict:
    """
    Attempt to extract metadata from various ebook formats when no OPF file is found.
    Returns a dict with the same structure you use for OPF-based metadata.
    {
        "title": str,
        "creators": [str],
        "subjects": [str],
        "description": str,
        "language": str,
        "date": str,
        "identifiers": {},
    }
    """
    # Basic skeleton of metadata in your existing style
    metadata = {
        "title": None,
        "creators": [],
        "subjects": [],
        "description": None,
        "language": None,
        "date": None,
        "identifiers": {}
    }
    
    # Use the file extension to decide how to parse
    _, ext = os.path.splitext(ebook_path)
    ext = ext.lower()

    try:
        if ext == ".pdf":
            # Parse with PyPDF2
            reader = PdfReader(ebook_path)
            pdf_info = reader.metadata

            if pdf_info is not None:
                metadata["title"] = pdf_info.title if pdf_info.title else None
                if pdf_info.author:
                    # If authors field is a single string, split on possible delimiters if needed
                    authors = [auth.strip() for auth in re.split("[,;]", pdf_info.author)]
                    metadata["creators"] = authors
                # Additional fields like creationDate, subject, etc. might be used
                # but are less standardized

        elif ext == ".epub":
            # Parse with ebooklib
            book = epub.read_epub(ebook_path)

            # The following fields often appear in ePub metadata
            if book.metadata:
                # ebooklib stores metadata in a dict keyed by namespace, e.g., 'DC'
                # The standard keys for ePub's Dublin Core are often something like:
                # book.metadata['DC']['title'], book.metadata['DC']['creator'], etc.
                
                dc_dict = book.metadata.get("DC", {})
                
                # Titles
                if "title" in dc_dict:
                    metadata["title"] = dc_dict["title"][0][0]
                
                # Creators
                if "creator" in dc_dict:
                    metadata["creators"] = [item[0] for item in dc_dict["creator"]]
                
                # Description
                if "description" in dc_dict:
                    metadata["description"] = dc_dict["description"][0][0]
                
                # Language
                if "language" in dc_dict:
                    metadata["language"] = dc_dict["language"][0][0]
                
                # Date
                if "date" in dc_dict:
                    metadata["date"] = dc_dict["date"][0][0]
                
                # Subjects
                if "subject" in dc_dict:
                    metadata["subjects"] = [item[0] for item in dc_dict["subject"]]

        else:
            #  - Attempt to read the first line from the file or 
            #    rely on the filename as a last resort.
            base_filename = os.path.splitext(os.path.basename(ebook_path))[0]
            
            # Possibly you have a naming scheme like "Title - Author"
            guess_parts = re.split(r'[\-_]', base_filename)
            if guess_parts:
                metadata["title"] = guess_parts[0].strip()
            if len(guess_parts) > 1:
                # Everything beyond the first might be considered the creator guess
                metadata["creators"] = [" ".join(guess_parts[1:]).strip()]

        elif ext == ".txt":
            # For plain text, there's typically no embedded metadata.
            # Let's just set the title from the filename:
            base_filename = os.path.splitext(os.path.basename(ebook_path))[0]
            metadata["title"] = base_filename
            # No creators or other info. A possible approach:
            #  - If you have naming convention "Author - Title.txt", parse it.
            #  - Or if the folder name indicates something, parse that.

        else:
            # Unrecognized format, fallback
            base_filename = os.path.splitext(os.path.basename(ebook_path))[0]
            metadata["title"] = base_filename

    except Exception as e:
        print(f"Error extracting metadata from {ebook_path}: {e}")
        # In case of error, fallback to filename
        base_filename = os.path.splitext(os.path.basename(ebook_path))[0]
        metadata["title"] = base_filename

    # Provide minimal fallback if title is still None
    if not metadata["title"]:
        metadata["title"] = os.path.splitext(os.path.basename(ebook_path))[0]
    
    return metadata
