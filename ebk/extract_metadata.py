import os
import xmltodict
from typing import Dict, Optional
from slugify import slugify
import PyPDF2
from ebooklib import epub

def extract_metadata_from_opf(opf_file: str) -> Dict:
    """
    Parse a Calibre OPF file into a simplified dictionary structure (Dublin Core).
    Returns a dict with keys:
      - title
      - creators
      - subjects
      - description
      - language
      - date
      - identifiers
    """
    try:
        with open(opf_file, "r", encoding="utf-8") as f:
            opf_dict = xmltodict.parse(f.read(), process_namespaces=False)
    except Exception as e:
        print(f"[extract_metadata_from_opf] Error reading '{opf_file}': {e}")
        return {}

    package = opf_dict.get("package", {})
    metadata = package.get("metadata", {})

    # Prepare simplified structure
    simplified = {
        "title": metadata.get("dc:title", metadata.get("title")),
        "creators": [],
        "subjects": [],
        "description": metadata.get("dc:description", metadata.get("description")),
        "language": metadata.get("dc:language", metadata.get("language")),
        "date": metadata.get("dc:date", metadata.get("date")),
        "identifiers": {},
    }

    # -- Creators
    creators = metadata.get("dc:creator", metadata.get("creator", []))
    if isinstance(creators, list):
        simplified["creators"] = [
            c.get("#text", "").strip() if isinstance(c, dict) else c
            for c in creators
        ]
    elif isinstance(creators, dict):
        simplified["creators"] = [creators.get("#text", "").strip()]
    elif isinstance(creators, str):
        simplified["creators"] = [creators.strip()]

    # -- Subjects
    subjects = metadata.get("dc:subject", metadata.get("subject", []))
    if isinstance(subjects, list):
        simplified["subjects"] = [s.strip() for s in subjects]
    elif isinstance(subjects, str):
        simplified["subjects"] = [subjects.strip()]

    # -- Identifiers
    identifiers = metadata.get("dc:identifier", metadata.get("identifier", []))
    if isinstance(identifiers, list):
        for identifier in identifiers:
            if isinstance(identifier, dict):
                scheme = identifier.get("@opf:scheme", "unknown")
                text = identifier.get("#text", "").strip()
                simplified["identifiers"][scheme] = text
            else:
                simplified["identifiers"]["unknown"] = identifier
    elif isinstance(identifiers, dict):
        scheme = identifiers.get("@opf:scheme", "unknown")
        text = identifiers.get("#text", "").strip()
        simplified["identifiers"][scheme] = text

    return simplified


def extract_metadata_from_pdf(pdf_path: str) -> Dict:
    """
    Extract metadata from a PDF file using PyPDF2.
    Returns a dictionary with the same keys as the OPF-based dict.
    """
    metadata = {
        "title": None,
        "creators": [],
        "subjects": [],
        "description": None,
        "language": None,
        "date": None,
        "identifiers": {},
    }

    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            info = reader.metadata or {}

        # NOTE: Depending on PyPDF2 version, metadata keys can differ
        # e.g. info.title vs info.get('/Title')
        pdf_title = info.get("/Title", None) or info.get("title", None)
        pdf_author = info.get("/Author", None) or info.get("author", None)
        pdf_subject = info.get("/Subject", None) or info.get("subject", None)
        pdf_creator = info.get("/Creator", None) or info.get("creator", None)
        pdf_creation_date = info.get("/CreationDate", None)

        if pdf_title:
            metadata["title"] = pdf_title.strip()
        if pdf_author:
            metadata["creators"] = [pdf_author.strip()]
        if pdf_subject:
            metadata["subjects"] = [sub.strip() for sub in pdf_subject.split(",")]
            metadata["description"] = pdf_subject.strip()
        if pdf_creator:
            # Sometimes PDF can have a separate "Creator" field, which could be
            # a software tool. For now, we won't treat it as the 'author' but you could if needed.
            pass

        if pdf_creation_date and len(pdf_creation_date) >= 10:
            # Format: 'D:YYYYMMDDhhmmss'
            # We'll extract 'YYYY-MM-DD'
            date_str = pdf_creation_date[2:10]  # e.g., 20210101
            metadata["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        # Language not typically stored in PDF metadata
        metadata["language"] = None

        # For an "identifier," we don't really have a built-in PDF field, so it's optional
        metadata["identifiers"] = {"pdf:identifier": pdf_path}
    except Exception as e:
        print(f"[extract_metadata_from_pdf] Error reading '{pdf_path}': {e}")

    return metadata


def extract_metadata_from_epub(epub_path: str) -> Dict:
    """
    Extract metadata from an EPUB file using ebooklib.
    Returns a dictionary with the same keys as the OPF-based dict.
    """
    metadata = {
        "title": None,
        "creators": [],
        "subjects": [],
        "description": None,
        "language": None,
        "date": None,
        "identifiers": {},
    }

    try:
        book = epub.read_epub(epub_path)

        # Title
        dc_title = book.get_metadata("DC", "title")
        if dc_title:
            metadata["title"] = dc_title[0][0]

        # Creators
        dc_creators = book.get_metadata("DC", "creator")
        if dc_creators:
            metadata["creators"] = [c[0] for c in dc_creators]

        # Subjects
        dc_subjects = book.get_metadata("DC", "subject")
        if dc_subjects:
            metadata["subjects"] = [s[0] for s in dc_subjects]

        # Description
        dc_description = book.get_metadata("DC", "description")
        if dc_description:
            metadata["description"] = dc_description[0][0]

        # Language
        dc_language = book.get_metadata("DC", "language")
        if dc_language:
            metadata["language"] = dc_language[0][0]

        # Date
        dc_date = book.get_metadata("DC", "date")
        if dc_date:
            metadata["date"] = dc_date[0][0]

        # Identifiers
        identifiers = book.get_metadata("DC", "identifier")
        if identifiers:
            for identifier in identifiers:
                # identifier is a tuple: (value, { 'scheme': '...' })
                ident_value, ident_attrs = identifier
                scheme = ident_attrs.get("scheme", "unknown")
                metadata["identifiers"][scheme] = ident_value
    except Exception as e:
        print(f"[extract_metadata_from_epub] Error reading '{epub_path}': {e}")

    return metadata


def extract_metadata_from_path(file_path: str) -> Dict:
    """
    Fallback metadata extraction by interpreting the path as <...>/<author>/<title>.
    Slugify them to remove invalid characters.
    """
    metadata = {
        "title": "unknown_title",
        "creators": ["unknown_author"],
        "subjects": [],
        "description": "",
        "language": None,
        "date": None,
        "identifiers": {},
    }

    try:
        path_parts = file_path.split(os.sep)
        # Last part is likely the file name; the second last part might be the "author"
        if len(path_parts) >= 2:
            author = path_parts[-2]
            title = os.path.splitext(path_parts[-1])[0]  # remove extension
            metadata["title"] = slugify(title)
            metadata["creators"] = [slugify(author)]
    except Exception as e:
        print(f"[extract_metadata_from_path] Error with '{file_path}': {e}")

    return metadata


def merge_metadata(primary: Dict, fallback: Dict) -> Dict:
    """
    Merge two metadata dicts, favoring 'primary'.
    If a field is missing in 'primary', fill in from 'fallback'.
    For 'identifiers', union them.
    """
    merged = dict(primary)  # copy primary

    # List of top-level fields
    fields = ["title", "creators", "subjects", "description", "language", "date"]
    for field in fields:
        if not merged.get(field) and fallback.get(field):
            merged[field] = fallback[field]

    # Identifiers
    if "identifiers" not in merged:
        merged["identifiers"] = {}
    for scheme, val in fallback.get("identifiers", {}).items():
        if scheme not in merged["identifiers"]:
            merged["identifiers"][scheme] = val

    return merged


def extract_metadata(ebook_file: str, opf_file: Optional[str] = None) -> Dict:
    """
    High-level function to extract metadata from either:
      - OPF file (if provided)
      - The ebook_file (PDF, EPUB, or fallback from path)
    Then merges them, giving priority to OPF data.
    
    Returns a final merged dictionary with keys:
      - title
      - creators
      - subjects
      - description
      - language
      - date
      - identifiers
    """

    # 1. Extract from OPF if we have it
    opf_metadata = {}
    if opf_file and os.path.isfile(opf_file):
        opf_metadata = extract_metadata_from_opf(opf_file)

    # 2. Extract from ebook_file (pdf/epub/path fallback)
    _, ext = os.path.splitext(ebook_file.lower())
    if ext == ".pdf":
        ebook_metadata = extract_metadata_from_pdf(ebook_file)
    elif ext == ".epub":
        ebook_metadata = extract_metadata_from_epub(ebook_file)
    else:
        ebook_metadata = extract_metadata_from_path(ebook_file)

    # 3. Merge them: OPF is primary, ebook is fallback
    final = merge_metadata(opf_metadata, ebook_metadata)
    return final
