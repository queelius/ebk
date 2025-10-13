# Python API

Comprehensive guide to ebk's Python API for programmatic library management.

## Overview

ebk provides a powerful SQLAlchemy-based API for working with ebook libraries programmatically. The API follows modern Python conventions and supports context managers, fluent queries, and async operations (for LLM features).

## Basic Usage

### Opening a Library

```python
from pathlib import Path
from ebk.library_db import Library

# Open existing library
lib = Library.open(Path("~/my-library"))

# Use context manager (recommended)
with Library.open(Path("~/my-library")) as lib:
    # Work with library
    results = lib.search("Python")
    
# Library is automatically closed
```

See the [API Guide](/home/spinoza/github/beta/ebk/docs/API_GUIDE.md) for complete documentation.

## Core Classes

- `Library` - Main library class
- `Book` - Book model (SQLAlchemy ORM)
- `Author` - Author model
- `Subject` - Subject/tag model
- `File` - File model
- `Cover` - Cover image model

## Further Reading

- [API Guide](../API_GUIDE.md) - Complete API reference
- [LLM Features](llm-features.md) - AI-powered features
- [CLI Reference](cli.md) - Command-line interface
