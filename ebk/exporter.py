import os
from pathlib import Path

def export_to_hugo(json_file, hugo_dir):
    """Export JSON metadata to Hugo-compatible Markdown files."""
    with open(json_file, "r") as f:
        books = json.load(f)

    content_dir = Path(hugo_dir) / "content" / "library"
    static_dir = Path(hugo_dir) / "static" / "ebooks"
    content_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    for book in books:
        slug = book['Title'].replace(" ", "-").lower()
        md_file = content_dir / f"{slug}.md"

        with open(md_file, "w") as md:
            md.write("---\n")
            md.write(f"title: {book['Title']}\n")
            md.write(f"author: {book['Author']}\n")
            md.write(f"tags: [{', '.join(book['Tags'].split(', '))}]\n")
            md.write(f"ebook_file: /ebooks/{Path(book['File Path']).name}\n")
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

    print(f"Exported {len(books)} books to Hugo at {hugo_dir}.")
