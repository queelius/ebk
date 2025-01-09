import json
from pathlib import Path

def load_json(file_path):
    """Load a JSON file into memory."""
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    with open(file_path, "r") as f:
        return json.load(f)

def save_json(data, file_path):
    """Save a dictionary or list to a JSON file."""
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Saved JSON to {file_path}.")

def search_metadata(library, query):
    """Search metadata in the library for a query string."""
    query = query.lower()
    return [
        book for book in library
        if query in book["Title"].lower() or
           query in book["Author"].lower() or
           query in book["Tags"].lower()
    ]

def slugify(text):
    """Generate a URL-friendly slug from a string."""
    return text.replace(" ", "-").lower()

def copy_file(src, dest):
    """Copy a file from src to dest."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if Path(src).exists():
        dest.write_bytes(Path(src).read_bytes())
        return True
    return False
