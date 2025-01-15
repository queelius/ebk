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

