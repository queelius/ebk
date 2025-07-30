#!/usr/bin/env python3
"""
Demonstration of ebk's fluent API.
"""

from ebk import Library
from pathlib import Path
import tempfile


def main():
    """Run demo of fluent API features."""
    
    # Create a temporary library for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        print("Creating demo library...\n")
        lib = Library.create(temp_dir)
        
        # Add some books
        print("Adding books...")
        lib.add_entry(
            title="The Pragmatic Programmer",
            creators=["Andrew Hunt", "David Thomas"],
            subjects=["Programming", "Software Engineering", "Best Practices"],
            language="en",
            date="2019-09-13",
            publisher="Addison-Wesley",
            isbn="978-0135957059"
        )
        
        lib.add_entry(
            title="Clean Code",
            creators=["Robert C. Martin"],
            subjects=["Programming", "Software Engineering", "Code Quality"],
            language="en",
            date="2008-08-01",
            publisher="Prentice Hall",
            isbn="978-0132350884"
        )
        
        lib.add_entry(
            title="Design Patterns",
            creators=["Erich Gamma", "Richard Helm", "Ralph Johnson", "John Vlissides"],
            subjects=["Programming", "Software Design", "Patterns"],
            language="en",
            date="1994-10-31",
            publisher="Addison-Wesley"
        )
        
        lib.add_entry(
            title="Python Tricks",
            creators=["Dan Bader"],
            subjects=["Programming", "Python", "Tips"],
            language="en",
            date="2017-10-25",
            publisher="Real Python"
        )
        
        lib.add_entry(
            title="Effective Python",
            creators=["Brett Slatkin"],
            subjects=["Programming", "Python", "Best Practices"],
            language="en",
            date="2019-11-15",
            publisher="Addison-Wesley"
        )
        
        lib.save()
        print(f"Added {len(lib)} books to the library.\n")
        
        # Demonstrate queries
        print("=== Query Examples ===\n")
        
        # Simple search
        print("1. Books with 'Python' in title or subjects:")
        results = lib.search("Python")
        for entry in results:
            print(f"   - {entry.title} by {', '.join(entry.creators)}")
        
        # Query builder
        print("\n2. Books published after 2010:")
        results = lib.query().where("date", "2010", ">").order_by("date").execute()
        for book in results:
            print(f"   - {book['title']} ({book['date'][:4]})")
        
        # Complex query
        print("\n3. Programming books with multiple authors:")
        results = (lib.query()
                  .where("subjects", "Programming", "contains")
                  .where_lambda(lambda e: len(e.get("creators", [])) > 1)
                  .execute())
        for book in results:
            print(f"   - {book['title']} by {len(book['creators'])} authors")
        
        # Statistics
        print("\n=== Library Statistics ===\n")
        stats = lib.stats()
        print(f"Total books: {stats['total_entries']}")
        print(f"Subjects: {', '.join(list(stats['subjects'].keys())[:5])}...")
        print(f"Publishers: {len(set(e.get('publisher', 'Unknown') for e in lib._entries))}")
        
        # Grouping
        print("\n=== Books by Subject ===\n")
        by_subject = lib.group_by("subjects")
        for subject, entries in sorted(by_subject.items())[:5]:
            print(f"{subject}: {len(entries)} books")
        
        # Modifications
        print("\n=== Modifications ===\n")
        
        # Tag all books
        lib.tag_all("ebook")
        print("Tagged all books with 'ebook'")
        
        # Update specific entries
        python_books = lib.filter(lambda e: "Python" in str(e.get("subjects", [])))
        python_books.update_all(lambda e: e.add_subject("Python Programming"))
        print(f"Updated {len(python_books)} Python books")
        
        # Find duplicates
        print("\n=== Duplicate Check ===")
        duplicates = lib.duplicates(by="publisher")
        for publisher, books in duplicates:
            if publisher:  # Skip empty publishers
                print(f"\n{publisher}:")
                for book in books:
                    print(f"  - {book.title}")
        
        # Demonstrate chaining
        print("\n=== Method Chaining ===\n")
        entry = lib[0]
        (entry.set("edition", "20th Anniversary")
              .add_subject("Classic")
              .set("rating", 5))
        print(f"Updated: {entry.title}")
        print(f"  Edition: {entry.get('edition')}")
        print(f"  Subjects: {', '.join(entry.subjects)}")
        print(f"  Rating: {entry.get('rating')}")
        
        # Transaction example
        print("\n=== Transaction Example ===\n")
        initial_count = len(lib)
        try:
            with lib.transaction():
                lib.add_entry(title="Test Book 1", creators=["Test Author"])
                lib.add_entry(title="Test Book 2", creators=["Test Author"])
                print(f"Added 2 books in transaction (now {len(lib)} total)")
                # Simulate error
                raise Exception("Simulated error!")
        except:
            print(f"Transaction rolled back - still {len(lib)} books")
        
        # Successful transaction
        with lib.transaction():
            lib.add_entry(title="Real Book", creators=["Real Author"])
        print(f"Successful transaction - now {len(lib)} books")
        
        # Export demo (without actual file operations)
        print("\n=== Export Examples ===")
        print("lib.export_to_zip('/path/to/library.zip')")
        print("lib.export_to_hugo('/path/to/hugo', organize_by='subject')")
        print("lib.filter(lambda e: e.get('rating', 0) >= 4).export_to_hugo('/featured')")


if __name__ == "__main__":
    main()