"""Multi-faceted export for ebk libraries with sidebar navigation."""

from pathlib import Path
from typing import Dict, List, Set, Optional
import json
import shutil
from collections import defaultdict
import re
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from .html_utils import sanitize_entries_for_javascript, sanitize_for_html, create_safe_filename
from .base_exporter import BaseExporter


class MultiFacetExporter(BaseExporter):
    """Export library with multiple faceted navigation (subjects, authors, etc.)."""  
    
    def __init__(self, facets: Optional[Dict[str, str]] = None):
        """
        Initialize the multi-facet exporter.
        
        Args:
            facets: Dictionary mapping facet names to metadata fields
                   e.g., {"Subjects": "subjects", "Authors": "creators", "Years": "date"}
        """
        super().__init__()
        self.facets = facets or {
            "Subjects": "subjects",
            "Authors": "creators",
            "Publishers": "publisher",
            "Languages": "language"
        }
    
    def export(self, library_path: Path, output_path: Path, 
               include_files: bool = False,
               create_index: bool = True, **options):
        """Export the library with multi-faceted navigation."""
        # Use base class methods
        entries = self.load_metadata(library_path)
        self.prepare_output_directory(output_path)
        
        # Build facet data
        facet_data = self._build_facet_data(entries)
        
        # Create _books directory structure
        books_dir = output_path / "_books"
        books_dir.mkdir()
        
        # Process each entry
        for entry in entries:
            entry_id = entry.get("unique_id", "")
            if not entry_id:
                continue
            
            # Create entry directory
            entry_dir = books_dir / self._sanitize_filename(entry_id)
            entry_dir.mkdir(exist_ok=True)
            
            # Use base class file operations
            if include_files:
                self.copy_entry_files(entry, library_path, entry_dir)
            else:
                self.symlink_entry_files(entry, library_path, entry_dir)
            
            # Write entry metadata using base class method
            self.write_json(entry, entry_dir / "metadata.json")
            
            # Add computed fields for template
            entry["_entry_id"] = entry_id
            entry["_readable_name"] = self.get_readable_name(entry)
        
        # Create index.html if requested
        if create_index:
            self._create_index_file(output_path, entries, facet_data)
        
        # Create README using base class method
        stats = {
            'total_entries': len(entries),
            'export_date': datetime.now().isoformat(),
            'export_type': 'Multi-Faceted Export',
            'structure_description': f"Organized by {len(self.facets)} facets with {len(entries)} entries"
        }
        self.create_readme(output_path, stats)
    
    def _build_facet_data(self, entries: List[Dict]) -> Dict[str, Dict]:
        """Build facet data structure from entries."""
        facet_data = {}
        
        for facet_name, field_name in self.facets.items():
            items = defaultdict(int)
            
            for entry in entries:
                values = entry.get(field_name, [])
                if not isinstance(values, list):
                    values = [values] if values else []
                
                for value in values:
                    if value:  # Skip empty values
                        # Special handling for dates - extract year
                        if field_name == "date" and value:
                            try:
                                year = str(value)[:4]
                                if year.isdigit():
                                    items[year] += 1
                            except (KeyError, ValueError, AttributeError):
                                pass  # Skip entries with invalid date format
                        else:
                            items[str(value)] += 1
            
            facet_data[field_name] = {
                "display_name": facet_name,
                "items": dict(items)
            }
        
        return facet_data
    
    def _create_index_file(self, output_path: Path, entries: List[Dict], 
                          facet_data: Dict[str, Dict]):
        """Create the multi-faceted index.html file."""
        # Prepare entries for JSON
        clean_entries = []
        for entry in entries:
            clean_entry = {}
            for key, value in entry.items():
                if isinstance(value, str):
                    if key == "description":
                        # Strip HTML and limit length
                        import re
                        value = re.sub(r'<[^>]+>', '', value)
                        if len(value) > 500:
                            value = value[:500] + "..."
                    clean_entry[key] = value
                elif isinstance(value, list):
                    clean_entry[key] = [str(v) for v in value]
                else:
                    clean_entry[key] = str(value)
            clean_entries.append(clean_entry)
        
        # Use safe JSON encoding for JavaScript embedding
        entries_json = sanitize_entries_for_javascript(clean_entries)
        
        # Set up Jinja2
        template_dir = Path(__file__).parent / "templates"
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template("multi_facet_index.html")
        
        # Render template with sanitized data
        html_content = template.render(
            title=sanitize_for_html("EBK Library"),
            entries=entries,
            entries_json=entries_json,  # Already sanitized
            facets=facet_data,
            is_subdir=False
        )
        
        # Write the file
        index_path = output_path / "index.html"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    
        
        readme_path = output_path / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)