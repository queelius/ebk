# Project: ebk

## Documentation Files

### README.md

# ebk

![ebk Logo](https://github.com/queelius/ebk/blob/main/logo.png?raw=true)

**ebk** is a lightweight and versatile tool for managing eBook metadata. It allows users to convert Calibre libraries to JSON, manage and merge multiple libraries, export metadata to Hugo-compatible Markdown files, and interact with your library through a user-friendly Streamlit dashboard.

## Table of Contents

- [ebk](#ebk)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Installation](#installation)
  - [Usage](#usage)
    - [Command-Line Interface (CLI)](#command-line-interface-cli)
      - [Convert Calibre Library](#convert-calibre-library)
      - [Export to Hugo](#export-to-hugo)
      - [Launch Streamlit Dashboard](#launch-streamlit-dashboard)
    - [Streamlit Dashboard](#streamlit-dashboard)
  - [Library Management](#library-management)
  - [Merging Libraries](#merging-libraries)
    - [Usage](#usage-1)
  - [Identifying Library Entries](#identifying-library-entries)
  - [Contributing](#contributing)
  - [License](#license)
  - [🛠️ **Known Issues \& TODOs**](#️-known-issues--todos)
  - [📣 **Stay Updated**](#-stay-updated)
  - [🤝 **Support**](#-support)

## Features

- **Convert Calibre Libraries**: Transform your Calibre library into a structured JSON format.
- **Export to Hugo**: Generate Hugo-compatible Markdown files for seamless integration into static sites.
- **Streamlit Dashboard**: Interactive web interface for browsing, filtering, and managing your eBook library.
- **Library Management**: Add, update, delete, and search for books within your JSON library.
- **Merge Libraries**: Combine multiple eBook libraries with support for set operations like union and intersection.
- **Consistent Entry Identification**: Ensures unique and consistent identification of library entries across different libraries.

## Installation

Ensure you have [Python](https://www.python.org/) installed (version 3.7 or higher recommended).

1. **Clone the Repository**

   ```bash
   git clone https://github.com/queelius/ebk.git
   cd ebk
   ```

2. **Install Dependencies**

   It's recommended to use a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

   Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

3. **Install ebk Package**

   ```bash
   pip install .
   ```

## Usage

ebk provides both a Command-Line Interface (CLI) and a Streamlit-based web dashboard for interacting with your eBook libraries.

### Command-Line Interface (CLI)

After installation, you can access the CLI using the `ebk` command.

#### Convert Calibre Library

Convert your existing Calibre library into a JSON format.

```bash
ebk convert-calibre /path/to/calibre/library /path/to/output/folder
```

- **Arguments**:
  - `/path/to/calibre/library`: Path to your Calibre library directory.
  - `/path/to/output/folder`: Destination folder where the JSON metadata and copied eBooks will be stored.

#### Export to Hugo

Export your JSON library to Hugo-compatible Markdown files, ready for static site integration.

```bash
ebk export /path/to/metadata.json /path/to/hugo/site
```

- **Arguments**:
  - `/path/to/metadata.json`: Path to your JSON metadata file.
  - `/path/to/hugo/site`: Path to your Hugo site directory.

#### Launch Streamlit Dashboard

Start the interactive Streamlit dashboard to browse and manage your eBook library.

```bash
ebk dash --port 8501
```

- **Options**:
  - `--port`: (Optional) Specify the port for the Streamlit app. Defaults to `8501`.

### Streamlit Dashboard

The Streamlit dashboard provides an intuitive web interface for interacting with your eBook library.

1. **Upload a ZIP Archive**

   Prepare a ZIP archive containing:
   
   - `metadata.json` at the root.
   - All cover images referenced in `metadata.json`.
   - All eBook files referenced in `metadata.json`.

   Use the uploader in the dashboard to upload this ZIP archive.

2. **Advanced Filtering**

   Utilize the sidebar to apply advanced filters based on:
   
   - **Title**: Search by book title.
   - **Authors**: Filter by one or multiple authors.
   - **Subjects**: Filter by subjects or genres.
   - **Language**: Filter by language.
   - **Publication Year**: Select a range of publication years.
   - **Identifiers**: Search by unique identifiers like ISBN.

3. **Browse Books**

   - **Books Tab**: View detailed entries of your eBooks, including cover images, metadata, and download/view links.
   - **Statistics Tab**: Visualize your library with charts showing top authors, subjects, and publication trends.

4. **Download eBooks**

   - **View**: For supported formats like PDF and EPUB, view the eBook directly in the browser.
   - **Download**: Download eBooks in their respective formats.

## Library Management

Manage your eBook library using the `LibraryManager` class, which provides functionalities to:

- **List Books**: Retrieve a list of all books in the library.
- **Search Books**: Search for books by title, author, or tags.
- **Add Book**: Add new books to the library.
- **Delete Book**: Remove books from the library by title.
- **Update Book**: Modify metadata of existing books.

## Merging Libraries

Combine multiple eBook libraries into a single consolidated library with support for set operations:

- **Union**: Combine all unique eBooks from multiple libraries.
- **Intersection**: Retain only eBooks present in all selected libraries.
- **Set-Difference**: Remove eBooks present in one library from another.
- **Tagged Unions**: Merge libraries with tagging for better organization.

### Usage

```bash
ebk merge /path/to/library1 /path/to/library2 /path/to/merged_library
```

- **Arguments**:
  - `/path/to/library1`, `/path/to/library2`: Paths to the source library folders.
  - `/path/to/merged_library`: Destination folder for the merged library.

## Identifying Library Entries

To ensure consistent and unique identification of library entries across different libraries, `ebk` employs the following strategies:

1. **Unique Base Naming**: Each eBook is assigned a base name derived from a slugified combination of the title, first author, and a unique identifier (e.g., UUID or ISBN).

2. **Ebook Identification**: eBooks are identified either by their filename or by a hash of their contents, ensuring that duplicate files are correctly handled during operations like merging.

3. **Set-Theoretic Operations**: When performing set operations (union, intersection, etc.), eBooks are matched based on their unique identifiers to maintain consistency and avoid duplication.

## Contributing

Contributions are welcome! Whether it's fixing bugs, improving documentation, or adding new features, your support is greatly appreciated.

1. **Fork the Repository**

2. **Create a New Branch**

   ```bash
   git checkout -b feature/YourFeature
   ```

3. **Make Your Changes**

4. **Commit Your Changes**

   ```bash
   git commit -m "Add YourFeature"
   ```

5. **Push to the Branch**

   ```bash
   git push origin feature/YourFeature
   ```

6. **Open a Pull Request**

## License

Distributed under the MIT License. See [LICENSE](https://github.com/queelius/ebk/blob/main/LICENSE) for more information.

---

## 🛠️ **Known Issues & TODOs**

1. **Exporter Module (`exporter.py`)**
   - **Current Status**: Basic functionality implemented for exporting JSON metadata to Hugo-compatible Markdown files.
   - **To Do**:
     - **Error Handling**: Replace `os.system` calls with Python's `shutil` for copying files to enhance security and reliability.
     - **Metadata Fields**: Ensure all necessary metadata fields are accurately mapped to Hugo's front matter.
     - **Support for Additional Formats**: Extend support for more eBook formats and metadata nuances.

2. **Merger Module (`merge.py`)**
   - **Current Status**: Implements basic merging of multiple libraries by copying files and consolidating metadata.
   - **To Do**:
     - **Set-Theoretic Operations**: Implement union, intersection, set-difference, and tagged unions to provide flexible merging capabilities.
     - **Conflict Resolution**: Develop strategies to handle conflicts when merging metadata from different sources.
     - **Performance Optimization**: Enhance the module to efficiently handle large libraries.

3. **Consistent Entry Identification**
   - **Current Status**: Utilizes a combination of slugified title, author, and unique identifier for base naming.
   - **To Do**:
     - **Hash-Based Identification**: Incorporate hashing of eBook contents to uniquely identify files, ensuring accurate deduplication.
     - **Multiple eBooks per Entry**: Refine the identification system to handle entries with multiple associated eBook files seamlessly.
     - **Metadata Consistency**: Ensure that all metadata across merged libraries maintains consistency in naming and formatting.

---

## 📣 **Stay Updated**

For the latest updates, feature releases, and more, follow the [GitHub Repository](https://github.com/queelius/ebk).

---

## 🤝 **Support**

If you encounter any issues or have suggestions for improvements, please open an issue on the [GitHub Repository](https://github.com/queelius/ebk/issues).

---

Happy eBook managing! 📚✨
---

### Source File: `setup.py`

#### Source Code

```python
from setuptools import setup, find_packages
from pathlib import Path

# Read the README file for the long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name="ebk",
    version="0.1.0",
    description="A lightweight tool for managing eBook metadata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Alex Towell",
    author_email="lex@metafunctor.com",
    url="https://github.com/yourusername/ebk",  # Replace with your repository URL
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "ebk=ebk.cli:main"
        ]
    },
    install_requires=[
        "streamlit",
        "lxml",
        "pandas",
        "slugify",
        "pyyaml",
        "pathlib",
        "PyPDF2",
        "ebooklib",
        "altair",
        "Pillow"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
    include_package_data=True,  # Include non-Python files specified in MANIFEST.in
    package_data={
        "ebk.streamlit": ["*"],  # Include all files in the streamlit subpackage
    },
)

```

---

### Directory: `ebk`

### Source File: `ebk/__init__.py`

#### Source Code

```python
from .extract_metadata import extract_metadata
from .manager import LibraryManager
from .exports.hugo import export_hugo
from .imports.calibre import import_calibre

# Define the public API
__all__ = ["import_calibre", "LibraryManager", "export_hugo", "extract_metadata"]

# Optional package metadata
__version__ = "0.1.0"
__author__ = "Alex Towell"
__email__ = "lex@metafunctor.com"

```

---

### Source File: `ebk/cli.py`

#### Source Code

```python
import argparse
import subprocess
import sys
import json
import shutil
from .exports.hugo import export_hugo
from .exports.zip import export_zipfile
from .imports.calibre import import_calibre
from .imports.ebooks import import_ebooks
from .merge import merge_libraries
from .utils import enumerate_ebooks, load_library
from .ident import add_unique_id
from pathlib import Path
import logging

from .utils import search_entries, get_library_statistics

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="ebk - eBook CLI",
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Import Command
    import_parser = subparsers.add_parser("import", help="Import data from various sources")
    import_subparsers = import_parser.add_subparsers(dest="source", help="Data sources to import from")

    ## Import from Calibre
    calibre_parser = import_subparsers.add_parser("calibre", help="Import a Calibre library")
    calibre_parser.add_argument("calibre_dir", help="Path to the Calibre library directory")
    calibre_parser.add_argument(
        "--output-dir", "-o",
        help="Output directory for the ebk library (default: <calibre_dir>_ebk)"
    )

    ## Import raw eBooks
    ebook_parser = import_subparsers.add_parser("ebooks", help="Recursively import a directory ebooks. The metadata will be inferred from the file.")
    ebook_parser.add_argument("ebooks_dir", help="Path to the directory containing ebook files")
    ebook_parser.add_argument(
        "--output-dir", "-o",
        help="Output directory for the ebk library (default: <ebooks_dir>_ebk)"
    )
    ebook_parser.add_argument("--ebook-formats", "-f", nargs="+", default=["pdf", "epub", "mobi", "azw3", "txt", "markdown", "html", "docx", "rtf", "djvu", "fb2", "cbz", "cbr"],
                              help="List of ebook formats to import (default: pdf, epub, mobi, azw3, txt, markdown, html, docx, rtf, djvu, fb2, cbz, cbr)")

    # Export Command
    export_parser = subparsers.add_parser("export", help="Export ebk library to different formats")
    export_subparsers = export_parser.add_subparsers(dest="format", help="Export formats")

    ## Export to Hugo
    hugo_parser = export_subparsers.add_parser("hugo", help="Export to Hugo")
    hugo_parser.add_argument("lib_dir", help="Path to the ebk library directory to export (contains `metadata.json` and ebook-related files)")    
    hugo_parser.add_argument("hugo_dir", help="Path to the Hugo site directory")

    ## Export to Zip format
    zip_parser = export_subparsers.add_parser("zip", help="Export to Zip format. This will create a Zip file containing the library. All commands work with the Zip file, so they are interchangeable. When using the streamlist dashboard, however, the Zip format is required.")
    zip_parser.add_argument("lib_dir", help="Path to the ebk library directory to export (contains `metadata.json` and ebook-related files)")
    zip_parser.add_argument("zip_file", help="Path to the Zip file to export the library to")

    # Merge Command
    merge_parser = subparsers.add_parser(
        "merge", help="Merge multiple ebk libraries using set-theoretic operations.")
    merge_parser.add_argument(
        "operation", choices=["union", "intersect", "diff", "symdiff"],
                              help="Set-theoretic operation to apply")
    merge_parser.add_argument(
        "output_dir", help="Output directory for the merged ebk library")
    merge_parser.add_argument(
        "libs", nargs='+', help="Paths to the source ebk library directories"),
    
    # Search Command
    search_parser = subparsers.add_parser(
        "search", help="Search entries in an ebk library.")
    search_parser.add_argument(
        "expression",
        type=str,
        help="Regex search expression. Default: '*' (all entries)",
        default="*")
    search_parser.add_argument("lib_dir", help="Path to the ebk library directory to search")

    # Stats Command
    stats_parser = subparsers.add_parser(
        "stats", help="Get statistics about the ebk library.")
    stats_parser.add_argument("lib_dir", help="Path to the ebk library directory to get stats")
    stats_parser.add_argument("--keywords", nargs="+", help="Keywords to search for in titles", default=["python", "data", "machine learning"])

    # List Command
    list_parser = subparsers.add_parser(
        "list", help="List entries in an ebk library.")
    list_parser.add_argument("lib_dir", help="Path to the ebk library directory to list")

    # Add Command
    add_parser = subparsers.add_parser(
        "add", help="Add entries to the ebk library.")
    add_parser.add_argument("lib_dir", help="Path to the ebk library directory to modify")
    add_parser.add_argument("--json", help="JSON file containing entry info to add - may be combined with the other options")
    add_parser.add_argument("--title", help="Title of the entry to add")
    add_parser.add_argument("--creators", nargs="+", help="Creators of the entry to add")
    add_parser.add_argument("--ebooks", nargs="+", help="Paths to the ebook files to add")
    add_parser.add_argument("--cover", help="Path to the cover image to add")

    # Remove Command
    remove_parser = subparsers.add_parser(
        "remove", help="Remove entries from the ebk library.")
    remove_parser.add_argument("lib_dir", help="Path to the ebk library directory to modify")
    remove_parser.add_argument("regex", help="Regex search expression to remove entries")
    #remove_parser.add_argument("--dry-run", action="store_true", help="Perform a dry-run without modifying the library")
    remove_parser.add_argument("--force", action="store_true", help="Force removal without confirmation")
    remove_parser.add_argument("--apply-to", nargs="+",
                               default=["title"],
                               choices=["identifers", "creators", "title"], help="Apply the removal to ebooks, covers, or all files")
    
    # Remove by index Command
    remove_index_parser = subparsers.add_parser(
        "remove-index", help="Remove entries from the ebk library by index.")
    remove_index_parser.add_argument("lib_dir", help="Path to the ebk library directory to modify")
    remove_index_parser.add_argument("indices", nargs="+", help="Indices of entries to remove")
                             
    # Dashboard Command
    dash_parser = subparsers.add_parser("dash", help="Launch the Streamlit dashboard")
    dash_parser.add_argument(
        "--port", default=8501, type=int, help="Port to run the Streamlit app (default: 8501)"
    )
    args = parser.parse_args()

    if args.command == "import":
        if args.source == "calibre":
            import_calibre(args.calibre_dir, args.output_dir)
            logger.debug(f"Calibre library imported to {args.output_dir}")
        elif args.source == "ebooks":
            import_ebooks(args.ebooks_dir, args.output_dir)
            logger.debug(f"Raw ebooks imported to {args.output_dir}")
        else:
            import_parser.print_help()

    elif args.command == "export":
        if args.format == "hugo":
            export_hugo(args.lib_dir, args.hugo_dir)
            logger.debug(f"Library exported to Hugo at {args.hugo_dir}")
        elif args.format == "zip":
            export_zipfile(args.lib_dir, args.zip_file)
            logger.debug(f"Library exported to Zip file {args.zip_file}")
        else:
            export_parser.print_help()

    elif args.command == "search":
        # Search entries in an ebk library
        results = search_entries(args.lib_dir, args.expression)
        print(json.dumps(results, indent=2))

    elif args.command == "merge":
        if len(args.libs) < 2:
            parser.error("Merge operation requires at least two source libraries.")
        merge_libraries(args.libs, args.output_dir, args.operation)
        print(f"Libraries merged with operation '{args.operation}' into {args.output_dir}")        

    elif args.command == "dash":
        streamlit_app(args.port)

    elif args.command == "stats":
        stats = get_library_statistics(args.lib_dir, args.keywords)
        print(json.dumps(stats, indent=2))

    elif args.command == "remove-index":
        metadata_list = load_library(args.lib_dir)
        if not metadata_list:
            print("Failed to load library.")
            sys.exit(1)
        print(f"Loaded {len(metadata_list)} entries from {args.lib_dir}")
        indices = [int(i) for i in args.indices]
        indices.sort(reverse=True)
        for i in indices:
            del metadata_list[i]
        with open(Path(args.lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)

    elif args.command == "remove":
        metadata_list = load_library(args.lib_dir)
        if not metadata_list:
            print("Failed to load library.")
            sys.exit(1)
        print(f"Loaded {len(metadata_list)} entries from {args.lib_dir}")

        import re
        if "title" in args.apply_to:
            rem_list = [entry for entry in metadata_list if re.search(args.regex, entry["title"])]
        if "creators" in args.apply_to:
            rem_list = [entry for entry in metadata_list if any(re.search(args.regex, creator) for creator in entry["creators"])]
        if "identifiers" in args.apply_to:
            rem_list = [entry for entry in metadata_list if any(re.search(args.regex, identifier) for identifier in entry["identifiers"])]
        
        for entry in rem_list:
            # confirm removal
            if not args.force:
                print(f"Remove entry: {entry}")
                confirm = input("Confirm removal? (y/n): ")
                if confirm.lower() != "y":
                    continue

            metadata_list.remove(entry)
            print(f"Removed entry: {entry}")

        with open(Path(args.lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)

    elif args.command == "add":
        metadata_list = load_library(args.lib_dir)
        if not metadata_list:
            print("Failed to load library.")
            sys.exit(1)
        print(f"Loaded {len(metadata_list)} entries from {args.lib_dir}")
        new_entry = {
            "title": args.title,
            "creators": args.creators,
            "file_paths": args.ebooks,
            "cover_path": args.cover,
        }
        add_unique_id(new_entry)

        print(f"Adding new entry: {new_entry}")
        metadata_list.append(new_entry)
        with open(Path(args.lib_dir) / "metadata.json", "w") as f:
            json.dump(metadata_list, f, indent=2)

        # let's use shutil to copy the files
        if args.ebooks:
            for ebook in args.ebooks:
                shutil.copy(ebook, args.lib_dir)
        if args.cover:
            shutil.copy(args.cover, args.lib_dir)




    elif args.command == "list":
        enumerate_ebooks(args.lib_dir)

    else:
        parser.print_help()


def streamlit_app(port: int):
    """
    Launch the Streamlit dashboard.
    """
    try:
        # Determine the path to the Streamlit app
        app_path = Path(__file__).parent / 'streamlit' / 'app.py'
        
        # Check if the app file exists
        if not app_path.exists():
            print(f"Streamlit app not found at {app_path}")
            sys.exit(1)
        
        # Launch the Streamlit app using subprocess
        subprocess.run(
            ['streamlit', 'run', str(app_path), "--server.port", str(port)], check=True)

    except FileNotFoundError:
        print("Error: Streamlit is not installed. Please install it with `pip install streamlit`.")
        sys.exit(1)    
    except subprocess.CalledProcessError as e:
        print(f"Failed to launch Streamlit app: {e}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


```

---

### Source File: `ebk/extract_metadata.py`

#### Source Code

```python
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
        "subjects": None,
        "description": metadata.get("dc:description", metadata.get("description")),
        "language": metadata.get("dc:language", metadata.get("language")),
        "date": metadata.get("dc:date", metadata.get("date")),
        "publisher": metadata.get("dc:publisher", metadata.get("publisher")),
        "identifiers": None
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

    return simplified


def extract_metadata_from_pdf(pdf_path: str) -> Dict:
    """
    Extract metadata from a PDF file using PyPDF2.
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
        pdf_keywords = info.get("/Keywords", None) or info.get("keywords", None)
        pdf_publisher = info.get("/Producer", None) or info.get("producer", None) or info.get("/Publisher", None) or info.get("publisher", None)
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
            metadata["keywords"] = [kw.strip() for kw in pdf_keywords.split(",")]

        if pdf_publisher:
            metadata["publisher"] = pdf_publisher.strip()

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

    _, ext = os.path.splitext(ebook_file.lower())
    if ext == ".pdf":
        ebook_metadata = extract_metadata_from_pdf(ebook_file)
    elif ext == ".epub":
        ebook_metadata = extract_metadata_from_epub(ebook_file)

    path_metadata = extract_metadata_from_path(ebook_file)

    metadata = {key: opf_metadata.get(key) or ebook_metadata.get(key) or value for key, value in ebook_metadata.items()}
    metadata = {key: metadata.get(key) or value for key, value in path_metadata.items()}
    return metadata


```

---

### Source File: `ebk/ident.py`

#### Source Code

```python
import hashlib
import re
from typing import List, Dict
import uuid

def canonicalize_text(text: str) -> str:
    """
    Canonicalize text by converting to lowercase, removing punctuation,
    stripping whitespace, and replacing spaces with underscores.
    """
    text = text.lower()
    # Remove punctuation using regex
    text = re.sub(r'[^\w\s]', '', text)
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading and trailing whitespace
    text = text.strip()
    # Replace spaces with underscores
    text = text.replace(' ', '_')
    return text

def canonicalize_creators(creators: List[str]) -> str:
    """
    Canonicalize a list of creators (authors) by sorting them,
    canonicalizing each name, and joining with underscores.
    """
    # Sort creators alphabetically for consistency
    sorted_creators = sorted(creators)
    canonical_creators = [canonicalize_text(creator) for creator in sorted_creators]
    # Join multiple creators with underscores
    return '_'.join(canonical_creators)

def generate_composite_string(entry: Dict) -> str:
    """
    Generate a composite string by concatenating canonicalized values
    of ISBN, date, language, publisher, creators, and title.
    
    The order is important for consistency.
    """
    identifiers = entry.get('identifiers', {})
    #isbn = identifiers.get('ISBN', '').strip()
    #date = entry.get('date', '').strip()
    language = entry.get('language', '').strip()
    #publisher = entry.get('publisher', '').strip()
    creators = entry.get('creators', [])
    title = entry.get('title', '').strip()
    
    # Canonicalize each field
    #isbn_c = canonicalize_text(isbn) if isbn else 'no_isbn'
    #date_c = canonicalize_text(date) if date else 'no_date'
    language_c = canonicalize_text(language) if language else 'no_language'
    #publisher_c = canonicalize_text(publisher) if publisher else 'no_publisher'
    creators_c = canonicalize_creators(creators) if creators else 'no_creators'
    title_c = canonicalize_text(title) if title else 'no_title'

    if language_c == 'no_language' and creators_c == 'no_creators' and title_c == 'no_title':
        return None
    
    # Concatenate fields with double underscores as delimiters
    composite_string = f"{language_c}__{creators_c}__{title_c}"
    return composite_string

def generate_hash_id(entry: Dict) -> str:
    """
    Generate a unique hash ID for an eBook entry by hashing the composite string.
    
    Args:
        entry (Dict): The eBook entry metadata.
    
    Returns:
        str: The SHA-256 hash hexadecimal string.
    """
    composite_string = generate_composite_string(entry)
    if composite_string:
        composite_bytes = composite_string.encode('utf-8')
    else:
        composite_bytes = str(uuid.uuid4()).encode('utf-8')

    # Create SHA-256 hash
    hash_obj = hashlib.sha256(composite_bytes)
    hash_hex = hash_obj.hexdigest()
    return hash_hex

def add_unique_id(entry: Dict) -> Dict:
    """
    Add a unique hash ID to the eBook entry.
    
    Args:
        entry (Dict): The original eBook entry metadata.
    
    Returns:
        Dict: The eBook entry with an added 'unique_id' field.
    """
    unique_id = generate_hash_id(entry)
    entry['unique_id'] = unique_id
    return entry

```

---

### Source File: `ebk/manager.py`

#### Source Code

```python
import json

class LibraryManager:
    def __init__(self, json_file):
        self.json_file = json_file
        self._load_library()

    def _load_library(self):
        """Load the JSON library into memory."""
        with open(self.json_file, "r") as f:
            self.library = json.load(f)

    def save_library(self):
        """Save the in-memory library back to the JSON file."""
        with open(self.json_file, "w") as f:
            json.dump(self.library, f, indent=4)

    def list_books(self):
        """List all books in the library."""
        return self.library

    def search_books(self, query):
        """Search for books by title, author, or tags."""
        return [
            book for book in self.library
            if query.lower() in (book["Title"].lower() + book["Author"].lower() + book["Tags"].lower())
        ]

    def add_book(self, book_metadata):
        """Add a new book to the library."""
        self.library.append(book_metadata)
        self.save_library()

    def delete_book(self, title):
        """Delete a book by title."""
        self.library = [book for book in self.library if book["Title"] != title]
        self.save_library()

    def update_book(self, title, new_metadata):
        """Update metadata for a specific book."""
        for book in self.library:
            if book["Title"] == title:
                book.update(new_metadata)
        self.save_library()

```

---

### Source File: `ebk/merge.py`

#### Source Code

```python
import os
import json
import shutil
from slugify import slugify
from typing import List, Dict, Tuple
from .ident import generate_hash_id  # Ensure this function is available
import logging

logger = logging.getLogger(__name__)

def load_all_metadata(source_folders: List[str]) -> List[Tuple[Dict, str]]:
    """
    Given a list of source folders, load all 'metadata.json' files and 
    return them as a list of (metadata_entry, source_folder).
    """
    all_entries = []
    for folder in source_folders:
        meta_path = os.path.join(folder, "metadata.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    for entry in data:
                        # Ensure each entry has a unique_id
                        if 'unique_id' not in entry:
                            entry = add_unique_id(entry)  # Assuming this function adds 'unique_id'
                        all_entries.append((entry, folder))
                except json.JSONDecodeError as e:
                    logger.error(f"Error decoding JSON from {meta_path}: {e}")
        else:
            logger.warning(f"No metadata.json found in {folder}")
    return all_entries

def add_unique_id(entry: Dict) -> Dict:
    """
    Ensure that each entry has a unique_id. If not, generate one.
    """
    if 'unique_id' not in entry or not entry['unique_id']:
        entry = add_unique_id(entry)  # Recursive call; ensure no infinite loop
    return entry

def perform_set_operation(
    entries: List[Dict], 
    operation: str, 
    source_counts: Dict[str, int]
) -> List[Dict]:
    """
    Perform the specified set operation on the list of entries.
    
    Args:
        entries (List[Dict]): List of eBook entries with 'unique_id'.
        operation (str): One of 'union', 'intersect', 'diff', 'symdiff'.
        source_counts (Dict[str, int]): Counts of how many sources each unique_id appears in.
    
    Returns:
        List[Dict]: Filtered list of entries based on the set operation.
    """
    if operation == "union":
        # All unique entries
        return entries
    elif operation == "intersect":
        # Entries present in all source libraries
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == len(source_counts)]
    elif operation == "diff":
        # Set difference: entries present in the first library but not in others
        # Assuming 'diff' is lib1 - lib2
        # Modify the function signature to pass specific libraries if needed
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == 1]
    elif operation == "symdiff":
        # Symmetric difference: entries present in one library but not in both
        return [entry for entry in entries if source_counts.get(entry['unique_id'], 0) == 1]
    else:
        logger.error(f"Unsupported set operation: {operation}")
        return []

def merge_libraries(
    source_folders: List[str], 
    merged_folder: str, 
    operation: str
):
    """
    Merges multiple ebook libraries (each in a separate folder) into a single library
    based on the specified set-theoretic operation.
    
    Args:
        source_folders (List[str]): List of source library folders to merge.
        merged_folder (str): Path to the folder where the merged library will be saved.
        operation (str): Set operation to apply ('union', 'intersect', 'diff', 'symdiff').
    """
    if not os.path.exists(merged_folder):
        os.makedirs(merged_folder)
        logger.info(f"Created merged folder at {merged_folder}")
    
    # Load all entries
    entries_with_sources = load_all_metadata(source_folders)
    
    # Index entries by unique_id
    unique_entries = {}
    source_counts = {}
    
    for entry, source in entries_with_sources:
        uid = entry['unique_id']
        if uid not in unique_entries:
            unique_entries[uid] = entry
            source_counts[uid] = 1
        else:
            source_counts[uid] += 1
            # Optionally, handle metadata conflicts here
            # For example, you could merge metadata fields or prioritize certain sources
            # Here, we'll assume the first occurrence is kept
            logger.debug(f"Duplicate entry found for unique_id {uid} in {source}. Ignoring.")
    
    all_unique_entries = list(unique_entries.values())
    
    # Perform the set operation
    filtered_entries = perform_set_operation(all_unique_entries, operation, source_counts)
    
    logger.info(f"Performing '{operation}' operation. {len(filtered_entries)} entries selected.")
    
    # Copy files and prepare merged metadata
    merged_metadata = []
    
    for entry in filtered_entries:
        # Copy eBook files
        new_entry = copy_entry_files(entry, source_folders, merged_folder)
        merged_metadata.append(new_entry)
    
    # Write merged metadata.json
    merged_meta_path = os.path.join(merged_folder, "metadata.json")
    with open(merged_meta_path, "w", encoding="utf-8") as f:
        json.dump(merged_metadata, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Merged {len(merged_metadata)} entries into {merged_folder}")

def copy_entry_files(
    entry: Dict, 
    source_folders: List[str], 
    dst_folder: str
) -> Dict:
    """
    Copies all relevant files for an entry from its source folder to the destination folder.
    
    Args:
        entry (Dict): The eBook entry metadata.
        source_folders (List[str]): List of source folders to search for the entry's files.
        dst_folder (str): Destination folder to copy files to.
    
    Returns:
        Dict: The updated entry with new file paths.
    """
    base_name = f"{slugify(entry.get('title', 'unknown_title'))}__{slugify(entry['creators'][0] if entry.get('creators') else 'unknown_creator')}__{entry.get('unique_id')}"
    
    new_entry = entry.copy()
    
    # Find the source folder containing this entry
    source_folder = find_source_folder(entry, source_folders)
    if not source_folder:
        logger.warning(f"Source folder not found for entry with unique_id {entry['unique_id']}")
        return new_entry
    
    # Copy eBook files
    new_file_paths = []
    for file_rel_path in entry.get('file_paths', []):
        src_path = os.path.join(source_folder, file_rel_path)
        if not os.path.exists(src_path):
            logger.warning(f"Ebook file '{src_path}' does not exist.")
            continue
        _, ext = os.path.splitext(file_rel_path)
        dst_filename = f"{base_name}{ext}"
        dst_path = os.path.join(dst_folder, dst_filename)
        dst_path = get_unique_filename(dst_path)
        try:
            shutil.copy(src_path, dst_path)
        except OSError as e:
            logger.error(f"Error copying file '{src_path}' to '{dst_path}': {e}")
            continue
        new_file_paths.append(os.path.basename(dst_path))
        logger.debug(f"Copied ebook file '{src_path}' to '{dst_path}'")
    
    new_entry['file_paths'] = new_file_paths
    
    # Copy cover image if exists
    cover_path = entry.get('cover_path')
    if cover_path:
        src_cover = os.path.join(source_folder, cover_path)
        if os.path.exists(src_cover):
            _, ext = os.path.splitext(cover_path)
            dst_cover_filename = f"{base_name}_cover{ext}"
            dst_cover_path = os.path.join(dst_folder, dst_cover_filename)
            dst_cover_path = get_unique_filename(dst_cover_path)
            try:
                shutil.copy(src_cover, dst_cover_path)
            except OSError as e:
                logger.error(f"Error copying cover image '{src_cover}' to '{dst_cover_path}': {e}")
                new_entry['cover_path'] = None
                return new_entry
            new_entry['cover_path'] = os.path.basename(dst_cover_path)
            logger.debug(f"Copied cover image '{src_cover}' to '{dst_cover_path}'")
        else:
            logger.warning(f"Cover image '{src_cover}' does not exist.")
            new_entry['cover_path'] = None
    else:
        new_entry['cover_path'] = None
    
    return new_entry

def find_source_folder(entry: Dict, source_folders: List[str]) -> str:
    """
    Identifies the source folder where the entry's files are located.
    
    Args:
        entry (Dict): The eBook entry metadata.
        source_folders (List[str]): List of source library folders.
    
    Returns:
        str: The path to the source folder, or None if not found.
    """
    for folder in source_folders:
        meta_path = os.path.join(folder, "metadata.json")
        if not os.path.exists(meta_path):
            continue
        with open(meta_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                for src_entry in data:
                    if src_entry.get('unique_id') == entry.get('unique_id'):
                        return folder
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from {meta_path}: {e}")
    return None

def get_unique_filename(target_path: str) -> str:
    """
    If target_path already exists, generate a new path with (1), (2), etc.
    Otherwise just return target_path.
    
    Example:
       'myfile.pdf' -> if it exists -> 'myfile (1).pdf' -> if that exists -> 'myfile (2).pdf'
    """
    if not os.path.exists(target_path):
        return target_path

    base, ext = os.path.splitext(target_path)
    counter = 1
    new_path = f"{base} ({counter}){ext}"
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{base} ({counter}){ext}"

    return new_path

```

---

### Source File: `ebk/utils.py`

#### Source Code

```python
import json
import os
from collections import Counter
from pathlib import Path
from typing import List, Dict
import logging
from jmespath import search
import sys
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
RICH_AVAILABLE = True

logger = logging.getLogger(__name__)

def search_entries(lib_dir: str, expression: str):
    """
    Search entries in an ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory
        expression (str): Search expression (regex)

    Returns:
        List[Dict]: List of matching entries
    """
    library = load_library(lib_dir)
    if not library:
        logger.error(f"Failed to load the library at {lib_dir}")
        return []
    
    result = search(expression, library)
    return result


def load_library(lib_dir: str) -> List[Dict]:
    """
    Load an ebk library from the specified directory.

    Args:
        lib_dir (str): Path to the ebk library directory

    Returns:
        List[Dict]: List of entries in the library
    """
    lib_dir = Path(lib_dir)
    metadata_path = lib_dir / "metadata.json"
    if not metadata_path.exists():
        logger.error(f"Metadata file not found at {metadata_path}")
        return []

    with open(metadata_path, "r") as f:
        try:
            library = json.load(f)
            return library
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {metadata_path}: {e}")
            return []

def get_library_statistics(lib_dir: str,
                           keywords: List[str] = None) -> Dict:
    """
    Compute statistics for an ebk library.

    Args:
        lib_dir (str): Path to the ebk library directory.
        keywords (List[str]): Keywords to search for in titles (default: None).

    Returns:
        dict: A dictionary or markdown with statistics about the library.
    """

    # Load the library
    library = load_library(lib_dir)
    if not library:
        logger.error(f"Failed to load the library at {lib_dir}")
        return {}

    # Initialize counters and statistics
    stats = {
        "total_entries": 0,
        "languages": Counter(),
        "creators_count": 0,
        "average_creators_per_entry": 0,
        "most_creators_in_entry": 0,
        "least_creators_in_entry": 0,
        "top_creators": Counter(),
        "subjects": Counter(),
        "most_common_subjects": [],
        "average_title_length": 0,
        "longest_title": "",
        "shortest_title": "",
        "virtual_libs": Counter(),
        "titles_with_keywords": Counter(),
    }

    title_lengths = []

    for entry in library:
        # Total entries
        stats["total_entries"] += 1

        # Languages
        language = entry.get("language", "unknown")
        stats["languages"][language] += 1

        # Creators
        creators = entry.get("creators", [])
        stats["creators_count"] += len(creators)
        stats["top_creators"].update(creators)
        stats["most_creators_in_entry"] = max(stats["most_creators_in_entry"], len(creators))
        if stats["least_creators_in_entry"] == 0 or len(creators) < stats["least_creators_in_entry"]:
            stats["least_creators_in_entry"] = len(creators)

        # Subjects
        subjects = entry.get("subjects", [])
        stats["subjects"].update(subjects)

        # Titles
        title = entry.get("title", "")
        if title:
            title_lengths.append(len(title))
            if len(title) > len(stats["longest_title"]):
                stats["longest_title"] = title
            if not stats["shortest_title"] or len(title) < len(stats["shortest_title"]):
                stats["shortest_title"] = title

        # Keywords
        for keyword in keywords:
            if keyword.lower() in title.lower():
                stats["titles_with_keywords"][keyword] += 1

        # Virtual Libraries
        virtual_libs = entry.get("virtual_libs", [])
        stats["virtual_libs"].update(virtual_libs)

    # Post-process statistics
    stats["average_creators_per_entry"] = round(stats["creators_count"] / stats["total_entries"], 2)
    stats["average_title_length"] = round(sum(title_lengths) / len(title_lengths), 2) if title_lengths else 0
    stats["most_common_subjects"] = stats["subjects"].most_common(5)
    stats["languages"] = dict(stats["languages"])
    stats["top_creators"] = dict(stats["top_creators"].most_common(5))
    stats["titles_with_keywords"] = dict(stats["titles_with_keywords"])
    stats["virtual_libs"] = dict(stats["virtual_libs"])

    return stats

def get_unique_filename(target_path: str) -> str:
    """
    If target_path already exists, generate a new path with (1), (2), etc.
    Otherwise just return target_path.
    
    Example:
       'myfile.pdf' -> if it exists -> 'myfile (1).pdf' -> if that exists -> 'myfile (2).pdf'
    """
    if not os.path.exists(target_path):
        return target_path

    base, ext = os.path.splitext(target_path)
    counter = 1
    new_path = f"{base} ({counter}){ext}"
    while os.path.exists(new_path):
        counter += 1
        new_path = f"{base} ({counter}){ext}"

    return new_path

def enumerate_ebooks(lib_dir: str) -> None:
    """
    Enumerates and displays the ebooks in the specified library directory.

    For each ebook, displays its index, title, creators, and a clickable link to the first PDF file.

    Args:
        lib_dir (str): The path to the library directory containing ebook metadata.
    """
    console = Console()
    lib_path = Path(lib_dir)

    if not lib_path.exists():
        console.print(f"[bold red]Error:[/bold red] The library directory '{lib_dir}' does not exist.")
        sys.exit(1)

    if not lib_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] The path '{lib_dir}' is not a directory.")
        sys.exit(1)

    try:
        metadata_list = load_library(lib_path)
    except Exception as e:
        console.print(f"[bold red]Error loading library metadata:[/bold red] {e}")
        sys.exit(1)

    total_books = len(metadata_list)
    if total_books == 0:
        console.print("[yellow]No ebooks found in the library.[/yellow]")
        return

    console.print(f"📚 [bold]Found {total_books} ebook(s) in the library:[/bold]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", min_width=20)
    table.add_column("Creators", min_width=20)
    table.add_column("Link", min_width=30)

    for i, book in enumerate(metadata_list, start=1):
        title = book.get('title', 'Unknown Title')
        creators = book.get('creators', ['Unknown'])
        if not isinstance(creators, list):
            creators = [str(creators)]
        creators_str = ', '.join(creators)

        ebook_paths = book.get('file_paths', [])
        ebook_path = ebook_paths[0] if ebook_paths else None

        if ebook_path:
            ebook_full_path = lib_path / ebook_path
            if ebook_full_path.exists():
                # Resolve the path to an absolute path
                resolved_path = ebook_full_path.resolve()
                # Convert Windows paths to URL format if necessary
                if sys.platform.startswith('win'):
                    ebook_link = resolved_path.as_uri()
                else:
                    ebook_link = f"file://{resolved_path}"
                link_display = f"[link={ebook_link}]🔗 Open[/link]"
            else:
                ebook_link = "File not found"
                link_display = "[red]🔗 Not Found[/red]"
        else:
            ebook_link = "Unknown"
            link_display = "[red]🔗 Unknown[/red]"

        table.add_row(str(i), title, creators_str, link_display)

    console.print(table)
    console.print("\n")  # Add some spacing

```

---

#### Directory: `ebk/imports`

### Source File: `ebk/imports/__init__.py`

#### Source Code

```python

```

---

### Source File: `ebk/imports/calibre.py`

#### Source Code

```python
import os
import shutil
import json
from slugify import slugify
from typing import Dict
import logging
from ..extract_metadata import extract_metadata
from ..ident import add_unique_id
from ..utils import get_unique_filename

logger = logging.getLogger(__name__)

ebook_exts = (".pdf", ".epub", ".mobi", ".azw3", ".txt", ".docx", ".odt",
              ".html", ".rtf", ".md", ".fb2", ".cbz", ".cbr", ".djvu",
              ".xps", ".ibooks", ".azw", ".lit", ".pdb", ".prc", ".lrf",
              ".pdb", ".pml", ".rb", ".snb", ".tcr", ".txtz", ".azw1")                

def import_calibre(calibre_dir: str,
                   output_dir: str,
                   ebook_exts: tuple = ebook_exts):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    metadata_list = []

    for root, _, files in os.walk(calibre_dir):
        # Look for OPF
        opf_file_path = os.path.join(root, "metadata.opf")
        
        # Gather valid ebook files
        ebook_files = [f for f in files if f.lower().endswith(ebook_exts)]
        
        if not ebook_files:
            logger.debug(f"No recognized ebook files found in {root}. Skipping.")
            continue  # skip if no recognized ebook files

        # Pick the "primary" ebook file. This is arbitrary and can be changed.
        primary_ebook_file = ebook_files[0]
        ebook_full_path = os.path.join(root, primary_ebook_file)

        # Extract metadata
        if os.path.exists(opf_file_path):
            logger.debug(f"Found metadata.opf in {root}. Extracting metadata from OPF.")
            metadata = extract_metadata(ebook_full_path, opf_file_path)
        else:
            logger.warning(f"No metadata.opf found in {root}. Inferring metadata from ebook files.")
            metadata = extract_metadata(ebook_full_path)  # Only ebook file path is provided

        # Extract metadata (OPF + ebook)
        metadata = extract_metadata(ebook_full_path, opf_file_path)
        metadata["root"] = root
        metadata["source_folder"] = calibre_dir
        metadata["output_folder"] = output_dir
        metadata["imported_from"] = "calibre"
        metadata["virtual_libs"] = [slugify(output_dir)]

        # Generate base name
        title_slug = slugify(metadata.get("title", "unknown_title"))
        creator_slug = slugify(
            metadata["creators"][0]) if metadata.get("creators") else "unknown_creator"

        base_name = f"{title_slug}__{creator_slug}"

        # Copy ebooks
        file_paths = []
        for ebook_file in ebook_files:
            _, ext = os.path.splitext(ebook_file)
            src = os.path.join(root, ebook_file)
            dst = os.path.join(output_dir, f"{base_name}{ext}")
            dst = get_unique_filename(dst)
            shutil.copy(src, dst)
            file_paths.append(os.path.relpath(dst, output_dir))

        # Optionally handle cover.jpg
        if "cover.jpg" in files:
            cover_src = os.path.join(root, "cover.jpg")
            cover_dst = os.path.join(output_dir, f"{base_name}_cover.jpg")
            shutil.copy(cover_src, cover_dst)
            metadata["cover_path"] = os.path.relpath(cover_dst, output_dir)

        # Store relative paths in metadata
        metadata["file_paths"] = file_paths
        metadata_list.append(metadata)

    for entry in metadata_list:
        add_unique_id(entry)

    # Write out metadata.json
    output_json = os.path.join(output_dir, "metadata.json")
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, indent=2, ensure_ascii=False)


def ensure_metadata_completeness(metadata: Dict) -> Dict:
    """
    Ensure that all required metadata fields are present.
    If a field is missing or empty, attempt to infer or set default values.
    
    Args:
        metadata (Dict): The metadata dictionary extracted from OPF or inferred.
    
    Returns:
        Dict: The updated metadata dictionary with all necessary fields.
    """
    required_fields = ["title", "creators",
                       "subjects", "description",
                       "language", "date", "identifiers",
                       "file_paths", "cover_path", "unique_id",
                       "source_folder", "output_folder",
                       "imported_from", "virtual_libs"]
    for field in required_fields:
        if field not in metadata:
            if field == "creators":
                metadata[field] = ["Unknown Author"]
                logger.debug(f"Set default value for '{field}'.")
            elif field == "subjects":
                metadata[field] = []
                logger.debug(f"Set default value for '{field}'.")
            elif field == "description":
                metadata[field] = "No description available."
                logger.debug(f"Set default value for '{field}'.")
            elif field == "language":
                metadata[field] = "en"  # Default to English
                logger.debug(f"Set default value for '{field}'.")
            elif field == "date":
                metadata[field] = None  # Unknown date
                logger.debug(f"Set default value for '{field}'.")
            elif field == "title":
                metadata[field] = "Unknown Title"
                logger.debug(f"Set default value for '{field}'.")
            elif field == "identifiers":
                metadata[field] = {}
                logger.debug(f"Set default value for '{field}'.")
            elif field == "file_paths":
                metadata[field] = []
                logger.debug(f"Set default value for '{field}'.")
            elif field == "cover_path":
                metadata[field] = None
                logger.debug(f"Set default value for '{field}'.")
            elif field == "unique_id":
                metadata[field] = None
                logger.debug(f"Set default value for '{field}'.")
    
    return metadata
```

---

### Source File: `ebk/imports/ebooks.py`

#### Source Code

```python
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

```

---

#### Directory: `ebk/exports`

### Source File: `ebk/exports/__init__.py`

#### Source Code

```python

```

---

### Source File: `ebk/exports/hugo.py`

#### Source Code

```python
import os
import json
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)

def export_hugo(lib_dir, hugo_dir):
    """
    Export ebk library to Hugo-compatible Markdown files.

    Args:
        lib_dir (str): Path to the ebk library directory to export (contains `metadata.json` and ebook-related files)
        hugo_dir (str): Path to the Hugo site directory
    """

    lib_dir = Path(lib_dir)
    with open(lib_dir / "metadata.json", "r") as f:
        books = json.load(f)

    hugo_dir = Path(hugo_dir)

    content_dir = hugo_dir / "content" / "library"
    static_dir = hugo_dir / "static" / "ebooks"
    content_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    for book in books:
        slug = book['title'].replace(" ", "-").lower()
        md_file = content_dir / f"{slug}.md"

        with open(md_file, "w") as md:
            md.write("---\n")
            md.write(f"title: {book['title']}\n")
            md.write(f"creators: [{', '.join(book['creators'])}]\n")
            md.write(f"subjects: [{', '.join(book['subjects'])}]\n")
            md.write(f"description: {book['description']}\n")
            md.write(f"date: {book['date']}\n")
            md.write(f"tags: [{', '.join(book['Tags'].split(', '))}]\n")
            md.write(f"ebook_file: /ebooks/{Path(book['file_path']).name}\n")
            md.write(f"cover_image: /ebooks/{Path(book['Cover Path']).name if book['Cover Path'] else ''}\n")
            md.write("---\n\n")
            md.write(f"# {book['Title']}\n\n")
            md.write(f"Author: {book['Author']}\n\n")
            md.write(f"[Download eBook](/ebooks/{Path(book['File Path']).name})\n")

        # Copy eBook and cover to static directory
        if book["File Path"]:
            os.system(f"cp '{book['File Path']}' '{static_dir}'")
        if book["Cover Path"]:
            os.system(f"cp '{book['Cover Path']}' '{static_dir}'")

    logger.debug(f"Exported {len(books)} books to Hugo site at '{hugo_dir}'")


```

---

### Source File: `ebk/exports/zip.py`

#### Source Code

```python

import json
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
                z.write(file_path, arcname=file_path.relative_to(lib_dir))

    logger.debug(f"Exported ebk library at '{lib_dir}' to '{zip_file}'")

```

---

#### Directory: `ebk/streamlit`

### Source File: `ebk/streamlit/__init__.py`

#### Source Code

```python

```

---

### Source File: `ebk/streamlit/app.py`

#### Source Code

```python
import streamlit as st
import pandas as pd
import os
import logging
from utils import load_metadata, extract_zip
from filters import sanitize_dataframe, create_filters
from display import display_books_tab, display_statistics_tab

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#def display_footer():
#    st.markdown("---")
#    st.write("Developed with ❤️ using Streamlit.")

def display_dashboard(metadata_list: list, cover_images: dict, ebook_files: dict):
    """
    Displays the main dashboard with advanced filtering and a compact UI layout using tabs.
    """
    # Convert metadata list to DataFrame
    df = pd.DataFrame(metadata_list)
    logger.debug("Converted metadata list to DataFrame.")

    # Sanitize DataFrame
    df = sanitize_dataframe(df)
    logger.debug("Sanitized DataFrame.")

    # Apply Filters
    filtered_df = create_filters(df)
    logger.debug("Applied filters to DataFrame.")

    # Create Tabs
    tabs = st.tabs(["📚 Books", "📊 Statistics", "Advanced Search", "📖 Table", "📝 Instructions"])
    

    with tabs[0]:
        # Display Books
        display_books_tab(filtered_df, cover_images, ebook_files)

    with tabs[1]:
        # Display Statistics
        display_statistics_tab(filtered_df)

    with tabs[2]:
        # Display Advanced Search
        display_advanced_search_tab(metadata_list)

    with tabs[3]:
        # Display Table
        display_table_view_tab(filtered_df)

    with tabs[4]:
        # Display Instructions
        st.header("📝 Instructions")
        st.markdown("""
        1. **Prepare a ZIP Archive** of an ebk library using the following process:
        - Go to the directory containing the desired ebk library (should have 'metadata.json` and associated files).
        - Compress the directory into a ZIP archive.
                - The `ebk` CLI tool can also autoatically output a ZIP archive,
                e.g., `ebk import calibre <calibre-library> --output.zip`.
        2. **Upload the ZIP Archive** using the uploader below.
        3. **Use the Sidebar** to apply filters and search your library.
        4. **Interact** with the dashboard to view details and download ebooks.
        """)

    # Display Footer
    # display_footer()

def main():
    st.set_page_config(page_title="ebk Dashboard", layout="wide")
    st.title("📚 ebk Dashoard")
    st.write("""
    Upload a **ZIP archive** containing your `metadata.json`, all associated cover images, and ebook files.
    The app will automatically process and display your library with advanced search and filtering options.
    """)

    # File uploader for ZIP archive
    st.subheader("📁 Upload ZIP Archive")
    zip_file = st.file_uploader(
        label="Upload a ZIP file containing `metadata.json`, cover images, and ebook files",
        type=["zip"],
        key="zip_upload"
    )

    MAX_ZIP_SIZE = 8 * 1024 * 1024 * 1024  # 1 GB

    if zip_file:
        print("Uploaded ZIP file:", zip_file.name)
        print("🔄 File size:", zip_file.size)
        if zip_file.size > MAX_ZIP_SIZE:
            st.error(f"❌ Uploaded ZIP file is {zip_file.size / 1024 / 1024 / 1024:.2f} GB, which exceeds the size limit of 1 GB.")
            logger.error("Uploaded ZIP file exceeds the size limit.")
            st.stop()

        with st.spinner("🔄 Extracting and processing ZIP archive..."):
            extracted_files = extract_zip(zip_file)
        if not extracted_files:
            logger.error("No files extracted from the ZIP archive.")
            st.stop()  # Stop if extraction failed

        # Locate metadata.json (case-insensitive search)
        metadata_key = next((k for k in extracted_files if os.path.basename(k).lower() == "metadata.json"), None)
        if not metadata_key:
            st.error("❌ `metadata.json` not found in the uploaded ZIP archive.")
            logger.error("`metadata.json` not found in the uploaded ZIP archive.")
            st.stop()

        metadata_content = extracted_files[metadata_key]
        metadata_list = load_metadata(metadata_content)
        if not metadata_list:
            logger.error("Failed to load metadata from `metadata.json`.")
            st.stop()

        # Collect cover images and ebook files
        cover_images = {}
        ebook_files = {}
        for filename, file_bytes in extracted_files.items():
            lower_filename = filename.lower()
            basename = os.path.basename(filename)
            if lower_filename.endswith(('.jpg', '.jpeg', '.png')):
                cover_images[basename] = file_bytes
                logger.debug(f"Added cover image: {basename}")
            elif lower_filename.endswith(('.pdf', '.epub', '.mobi', '.azw3', '.txt')):
                ebook_files[basename] = file_bytes
                logger.debug(f"Added ebook file: {basename}")
            else:
                # Ignore other file types or handle as needed
                logger.debug(f"Ignored unsupported file type: {basename}")
                pass

        # Inform user about unmatched cover images
        expected_covers = {os.path.basename(md.get("cover_path", "")) for md in metadata_list if md.get("cover_path")}
        uploaded_covers = set(cover_images.keys())
        missing_covers = expected_covers - uploaded_covers
        if missing_covers:
            st.warning(f"⚠️ The following cover images are referenced in `metadata.json` but were not uploaded: {', '.join(missing_covers)}")
            logger.warning(f"Missing cover images: {missing_covers}")

        # Inform user about unmatched ebook files
        expected_ebooks = {os.path.basename(path) for md in metadata_list for path in md.get("file_paths", [])}
        uploaded_ebooks = set(ebook_files.keys())
        missing_ebooks = expected_ebooks - uploaded_ebooks
        if missing_ebooks:
            st.warning(f"⚠️ The following ebook files are referenced in `metadata.json` but were not uploaded: {', '.join(missing_ebooks)}")
            logger.warning(f"Missing ebook files: {missing_ebooks}")

        # Display the dashboard with metadata and cover images
        display_dashboard(metadata_list, cover_images, ebook_files)
    else:
        st.info("📥 Please upload a ZIP archive to get started.")
        logger.debug("No ZIP archive uploaded yet.")

def display_table_view_tab(filtered_df: pd.DataFrame):
    """
    Displays the Table tab with a searchable table of metadata.
    """
    st.header("📖 Table")
    st.write("Explore the metadata of your library using the interactive table below.")
    st.dataframe(filtered_df)




def display_advanced_search_tab(metadata_list: list):
    """
    Using JMESPath to search the metadata list.
    """
    import jmespath

    st.header("Advanced Search")
    st.write("Use JMESPath queries to search the metadata list.")
    query = st.text_input("Enter a JMESPath query", "[].[?date > `2020-01-01`]")
    try:
        result = jmespath.search(query, metadata_list)
        st.write("Search Results:")
        st.write(result)
    except Exception as e:
        st.error(f"An error occurred: {e}")
        logger.error(f"JMESPath search error: {e}")



if __name__ == "__main__":
    main()

```

---

### Source File: `ebk/streamlit/display.py`

#### Source Code

```python
import streamlit as st
from PIL import Image
import pandas as pd
import altair as alt
import logging
import os

logger = logging.getLogger(__name__)

def display_books_tab(filtered_df: pd.DataFrame, cover_images: dict, ebook_files: dict):
    """
    Displays the Books tab with book entries and download/view links.
    """
    total_size = len(filtered_df)
    st.subheader(f"📚 Book Entries (Total: {total_size})")
    if not filtered_df.empty:
        for idx, row in filtered_df.iterrows():
            with st.expander(f"**{row.get('title', 'No Title')}**"):
                # Layout: Cover Image & Downloads | Metadata
                cols = st.columns([1.5, 3])

                # Left Column: Cover Image
                with cols[0]:
                    # Cover Image
                    cover_path = row.get("cover_path", "")
                    cover_filename = os.path.basename(cover_path)
                    cover_data = cover_images.get(cover_filename)
                    if cover_data:
                        try:
                            image = Image.open(cover_data)
                            st.image(image, use_container_width=True, caption="🖼️ Cover")
                            logger.debug(f"Displayed cover image: {cover_filename}")
                        except Exception as e:
                            st.error(f"🖼️ Error loading image: {e}")
                            logger.error(f"Error loading image {cover_filename}: {e}")
                    else:
                        st.info("🖼️ No cover image available.")
                        logger.debug(f"No cover image available for {cover_filename}.")

                # Right Column: Metadata Details and Ebook Links
                with cols[1]:


                    # show title in a header style
                    title = row.get("title", "No Title")
                    st.markdown(f"# 📖 {title}")

                    metadata_details = {
                        "👤 **Author(s)**": ", ".join(row.get("creators", ["N/A"])),
                        "📚 **Subjects**": ", ".join(row.get("subjects", ["N/A"])),
                        "📝 **Description**": row.get("description", "N/A"),
                        "🌐 **Language**": row.get("language", "N/A"),
                        "📅 **Publication Date**": row.get("date", "N/A") if pd.notna(row.get("date", None)) else "N/A",
                        "📖 **Publisher**": row.get("publisher", "N/A"),
                        "📏 **File Size**": row.get("file_size", "N/A"),
                        "📚 **Virtual Libraries**": ", ".join(row.get("virtual_libs", ["N/A"])),
                        "🔑 **Identifiers**": ", ".join([f"{k}: {v}" for k, v in row.get("identifiers", {}).items()]),
                        "🔑 **Unique ID**": row.get("unique_id", "NA"),
                    }

                    for key, value in metadata_details.items():
                        st.markdown(f"{key}: {value}")

                    # Ebook Download and View Links
                    ebook_paths = row.get("file_paths", [])
                    if ebook_paths:
                        st.markdown("### 📥 Ebook Links")
                        for ebook_path in ebook_paths:
                            ebook_filename = os.path.basename(ebook_path)
                            ebook_data = ebook_files.get(ebook_filename)
                            if ebook_data:
                                # Determine MIME type based on file extension
                                _, ext = os.path.splitext(ebook_filename.lower())
                                mime_types = {
                                    '.pdf': 'application/pdf',
                                    '.epub': 'application/epub+zip',
                                    '.mobi': 'application/x-mobipocket-ebook',
                                    '.azw3': 'application/vnd.amazon.ebook',
                                    '.txt': 'text/plain'
                                }
                                mime_type = mime_types.get(ext, 'application/octet-stream')

                                st.download_button(
                                    label=f"💾 Download {ebook_filename}",
                                    data=ebook_data.getvalue(),
                                    file_name=ebook_filename,
                                    mime=mime_type
                                )
                                logger.debug(f"Provided link for {ebook_filename}.")
                            else:
                                st.warning(f"Ebook file '{ebook_filename}' not found in the uploaded ZIP.")
                                logger.warning(f"Ebook file '{ebook_filename}' not found in the uploaded ZIP.")
                    else:
                        st.info("📄 No ebook files available for download.")
                        logger.debug("No ebook files available for download.")
    else:
        st.info("📚 No books match the current filter criteria.")
        logger.debug("No books match the current filter criteria.")

def display_statistics_tab(filtered_df: pd.DataFrame):
    """
    Displays the Statistics tab with various visualizations.
    """
    st.subheader("📊 Statistics")

    if not filtered_df.empty:
        # Visualization: Books per Author (Top 10)
        st.markdown("### 📈 Top 10 Authors by Number of Books")
        author_counts = pd.Series([creator for creators in filtered_df['creators'] for creator in creators]).value_counts().nlargest(10).reset_index()
        author_counts.columns = ['Author', 'Number of Books']
        
        chart = alt.Chart(author_counts).mark_bar().encode(
            x=alt.X('Number of Books:Q', title='Number of Books'),
            y=alt.Y('Author:N', sort='-x', title='Author'),
            tooltip=['Author', 'Number of Books']
        ).properties(
            width=600,
            height=400
        )
        
        st.altair_chart(chart, use_container_width=True)
        logger.debug("Displayed Top 10 Authors chart.")

        # Visualization: Books per Subject (Top 10)
        st.markdown("### 📊 Top 10 Subjects by Number of Books")
        subject_counts = pd.Series([subject for subjects in filtered_df['subjects'] for subject in subjects]).value_counts().nlargest(10).reset_index()
        subject_counts.columns = ['Subject', 'Number of Books']
        
        subject_chart = alt.Chart(subject_counts).mark_bar().encode(
            x=alt.X('Number of Books:Q', title='Number of Books'),
            y=alt.Y('Subject:N', sort='-x', title='Subject'),
            tooltip=['Subject', 'Number of Books']
        ).properties(
            width=600,
            height=400
        )
        
        st.altair_chart(subject_chart, use_container_width=True)
        logger.debug("Displayed Top 10 Subjects chart.")

        # Visualization: Books Published Over Time
        st.markdown("### 📈 Books Published Over Time")
        if 'date' in filtered_df.columns and pd.api.types.is_numeric_dtype(filtered_df['date']):
            publication_years = filtered_df['date'].dropna().astype(int)
            if not publication_years.empty:
                year_counts = publication_years.value_counts().sort_index().reset_index()
                year_counts.columns = ['Year', 'Number of Books']
                
                time_chart = alt.Chart(year_counts).mark_line(point=True).encode(
                    x=alt.X('Year:O', title='Year'),
                    y=alt.Y('Number of Books:Q', title='Number of Books'),
                    tooltip=['Year', 'Number of Books']
                ).properties(
                    width=800,
                    height=400
                )
                
                st.altair_chart(time_chart, use_container_width=True)
                logger.debug("Displayed Books Published Over Time chart.")
            else:
                st.info("📅 No publication date data available.")
                logger.warning("Publication year data is empty after filtering.")
        else:
            st.info("📅 Publication date data is not available or not in a numeric format.")
            logger.warning("Publication date data is not available or not numeric.")
    else:
        st.info("📊 No statistics to display as no books match the current filter criteria.")
        logger.debug("No statistics to display due to empty filtered DataFrame.")

```

---

### Source File: `ebk/streamlit/filters.py`

#### Source Code

```python
import pandas as pd
import streamlit as st
import logging

logger = logging.getLogger(__name__)

def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Sanitizes the DataFrame by ensuring correct data types and handling missing values.
    """
    # List of columns that should contain lists
    list_columns = ['creators', 'subjects', 'file_paths']
    
    def ensure_list(column):
        """
        Ensures that each entry in the column is a list. If not, replaces it with an empty list.
        """
        return column.apply(lambda x: x if isinstance(x, list) else [])
    
    for col in list_columns:
        if col in df.columns:
            df[col] = ensure_list(df[col])
            logger.debug(f"Processed list column: {col}")
        else:
            df[col] = [[] for _ in range(len(df))]
            logger.debug(f"Created empty list column: {col}")
    
    # Handle 'identifiers' column
    if 'identifiers' in df.columns:
        df['identifiers'] = df['identifiers'].apply(lambda x: x if isinstance(x, dict) else {})
        logger.debug("Sanitized 'identifiers' column.")
    else:
        df['identifiers'] = [{} for _ in range(len(df))]
        logger.debug("Created empty 'identifiers' column.")
    
    # Sanitize 'language' column
    if 'language' in df.columns:
        df['language'] = df['language'].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
        logger.debug("Sanitized 'language' column.")
    else:
        df['language'] = ['' for _ in range(len(df))]
        logger.debug("Created empty 'language' column.")
    
    # Sanitize 'cover_path' column
    if 'cover_path' in df.columns:
        df['cover_path'] = df['cover_path'].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
        logger.debug("Sanitized 'cover_path' column.")
    else:
        df['cover_path'] = ['' for _ in range(len(df))]
        logger.debug("Created empty 'cover_path' column.")
    
    # Sanitize string fields: 'title', 'description'
    string_fields = ['title', 'description']
    for field in string_fields:
        if field in df.columns:
            df[field] = df[field].apply(lambda x: x if isinstance(x, str) else '').fillna('').astype(str)
            logger.debug(f"Sanitized '{field}' column.")
        else:
            df[field] = ['' for _ in range(len(df))]
            logger.debug(f"Created empty '{field}' column.")
    
    # Sanitize 'date' column
    if 'date' in df.columns:
        df['date'] = pd.to_numeric(df['date'], errors='coerce')
        logger.debug("Sanitized 'date' column to ensure numeric types.")
    else:
        df['date'] = [None for _ in range(len(df))]
        logger.debug("Created empty 'date' column.")
    
    return df

def create_filters(df: pd.DataFrame) -> pd.DataFrame:
    """
    Creates and applies advanced filters to the DataFrame based on user inputs.
    Returns the filtered DataFrame.
    """
    # Sidebar for Filters
    st.sidebar.header("🔍 Filters")
    
    # Title Search
    title_search = st.sidebar.text_input("🔎 Search by Title")
    
    # Author Filter (Multi-select)
    all_creators = sorted(set(creator for creators in df['creators'] for creator in creators))
    selected_authors = st.sidebar.multiselect("👤 Filter by Author(s)", all_creators, default=[])
    
    # Subjects Filter (Multi-select)
    all_subjects = sorted(set(subject for subjects in df['subjects'] for subject in subjects))
    selected_subjects = st.sidebar.multiselect("📚 Filter by Subject(s)", all_subjects, default=[])

    # Search by Various Libraries
    all_libraries = sorted(set(lib for libs in df['virtual_libs'] for lib in libs))
    selected_libraries = st.sidebar.multiselect("📚 Filter by Virtual Library(s)", all_libraries, default=[])
    
    # Language Filter (Multi-select)
    all_languages = sorted(set(lang for lang in df['language'] if lang))
    selected_languages = st.sidebar.multiselect("🌐 Filter by Language(s)", all_languages, default=[])
    
    # Publication Date Filter (Range Slider)
    selected_years = None
    if 'date' in df.columns and pd.api.types.is_numeric_dtype(df['date']):
        min_year = int(df['date'].min()) if pd.notna(df['date'].min()) else 0
        max_year = int(df['date'].max()) if pd.notna(df['date'].max()) else 0
        if min_year and max_year:
            selected_years = st.sidebar.slider("📅 Publication Year Range", min_year, max_year, (min_year, max_year))
            logger.debug(f"Publication year range selected: {selected_years}")
        else:
            st.sidebar.info("📅 No valid publication year data available.")
            logger.warning("Publication year data is not available or entirely NaN.")
    else:
        st.sidebar.info("📅 Publication date data is not available or not in a numeric format.")
        logger.warning("Publication date data is not available or not numeric.")
    
    # Identifier Search
    identifier_search = st.sidebar.text_input("🔑 Search by Identifier (e.g., ISBN)")
    
    # Apply Filters
    filtered_df = df.copy()
    
    if title_search:
        filtered_df = filtered_df[filtered_df['title'].str.contains(title_search, case=False, na=False)]
        logger.debug(f"Applied title search filter: '{title_search}'")
    
    if selected_authors:
        filtered_df = filtered_df[filtered_df['creators'].apply(lambda x: any(creator in selected_authors for creator in x))]
        logger.debug(f"Applied author filter: {selected_authors}")
    
    if selected_subjects:
        filtered_df = filtered_df[filtered_df['subjects'].apply(lambda x: any(subject in selected_subjects for subject in x))]
        logger.debug(f"Applied subject filter: {selected_subjects}")

    if selected_libraries:
        filtered_df = filtered_df[filtered_df['virtual_libs'].apply(lambda x: any(lib in selected_libraries for lib in x))]
        logger.debug(f"Applied library filter: {selected_libraries}")
    
    if selected_languages:
        filtered_df = filtered_df[filtered_df['language'].isin(selected_languages)]
        logger.debug(f"Applied language filter: {selected_languages}")
    
    if selected_years:
        filtered_df = filtered_df[(filtered_df['date'] >= selected_years[0]) & (filtered_df['date'] <= selected_years[1])]
        logger.debug(f"Applied publication year range filter: {selected_years}")
    
    if identifier_search:
        idents = filtered_df['identifiers']
        idents_stringified = idents.apply(
            lambda x: ' '.join(f"{k}:{v}" for k, v in x.items()) if isinstance(x, dict) else str(x)
        )
        filtered_df = filtered_df[idents_stringified.str.contains(identifier_search)]
    
    return filtered_df

```

---

### Source File: `ebk/streamlit/utils.py`

#### Source Code

```python
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


```

---

