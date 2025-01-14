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
