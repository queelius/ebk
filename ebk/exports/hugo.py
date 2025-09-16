import json
import shutil
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
            source_file = Path(book['File Path'])
            if source_file.exists():
                shutil.copy2(source_file, static_dir)
        if book["Cover Path"]:
            cover_file = Path(book['Cover Path'])
            if cover_file.exists():
                shutil.copy2(cover_file, static_dir)

    logger.debug(f"Exported {len(books)} books to Hugo site at '{hugo_dir}'")

