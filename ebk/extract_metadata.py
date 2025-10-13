import os
import xmltodict
from typing import Dict, Optional
from slugify import slugify
import pypdf
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
      - publisher
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
        "creators": None,
        "contributors": None,
        "subjects": None,
        "description": metadata.get("dc:description", metadata.get("description")),
        "language": metadata.get("dc:language", metadata.get("language")),
        "date": metadata.get("dc:date", metadata.get("date")),
        "publisher": metadata.get("dc:publisher", metadata.get("publisher")),
        "identifiers": None,
        "rights": metadata.get("dc:rights", metadata.get("rights")),
        "source": metadata.get("dc:source", metadata.get("source")),
        "series": None,
        "series_index": None
    }

    # -- Creators
    creators = metadata.get("dc:creator", metadata.get("creator"))
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
    subjects = metadata.get("dc:subject", metadata.get("subject"))
    if isinstance(subjects, list):
        simplified["subjects"] = [s.strip() for s in subjects]
    elif isinstance(subjects, str):
        simplified["subjects"] = [subjects.strip()]

    # -- Identifiers
    identifiers = metadata.get("dc:identifier", metadata.get("identifier"))
    if isinstance(identifiers, list):
        simplified["identifiers"] = {}
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

    # -- Contributors (editors, translators, etc)
    contributors_raw = metadata.get("dc:contributor", metadata.get("contributor"))
    if contributors_raw:
        simplified["contributors"] = []
        if isinstance(contributors_raw, list):
            for contrib in contributors_raw:
                if isinstance(contrib, dict):
                    name = contrib.get("#text", "").strip()
                    role = contrib.get("@opf:role", "contributor")
                    file_as = contrib.get("@opf:file-as", "")
                    if name:
                        simplified["contributors"].append({
                            "name": name,
                            "role": role,
                            "file_as": file_as
                        })
                elif isinstance(contrib, str):
                    simplified["contributors"].append({
                        "name": contrib.strip(),
                        "role": "contributor",
                        "file_as": ""
                    })
        elif isinstance(contributors_raw, dict):
            name = contributors_raw.get("#text", "").strip()
            role = contributors_raw.get("@opf:role", "contributor")
            file_as = contributors_raw.get("@opf:file-as", "")
            if name:
                simplified["contributors"] = [{
                    "name": name,
                    "role": role,
                    "file_as": file_as
                }]

    # -- Calibre-specific metadata (series, etc)
    # Look for meta tags with name attributes
    meta_tags = metadata.get("meta", [])
    if not isinstance(meta_tags, list):
        meta_tags = [meta_tags] if meta_tags else []

    for meta in meta_tags:
        if isinstance(meta, dict):
            meta_name = meta.get("@name", "")
            meta_content = meta.get("@content", "")

            if meta_name == "calibre:series" and meta_content:
                simplified["series"] = meta_content
            elif meta_name == "calibre:series_index" and meta_content:
                try:
                    simplified["series_index"] = float(meta_content)
                except (ValueError, TypeError):
                    pass

    return simplified


def extract_metadata_from_pdf(pdf_path: str) -> Dict:
    """
    Extract metadata from a PDF file using pypdf.
    Returns a dictionary with the same keys as the OPF-based dict.
    """

    metadata = {
        "title": None,
        "creators": None,
        "subjects": None,
        "description": None,
        "language": None,
        "date": None,
        "publisher": None,
        "identifiers": None,
        "keywords": None,
        "creator_application": None,
    }

    try:
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            info = reader.metadata or {}

        # NOTE: Depending on pypdf version, metadata keys can differ
        # e.g. info.title vs info.get('/Title')
        pdf_title = info.get("/Title", None) or info.get("title", None)
        pdf_author = info.get("/Author", None) or info.get("author", None)
        pdf_subject = info.get("/Subject", None) or info.get("subject", None)
        pdf_keywords = info.get("/Keywords", None) or info.get("keywords", None)
        pdf_creator = info.get("/Creator", None) or info.get("creator", None)  # Application used
        pdf_producer = info.get("/Producer", None) or info.get("producer", None)
        pdf_publisher = info.get("/Publisher", None) or info.get("publisher", None)
        pdf_creation_date = info.get("/CreationDate", None)

        if pdf_title:
            metadata["title"] = pdf_title.strip()
        if pdf_author:
            metadata["creators"] = [pdf_author.strip()]
        if pdf_subject:
            metadata["subjects"] = [sub.strip() for sub in pdf_subject.split(",")]
            metadata["description"] = pdf_subject.strip()

        if pdf_creation_date and len(pdf_creation_date) >= 10:
            # Format: 'D:YYYYMMDDhhmmss'
            # We'll extract 'YYYY-MM-DD'
            date_str = pdf_creation_date[2:10]  # e.g., 20210101
            metadata["date"] = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        # Language not typically stored in PDF metadata
        metadata["language"] = "unknown-language"

        # For an "identifier," we don't really have a built-in PDF field, so it's optional
        metadata["identifiers"] = {"pdf:identifier": pdf_path}

        if pdf_keywords:
            metadata["keywords"] = [kw.strip() for kw in pdf_keywords.split(",") if kw.strip()]

        # Creator is the application that created the PDF (e.g., LaTeX, Word)
        if pdf_creator:
            metadata["creator_application"] = pdf_creator.strip()

        # Publisher: prefer explicit Publisher field, fallback to Producer
        if pdf_publisher:
            metadata["publisher"] = pdf_publisher.strip()
        elif pdf_producer and not pdf_creator:
            # Only use producer as publisher if there's no creator app
            metadata["publisher"] = pdf_producer.strip()

        metadata["file_paths"] = [pdf_path]


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
        "title": None,
        "creators": [],
        "subjects": [],
        "description": "",
        "language": "unknown-language",
        "date": "unknown-date",
        "identifiers": {}
    }

    try:
        path_parts = file_path.split(os.sep)
        # path_parts: ['base_dir', 'author_dir', 'title', 'title - author.ext'] ]
        title = path_parts[-2]
        creators = path_parts[1].split(",")
        metadata["title"] = title
        metadata["creators"] = creators
    except Exception as e:
        print(f"[extract_metadata_from_path] Error with '{file_path}': {e}")

    return metadata

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
      - cover_path
      - file_paths
      - virtual_libs
      - unique_id
    """

    # 1. Extract from OPF if we have it
    opf_metadata = {}
    if opf_file and os.path.isfile(opf_file):
        opf_metadata = extract_metadata_from_opf(opf_file)

    ebook_metadata = {}
    _, ext = os.path.splitext(ebook_file.lower())
    if ext == ".pdf":
        ebook_metadata = extract_metadata_from_pdf(ebook_file)
    elif ext == ".epub":
        ebook_metadata = extract_metadata_from_epub(ebook_file)

    path_metadata = extract_metadata_from_path(ebook_file)

    metadata = {key: opf_metadata.get(key) or ebook_metadata.get(key) or value for key, value in ebook_metadata.items()}
    metadata = {key: metadata.get(key) or value for key, value in path_metadata.items()}
    return metadata

