"""
Flexible Jinja2-based export system for ebk libraries.

This module provides a template-driven approach to exporting ebook metadata
in various formats, with Hugo as the primary implementation.
"""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from jinja2 import Environment, FileSystemLoader, select_autoescape
import logging
from slugify import slugify
from collections import defaultdict

logger = logging.getLogger(__name__)


class JinjaExporter:
    """Flexible export system using Jinja2 templates."""
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize the exporter with a template directory.
        
        Args:
            template_dir: Path to custom templates. If None, uses built-in templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['slugify'] = slugify
        self.env.filters['join_list'] = lambda x: ', '.join(x) if isinstance(x, list) else x
        self.env.filters['default_if_none'] = lambda x, default='': x if x is not None else default
    
    def export_hugo(self, lib_dir: str, hugo_dir: str, 
                    organize_by: str = "flat",
                    create_indexes: bool = True,
                    copy_files: bool = True):
        """
        Export library to Hugo with flexible organization options.
        
        Args:
            lib_dir: Path to ebk library
            hugo_dir: Path to Hugo site directory
            organize_by: Organization method - "flat", "year", "language", "subject", "creator"
            create_indexes: Whether to create index pages for categories
            copy_files: Whether to copy ebook and cover files
        """
        lib_path = Path(lib_dir)
        hugo_path = Path(hugo_dir)
        
        # Load metadata
        with open(lib_path / "metadata.json", "r") as f:
            books = json.load(f)
        
        # Prepare books with normalized fields
        books = self._normalize_metadata(books)
        
        # Create directory structure
        content_dir = hugo_path / "content" / "library"
        static_dir = hugo_path / "static" / "ebooks"
        content_dir.mkdir(parents=True, exist_ok=True)
        static_dir.mkdir(parents=True, exist_ok=True)
        
        # Group books by organization method
        grouped_books = self._group_books(books, organize_by)
        
        # Export individual book pages
        for group_key, group_books in grouped_books.items():
            group_dir = content_dir / group_key if organize_by != "flat" else content_dir
            group_dir.mkdir(parents=True, exist_ok=True)
            
            for book in group_books:
                self._export_book(book, group_dir, static_dir, lib_path, copy_files)
        
        # Create index pages
        if create_indexes:
            self._create_indexes(grouped_books, content_dir, organize_by)
        
        # Create main library index
        self._create_main_index(books, content_dir, organize_by)
        
        logger.info(f"Exported {len(books)} books to Hugo site at '{hugo_dir}'")
    
    def _normalize_metadata(self, books: List[Dict]) -> List[Dict]:
        """Normalize metadata fields for consistent access."""
        normalized = []
        
        for book in books:
            # Create a normalized version with consistent field names
            norm = {
                'title': book.get('title', 'Unknown Title'),
                'creators': book.get('creators', []),
                'subjects': book.get('subjects', []),
                'description': book.get('description', ''),
                'language': book.get('language', 'en'),
                'date': book.get('date', ''),
                'publisher': book.get('publisher', ''),
                'identifiers': book.get('identifiers', {}),
                'file_paths': book.get('file_paths', []),
                'cover_path': book.get('cover_path', ''),
                'unique_id': book.get('unique_id', ''),
                # Keep original data for backward compatibility
                '_original': book
            }
            
            # Extract year from date if available
            if norm['date']:
                try:
                    norm['year'] = norm['date'][:4]
                except (IndexError, TypeError, AttributeError):
                    norm['year'] = ''  # Invalid date format
            else:
                norm['year'] = ''
            
            # Generate slug
            norm['slug'] = slugify(f"{norm['title']}-{norm['unique_id'][:8]}")
            
            normalized.append(norm)
        
        return normalized
    
    def _group_books(self, books: List[Dict], organize_by: str) -> Dict[str, List[Dict]]:
        """Group books by specified organization method."""
        grouped = defaultdict(list)
        
        if organize_by == "flat":
            grouped[""] = books
        elif organize_by == "year":
            for book in books:
                year = book.get('year', 'unknown-year')
                grouped[year].append(book)
        elif organize_by == "language":
            for book in books:
                lang = book.get('language', 'unknown-language')
                grouped[lang].append(book)
        elif organize_by == "subject":
            for book in books:
                subjects = book.get('subjects', ['uncategorized'])
                for subject in subjects:
                    grouped[slugify(subject)].append(book)
        elif organize_by == "creator":
            for book in books:
                creators = book.get('creators', ['unknown-creator'])
                for creator in creators:
                    grouped[slugify(creator)].append(book)
        else:
            # Default to flat
            grouped[""] = books
        
        return dict(grouped)
    
    def _export_book(self, book: Dict, output_dir: Path, static_dir: Path, 
                     lib_path: Path, copy_files: bool):
        """Export a single book."""
        # Load book template
        template = self.env.get_template('hugo/book.md')
        
        # Prepare file paths for Hugo
        ebook_urls = []
        if book['file_paths']:
            for file_path in book['file_paths']:
                if copy_files and file_path:
                    src = lib_path / file_path
                    if src.exists():
                        dst = static_dir / src.name
                        shutil.copy2(src, dst)
                        ebook_urls.append(f"/ebooks/{src.name}")
        
        cover_url = ""
        if book['cover_path'] and copy_files:
            src = lib_path / book['cover_path']
            if src.exists():
                dst = static_dir / src.name
                shutil.copy2(src, dst)
                cover_url = f"/ebooks/{src.name}"
        
        # Render template
        content = template.render(
            book=book,
            ebook_urls=ebook_urls,
            cover_url=cover_url
        )
        
        # Write file
        output_file = output_dir / f"{book['slug']}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _create_indexes(self, grouped_books: Dict[str, List[Dict]], 
                       content_dir: Path, organize_by: str):
        """Create index pages for each group."""
        if organize_by == "flat":
            return
        
        template = self.env.get_template('hugo/index.md')
        
        for group_key, books in grouped_books.items():
            if not group_key:  # Skip empty group
                continue
                
            group_dir = content_dir / group_key
            index_file = group_dir / "_index.md"
            
            # Determine group title
            if organize_by == "year":
                group_title = f"Books from {group_key}"
            elif organize_by == "language":
                group_title = f"Books in {group_key}"
            elif organize_by == "subject":
                group_title = f"Subject: {group_key.replace('-', ' ').title()}"
            elif organize_by == "creator":
                group_title = f"Books by {group_key.replace('-', ' ').title()}"
            else:
                group_title = group_key.replace('-', ' ').title()
            
            content = template.render(
                title=group_title,
                organize_by=organize_by,
                group_key=group_key,
                books=books,
                book_count=len(books)
            )
            
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(content)
    
    def _create_main_index(self, books: List[Dict], content_dir: Path, organize_by: str):
        """Create main library index page."""
        template = self.env.get_template('hugo/library.md')
        
        # Calculate statistics
        stats = {
            'total_books': len(books),
            'total_creators': len(set(creator for book in books for creator in book.get('creators', []))),
            'total_subjects': len(set(subject for book in books for subject in book.get('subjects', []))),
            'languages': defaultdict(int),
            'years': defaultdict(int),
            'top_creators': defaultdict(int),
            'top_subjects': defaultdict(int)
        }
        
        for book in books:
            # Language stats
            lang = book.get('language', 'unknown')
            stats['languages'][lang] += 1
            
            # Year stats
            year = book.get('year', 'unknown')
            if year:
                stats['years'][year] += 1
            
            # Creator stats
            for creator in book.get('creators', []):
                stats['top_creators'][creator] += 1
            
            # Subject stats
            for subject in book.get('subjects', []):
                stats['top_subjects'][subject] += 1
        
        # Sort and limit top items
        stats['top_creators'] = sorted(stats['top_creators'].items(), 
                                     key=lambda x: x[1], reverse=True)[:10]
        stats['top_subjects'] = sorted(stats['top_subjects'].items(), 
                                     key=lambda x: x[1], reverse=True)[:10]
        
        content = template.render(
            title="Library",
            books=books,
            stats=stats,
            organize_by=organize_by
        )
        
        index_file = content_dir / "_index.md"
        with open(index_file, 'w', encoding='utf-8') as f:
            f.write(content)