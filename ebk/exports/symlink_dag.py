"""
Export library as a navigable directory structure using symlinks to represent tag hierarchies.

This module creates a filesystem view of the library where:
- Tags are represented as directories in a hierarchy
- Books appear in all relevant tag directories via symlinks
- The DAG structure of tags is preserved through the directory tree
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
import re
from collections import defaultdict


class SymlinkDAGExporter:
    """Creates a navigable directory structure using symlinks to represent tag hierarchies."""
    
    def __init__(self):
        self.tag_separator = "/"  # Separator for hierarchical tags
        self.books_dir_name = "_books"  # Directory to store actual book files
        
    def export(self, lib_dir: str, output_dir: str, 
               tag_field: str = "subjects",
               include_files: bool = True,
               create_index: bool = True):
        """
        Export library as symlink-based directory structure.
        
        Args:
            lib_dir: Path to the ebk library
            output_dir: Output directory for the symlink structure
            tag_field: Field to use for tags (default: "subjects")
            include_files: Whether to copy actual ebook files
            create_index: Whether to create index.html files in directories
        """
        lib_path = Path(lib_dir)
        output_path = Path(output_dir)
        
        # Load metadata
        metadata_file = lib_path / "metadata.json"
        with open(metadata_file, "r") as f:
            entries = json.load(f)
        
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create books directory for actual files
        books_path = output_path / self.books_dir_name
        books_path.mkdir(exist_ok=True)
        
        # Process each entry
        entry_paths = {}  # Map entry ID to its path in _books
        tag_entries = defaultdict(list)  # Map tag to list of entries
        
        for i, entry in enumerate(entries):
            entry_id = entry.get("unique_id", f"entry_{i}")
            
            # Create entry directory in _books
            entry_dir = books_path / self._sanitize_filename(entry_id)
            entry_dir.mkdir(exist_ok=True)
            entry_paths[entry_id] = entry_dir
            
            # Save metadata
            with open(entry_dir / "metadata.json", "w") as f:
                json.dump(entry, f, indent=2)
            
            # Copy files if requested
            if include_files:
                self._copy_entry_files(entry, lib_path, entry_dir)
            
            # Create a readable symlink name
            title = entry.get("title", "Unknown Title")
            creators = entry.get("creators", [])
            if creators:
                readable_name = f"{self._sanitize_filename(title)} - {self._sanitize_filename(creators[0])}"
            else:
                readable_name = self._sanitize_filename(title)
            
            # Store readable name for later use
            entry["_readable_name"] = readable_name
            entry["_entry_id"] = entry_id
            
            # Extract tags and build hierarchy
            tags = entry.get(tag_field, [])
            if isinstance(tags, str):
                tags = [tags]
            
            for tag in tags:
                # Add to this tag and all parent tags
                tag_parts = tag.split(self.tag_separator)
                for i in range(len(tag_parts)):
                    parent_tag = self.tag_separator.join(tag_parts[:i+1])
                    tag_entries[parent_tag].append(entry)
        
        # Create tag directory structure with symlinks
        self._create_tag_structure(output_path, tag_entries, entry_paths)
        
        # Create root index if requested
        if create_index:
            self._create_index_files(output_path, tag_entries, entries)
        
        # Create a README
        self._create_readme(output_path, len(entries), len(tag_entries))
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be safe as a filename."""
        # Replace problematic characters
        name = re.sub(r'[<>:"/\\|?*]', '-', str(name))
        # Remove leading/trailing spaces and dots
        name = name.strip('. ')
        # Limit length
        if len(name) > 200:
            name = name[:200]
        return name or "unnamed"
    
    def _copy_entry_files(self, entry: Dict, lib_path: Path, entry_dir: Path):
        """Copy ebook and cover files for an entry."""
        # Copy ebook files
        for file_path in entry.get("file_paths", []):
            src_file = lib_path / file_path
            if src_file.exists():
                dest_file = entry_dir / src_file.name
                shutil.copy2(src_file, dest_file)
        
        # Copy cover file
        cover_path = entry.get("cover_path")
        if cover_path:
            src_cover = lib_path / cover_path
            if src_cover.exists():
                dest_cover = entry_dir / src_cover.name
                shutil.copy2(src_cover, dest_cover)
    
    def _create_tag_structure(self, output_path: Path, 
                            tag_entries: Dict[str, List[Dict]], 
                            entry_paths: Dict[str, Path]):
        """Create the hierarchical tag directory structure with symlinks."""
        # Sort tags to ensure parents are created before children
        sorted_tags = sorted(tag_entries.keys())
        
        for tag in sorted_tags:
            # Create tag directory path
            tag_parts = tag.split(self.tag_separator)
            tag_dir = output_path
            for part in tag_parts:
                tag_dir = tag_dir / self._sanitize_filename(part)
            tag_dir.mkdir(parents=True, exist_ok=True)
            
            # Get unique entries for this tag (avoid duplicates)
            seen_ids = set()
            unique_entries = []
            for entry in tag_entries[tag]:
                entry_id = entry["_entry_id"]
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    unique_entries.append(entry)
            
            # Create symlinks to entries
            for entry in unique_entries:
                entry_id = entry["_entry_id"]
                readable_name = entry["_readable_name"]
                
                # Path to actual entry in _books
                target_path = Path("..") / Path(*[".."] * len(tag_parts)) / self.books_dir_name / self._sanitize_filename(entry_id)
                
                # Create symlink
                symlink_path = tag_dir / readable_name
                
                # Remove existing symlink if it exists
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                
                # Create relative symlink
                try:
                    symlink_path.symlink_to(target_path)
                except OSError as e:
                    # On Windows, creating symlinks might require admin privileges
                    print(f"Warning: Could not create symlink for '{readable_name}': {e}")
    
    def _create_index_files(self, output_path: Path, 
                          tag_entries: Dict[str, List[Dict]], 
                          all_entries: List[Dict]):
        """Create index.html files in each directory for web browsing."""
        # Create root index
        self._write_index_file(output_path, "Library Root", all_entries, tag_entries.keys())
        
        # Create index for each tag directory
        for tag, entries in tag_entries.items():
            tag_parts = tag.split(self.tag_separator)
            tag_dir = output_path
            for part in tag_parts:
                tag_dir = tag_dir / self._sanitize_filename(part)
            
            # Get child tags
            child_tags = set()
            tag_prefix = tag + self.tag_separator
            for other_tag in tag_entries.keys():
                if other_tag.startswith(tag_prefix) and other_tag != tag:
                    # Check if it's a direct child
                    remaining = other_tag[len(tag_prefix):]
                    if self.tag_separator not in remaining:
                        child_tags.add(other_tag)
            
            # Get unique entries
            seen_ids = set()
            unique_entries = []
            for entry in entries:
                entry_id = entry.get("_entry_id", entry.get("unique_id"))
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    unique_entries.append(entry)
            
            self._write_index_file(tag_dir, tag, unique_entries, child_tags)
    
    def _write_index_file(self, directory: Path, title: str, 
                         entries: List[Dict], child_tags: Set[str]):
        """Write an index.html file for a directory."""
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title} - EBK Library</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .section {{ margin: 20px 0; }}
        .tag {{ 
            display: inline-block; 
            margin: 5px; 
            padding: 5px 10px; 
            background: #e0e0e0; 
            border-radius: 3px;
            text-decoration: none;
            color: #333;
        }}
        .tag:hover {{ background: #d0d0d0; }}
        .book {{ 
            margin: 10px 0; 
            padding: 10px; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
        }}
        .book-title {{ font-weight: bold; color: #2c3e50; }}
        .book-author {{ color: #7f8c8d; }}
        .book-link {{ text-decoration: none; color: #3498db; }}
        .book-link:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="section">
        <a href="../index.html" class="tag">⬆ Parent</a>
        <a href="/" class="tag">🏠 Root</a>
    </div>
"""
        
        # Add child tags section
        if child_tags:
            html_content += """
    <div class="section">
        <h2>Subcategories</h2>
"""
            for child_tag in sorted(child_tags):
                tag_name = child_tag.split(self.tag_separator)[-1]
                safe_name = self._sanitize_filename(tag_name)
                html_content += f'        <a href="{safe_name}/index.html" class="tag">📁 {tag_name}</a>\n'
            
            html_content += "    </div>\n"
        
        # Add books section
        if entries:
            html_content += f"""
    <div class="section">
        <h2>Books ({len(entries)})</h2>
"""
            for entry in sorted(entries, key=lambda e: e.get("title", "")):
                title = entry.get("title", "Unknown Title")
                creators = ", ".join(entry.get("creators", ["Unknown Author"]))
                readable_name = entry.get("_readable_name", title)
                
                html_content += f"""
        <div class="book">
            <div class="book-title">{title}</div>
            <div class="book-author">by {creators}</div>
            <a href="{readable_name}" class="book-link">📂 Open</a>
        </div>
"""
        
            html_content += "    </div>\n"
        
        html_content += """
</body>
</html>
"""
        
        # Write the file
        index_path = directory / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    
    def _create_readme(self, output_path: Path, num_entries: int, num_tags: int):
        """Create a README file explaining the structure."""
        readme_content = f"""# EBK Library - Symlink Navigation Structure

This directory contains a navigable view of your ebook library organized by tags.

## Statistics
- Total books: {num_entries}
- Total tags/categories: {num_tags}

## Structure

- **_books/**: Contains the actual ebook files and metadata
- **Tag directories**: Each tag becomes a directory, with hierarchical tags creating nested directories
- **Symlinks**: Books appear in multiple tag directories via symbolic links

## Navigation

You can navigate this structure using:
1. Your file explorer (Finder, Windows Explorer, etc.)
2. Command line tools (cd, ls, etc.)
3. Web browser (open index.html files)

## Hierarchical Tags

Tags like "Programming/Python/Web" create a nested structure:
```
Programming/
  Python/
    Web/
      (books tagged with Programming/Python/Web)
    (books tagged with Programming/Python)
  (books tagged with Programming)
```

Books appear at each relevant level in the hierarchy.

## Notes

- This is a read-only view. Modifying files here won't affect the original library.
- Symlinks point to files in the _books directory.
- On Windows, you may need administrator privileges to create symlinks.

Generated by EBK - https://github.com/queelius/ebk
"""
        
        with open(output_path / "README.md", "w") as f:
            f.write(readme_content)


def export_symlink_dag(lib_dir: str, output_dir: str, **kwargs):
    """
    Convenience function to export library as symlink DAG.
    
    Args:
        lib_dir: Path to ebk library
        output_dir: Output directory
        **kwargs: Additional arguments passed to SymlinkDAGExporter.export()
    """
    exporter = SymlinkDAGExporter()
    exporter.export(lib_dir, output_dir, **kwargs)