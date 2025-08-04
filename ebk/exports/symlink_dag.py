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
               include_files: bool = False,  # Changed default to False
               create_index: bool = True,
               flatten: bool = False,
               min_books: int = 0):
        """
        Export library as symlink-based directory structure.
        
        Args:
            lib_dir: Path to the ebk library
            output_dir: Output directory for the symlink structure
            tag_field: Field to use for tags (default: "subjects")
            include_files: Whether to copy actual ebook files (default: False)
            create_index: Whether to create index.html files in directories
            flatten: Whether to create direct symlinks to files instead of _books structure
            min_books: Minimum books per tag folder; smaller folders go to _misc (default: 0)
        """
        lib_path = Path(lib_dir)
        output_path = Path(output_dir)
        
        # Load metadata
        metadata_file = lib_path / "metadata.json"
        with open(metadata_file, "r") as f:
            entries = json.load(f)
        
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create books directory for actual files (unless flattening)
        if not flatten:
            books_path = output_path / self.books_dir_name
            books_path.mkdir(exist_ok=True)
        
        # Process each entry
        entry_paths = {}  # Map entry ID to its path in _books
        tag_entries = defaultdict(list)  # Map tag to list of entries
        
        for i, entry in enumerate(entries):
            entry_id = entry.get("unique_id", f"entry_{i}")
            
            if not flatten:
                # Create entry directory in _books
                entry_dir = books_path / self._sanitize_filename(entry_id)
                entry_dir.mkdir(exist_ok=True)
                entry_paths[entry_id] = entry_dir
                
                # Save metadata
                with open(entry_dir / "metadata.json", "w") as f:
                    json.dump(entry, f, indent=2)
                
                # Handle files - either copy or symlink
                if include_files:
                    self._copy_entry_files(entry, lib_path, entry_dir)
                else:
                    # Create symlinks to original files
                    self._symlink_entry_files(entry, lib_path, entry_dir)
            else:
                # For flatten mode, store original file paths
                entry_paths[entry_id] = entry.get("file_paths", [])
            
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
        
        # Consolidate small tag folders if min_books is set
        if min_books > 0:
            tag_entries = self._consolidate_small_tags(tag_entries, min_books)
        
        # Create tag directory structure with symlinks
        self._create_tag_structure(output_path, tag_entries, entry_paths, flatten, lib_path)
        
        # Create root index if requested
        if create_index:
            self._create_index_files(output_path, tag_entries, entries)
        
        # Create a README
        self._create_readme(output_path, len(entries), len(tag_entries))
    
    def _consolidate_small_tags(self, tag_entries: Dict[str, List[Dict]], 
                               min_books: int) -> Dict[str, List[Dict]]:
        """Consolidate tags with fewer than min_books into a _misc folder."""
        consolidated = defaultdict(list)
        misc_entries = []
        
        for tag, entries in tag_entries.items():
            # Get unique entries for this tag
            seen_ids = set()
            unique_entries = []
            for entry in entries:
                entry_id = entry.get("_entry_id", entry.get("unique_id"))
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    unique_entries.append(entry)
            
            # Check if this tag has enough unique books
            if len(unique_entries) < min_books:
                # Check if it's a leaf tag (no children with enough books)
                tag_prefix = tag + self.tag_separator
                has_large_children = any(
                    other_tag.startswith(tag_prefix) and 
                    len(set(e.get("_entry_id", e.get("unique_id")) for e in tag_entries[other_tag])) >= min_books
                    for other_tag in tag_entries.keys()
                )
                
                if not has_large_children:
                    # Add to misc folder with tag prefix
                    for entry in unique_entries:
                        misc_entry = entry.copy()
                        # Store original tag for display in misc folder
                        misc_entry["_original_tag"] = tag
                        misc_entries.append(misc_entry)
                else:
                    # Keep it as is because it has large children
                    consolidated[tag] = entries
            else:
                # Keep tags with enough books
                consolidated[tag] = entries
        
        # Add misc entries if any
        if misc_entries:
            consolidated["_misc"] = misc_entries
        
        return dict(consolidated)
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize a string to be safe as a filename."""
        # Replace problematic characters
        name = re.sub(r'[<>:"/\\|?*]', '-', str(name))
        # Remove leading/trailing spaces and dots
        name = name.strip('. ')
        # Limit length (being more conservative)
        if len(name) > 150:
            name = name[:147] + "..."
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
    
    def _symlink_entry_files(self, entry: Dict, lib_path: Path, entry_dir: Path):
        """Create symlinks to ebook and cover files for an entry."""
        # Symlink ebook files
        for file_path in entry.get("file_paths", []):
            src_file = lib_path / file_path
            if src_file.exists():
                # Get absolute path of source file
                abs_src = src_file.resolve()
                dest_link = entry_dir / src_file.name
                
                # Remove existing symlink if it exists
                if dest_link.exists() or dest_link.is_symlink():
                    dest_link.unlink()
                
                try:
                    # Create symlink using absolute path
                    dest_link.symlink_to(abs_src)
                except OSError as e:
                    print(f"Warning: Could not create symlink for '{file_path}': {e}")
        
        # Symlink cover file
        cover_path = entry.get("cover_path")
        if cover_path:
            src_cover = lib_path / cover_path
            if src_cover.exists():
                # Get absolute path of source cover
                abs_cover = src_cover.resolve()
                dest_link = entry_dir / src_cover.name
                
                if dest_link.exists() or dest_link.is_symlink():
                    dest_link.unlink()
                
                try:
                    # Create symlink using absolute path
                    dest_link.symlink_to(abs_cover)
                except OSError as e:
                    print(f"Warning: Could not create symlink for cover '{cover_path}': {e}")
    
    def _create_tag_structure(self, output_path: Path, 
                            tag_entries: Dict[str, List[Dict]], 
                            entry_paths: Dict[str, Path],
                            flatten: bool = False,
                            lib_path: Path = None):
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
                
                # For _misc folder, include original tag in the name
                if tag == "_misc" and "_original_tag" in entry:
                    original_tag = entry["_original_tag"]
                    # Shorten the tag to avoid filesystem limits
                    tag_parts = original_tag.split(self.tag_separator)
                    if len(tag_parts) > 2:
                        # Use only the last two parts of hierarchical tags
                        short_tag = self.tag_separator.join(tag_parts[-2:])
                    else:
                        short_tag = original_tag
                    
                    # Further limit tag length
                    if len(short_tag) > 50:
                        short_tag = short_tag[:47] + "..."
                    
                    tag_prefix = f"[{short_tag.replace(self.tag_separator, '-')}] "
                    
                    # Ensure the total name isn't too long
                    max_name_length = 200  # Safe limit for most filesystems
                    if len(tag_prefix + readable_name) > max_name_length:
                        # Truncate the readable name to fit
                        available_length = max_name_length - len(tag_prefix) - 3
                        readable_name = readable_name[:available_length] + "..."
                
                if not flatten:
                    # Path to actual entry in _books
                    target_path = Path(*[".."] * len(tag_parts)) / self.books_dir_name / self._sanitize_filename(entry_id)
                    # Create symlink
                    symlink_path = tag_dir / readable_name
                else:
                    # For flatten mode, create direct symlinks to original files
                    file_paths = entry_paths.get(entry_id, [])
                    if file_paths:
                        # Use the first file path (usually the main ebook file)
                        original_file = file_paths[0]
                        # Get absolute path to the original file
                        abs_file_path = (lib_path / original_file).resolve()
                        # Use original filename as symlink name
                        symlink_path = tag_dir / Path(original_file).name
                        target_path = abs_file_path
                    else:
                        continue  # Skip if no files
                
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
        # Create root index with tag counts
        root_child_tags = {}
        for tag, entries in tag_entries.items():
            if self.tag_separator not in tag:  # Top-level tags only
                unique_count = len(set(e.get("_entry_id", e.get("unique_id")) 
                                     for e in entries))
                root_child_tags[tag] = unique_count
        self._write_index_file(output_path, "Library Root", all_entries, root_child_tags, output_path)
        
        # Create index for each tag directory
        for tag, entries in tag_entries.items():
            tag_parts = tag.split(self.tag_separator)
            tag_dir = output_path
            for part in tag_parts:
                tag_dir = tag_dir / self._sanitize_filename(part)
            
            # Get child tags with counts
            child_tags = {}
            tag_prefix = tag + self.tag_separator
            for other_tag, other_entries in tag_entries.items():
                if other_tag.startswith(tag_prefix) and other_tag != tag:
                    # Check if it's a direct child
                    remaining = other_tag[len(tag_prefix):]
                    if self.tag_separator not in remaining:
                        # Count unique entries for this tag
                        unique_count = len(set(e.get("_entry_id", e.get("unique_id")) 
                                             for e in other_entries))
                        child_tags[other_tag] = unique_count
            
            # Get unique entries
            seen_ids = set()
            unique_entries = []
            for entry in entries:
                entry_id = entry.get("_entry_id", entry.get("unique_id"))
                if entry_id not in seen_ids:
                    seen_ids.add(entry_id)
                    unique_entries.append(entry)
            
            self._write_index_file(tag_dir, tag, unique_entries, child_tags, output_path)
    
    def _write_index_file(self, directory: Path, title: str, 
                         entries: List[Dict], child_tags: Dict[str, int], output_path: Path):
        """Write an index.html file for a directory using Jinja2 template."""
        from jinja2 import Environment, FileSystemLoader
        import json
        import re
        
        # Prepare entries for JSON (clean and escape)
        clean_entries = []
        for entry in entries:
            clean_entry = {}
            for key, value in entry.items():
                if isinstance(value, str):
                    # Remove problematic HTML from descriptions
                    if key == "description":
                        # Strip HTML tags from description for JSON
                        value = re.sub(r'<[^>]+>', '', value)
                        # Limit description length
                        if len(value) > 500:
                            value = value[:500] + "..."
                    clean_entry[key] = value
                elif isinstance(value, list):
                    clean_entry[key] = [str(v) for v in value]
                else:
                    clean_entry[key] = str(value)
            clean_entries.append(clean_entry)
        
        # Convert to JSON for JavaScript
        entries_json = json.dumps(clean_entries, ensure_ascii=True)
        
        # Set up Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("advanced_index.html")
        
        # Calculate if we're in a subdirectory (for proper _books path)
        is_subdir = directory != output_path
        
        # Render template
        html_content = template.render(
            title=title,
            entries=entries,
            entries_json=entries_json,
            child_tags=child_tags,
            tag_separator=self.tag_separator,
            is_subdir=is_subdir
        )
        
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