# Quick Start Guide

This guide will help you get started with ebk in just a few minutes.

## Creating Your First Library

### From Calibre
If you have an existing Calibre library:

```bash
ebk import-calibre ~/Calibre/Library --output-dir ~/my-ebooks
```

### From Raw eBooks
If you have a folder of PDF/EPUB files:

```bash
ebk import-ebooks ~/Downloads/ebooks --output-dir ~/my-ebooks
```

## Basic Operations

### List All Books
```bash
ebk list ~/my-ebooks
```

### Search for Books
```bash
# Search by title
ebk search "Python" ~/my-ebooks

# Search in multiple fields
ebk search "Machine Learning" ~/my-ebooks --regex-fields title subjects

# Advanced JMESPath query
ebk search "[?language=='en' && date >= '2020']" ~/my-ebooks --jmespath
```

### View Statistics
```bash
ebk stats ~/my-ebooks
```

## Using the Python API

```python
from ebk import Library

# Open your library
lib = Library.open("~/my-ebooks")

# Search for books
python_books = lib.search("Python")
for book in python_books:
    print(f"{book.title} by {', '.join(book.creators)}")

# Add a new book
lib.add_entry(
    title="Deep Learning",
    creators=["Ian Goodfellow", "Yoshua Bengio"],
    subjects=["Machine Learning", "Neural Networks"],
    language="en"
).save()

# Find similar books
similar = lib.find_similar(python_books[0].id)

# Export to Hugo
lib.export_to_hugo("~/my-blog", organize_by="subject")
```

## Launching the Web Interface

If you installed with the streamlit extra:

```bash
pip install ebk[streamlit]
streamlit run -m ebk.integrations.streamlit.app -- ~/my-ebooks
```

Then open http://localhost:8501 in your browser.

## Next Steps

- Learn about [advanced search options](../user-guide/search.md)
- Explore [import/export formats](../user-guide/import-export.md)
- Discover [library management](../user-guide/library-management.md) features
- Set up [integrations](../integrations/index.md)