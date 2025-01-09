from .convert_calibre import convert_calibre
from .manager import LibraryManager
from .exporter import export_to_hugo

# Define the public API
__all__ = ["convert_calibre", "LibraryManager", "export_to_hugo"]

# Optional package metadata
__version__ = "0.1.0"
__author__ = "Alex Towell"
__email__ = "lex@metafunctor.com"
