"""Base exporter class for ebk library exports."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import shutil
import re
from .html_utils import create_safe_filename, sanitize_for_html


class BaseExporter(ABC):
    """
    Abstract base class for all ebk exporters.
    
    Provides common functionality for exporting library data:
    - Loading metadata
    - File operations (copy/symlink)
    - Filename sanitization
    - Directory management
    """
    
    def __init__(self):
        """Initialize the base exporter."""
        self.library_path = None
        self.output_path = None
        self.entries = []
        
    def load_metadata(self, library_path: Path) -> List[Dict]:
        """
        Load metadata from the library.
        
        Args:
            library_path: Path to the ebk library
            
        Returns:
            List of entry dictionaries
            
        Raises:
            FileNotFoundError: If metadata.json doesn't exist
            json.JSONDecodeError: If metadata is invalid
        """
        self.library_path = Path(library_path)
        metadata_path = self.library_path / "metadata.json"
        
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found at {metadata_path}")
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.entries = json.load(f)
            
        return self.entries
    
    def prepare_output_directory(self, output_path: Path, clean: bool = True):
        """
        Prepare the output directory.
        
        Args:
            output_path: Path for output
            clean: Whether to clean existing directory
        """
        self.output_path = Path(output_path)
        
        if clean and self.output_path.exists():
            shutil.rmtree(self.output_path)
            
        self.output_path.mkdir(parents=True, exist_ok=True)
    
    def copy_entry_files(self, entry: Dict, source_dir: Path, dest_dir: Path):
        """
        Copy entry files (ebooks and covers) to destination.
        
        Args:
            entry: Entry dictionary
            source_dir: Source library directory
            dest_dir: Destination directory
        """
        # Copy ebook files
        for file_path in entry.get('file_paths', []):
            src_file = source_dir / file_path
            if src_file.exists():
                dest_file = dest_dir / Path(file_path).name
                shutil.copy2(src_file, dest_file)
        
        # Copy cover image
        cover_path = entry.get('cover_path')
        if cover_path:
            src_cover = source_dir / cover_path
            if src_cover.exists():
                dest_cover = dest_dir / Path(cover_path).name
                shutil.copy2(src_cover, dest_cover)
    
    def symlink_entry_files(self, entry: Dict, source_dir: Path, dest_dir: Path):
        """
        Create symlinks to entry files instead of copying.
        
        Args:
            entry: Entry dictionary
            source_dir: Source library directory
            dest_dir: Destination directory
        """
        # Symlink ebook files
        for file_path in entry.get('file_paths', []):
            src_file = source_dir / file_path
            if src_file.exists():
                dest_file = dest_dir / Path(file_path).name
                if not dest_file.exists():
                    dest_file.symlink_to(src_file.absolute())
        
        # Symlink cover image
        cover_path = entry.get('cover_path')
        if cover_path:
            src_cover = source_dir / cover_path
            if src_cover.exists():
                dest_cover = dest_dir / Path(cover_path).name
                if not dest_cover.exists():
                    dest_cover.symlink_to(src_cover.absolute())
    
    def sanitize_filename(self, name: str, max_length: int = 100) -> str:
        """
        Sanitize filename to be filesystem-safe.
        
        Args:
            name: Original filename
            max_length: Maximum length for filename
            
        Returns:
            Sanitized filename
        """
        return create_safe_filename(name, max_length=max_length)
    
    def get_readable_name(self, entry: Dict) -> str:
        """
        Get a human-readable name for an entry.
        
        Args:
            entry: Entry dictionary
            
        Returns:
            Readable name combining title and author
        """
        title = entry.get('title', 'Unknown')
        creators = entry.get('creators', [])
        
        if creators:
            author = creators[0]
            if len(creators) > 1:
                author += " et al."
            return f"{title} - {author}"
        
        return title
    
    def write_json(self, data: Any, file_path: Path):
        """
        Write JSON data to file with proper encoding.
        
        Args:
            data: Data to serialize
            file_path: Output file path
        """
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def create_readme(self, output_dir: Path, stats: Dict):
        """
        Create a README file with export information.
        
        Args:
            output_dir: Output directory
            stats: Statistics dictionary
        """
        readme_path = output_dir / "README.md"
        
        content = f"""# EBK Library Export

This directory contains an export of an EBK library.

## Statistics
- Total entries: {stats.get('total_entries', 0)}
- Export date: {stats.get('export_date', 'Unknown')}
- Export type: {stats.get('export_type', 'Unknown')}

## Structure
{stats.get('structure_description', 'See directory contents for structure.')}

---
Generated by EBK Library Manager
"""
        
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    @abstractmethod
    def export(self, library_path: Path, output_path: Path, **options):
        """
        Export the library.
        
        This method must be implemented by subclasses.
        
        Args:
            library_path: Path to source library
            output_path: Path for output
            **options: Additional export options
        """
        pass
    
    def validate_export(self) -> bool:
        """
        Validate that the export was successful.
        
        Returns:
            True if validation passes
        """
        if not self.output_path or not self.output_path.exists():
            return False
            
        # Check if at least some files were created
        return any(self.output_path.iterdir())