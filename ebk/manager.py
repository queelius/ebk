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
