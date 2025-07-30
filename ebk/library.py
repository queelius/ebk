"""
Fluent API for ebk library management.

This module provides a comprehensive, chainable interface for working with
ebook libraries programmatically.
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Callable, Iterator, Tuple
from datetime import datetime
import re
from copy import deepcopy
from collections import defaultdict
import jmespath

from .ident import add_unique_id
from .utils import search_regex, search_jmes
from .imports.calibre import import_calibre
from .imports.ebooks import import_ebooks
from .exports.zip import export_zipfile
from .exports.jinja_export import JinjaExporter
from .merge import perform_set_operation


class QueryBuilder:
    """Fluent query builder for searching library entries."""
    
    def __init__(self, entries: List[Dict[str, Any]]):
        self._entries = entries
        self._filters = []
        self._sort_key = None
        self._sort_reverse = False
        self._limit = None
        self._offset = 0
    
    def where(self, field: str, value: Any, operator: str = "==") -> 'QueryBuilder':
        """Add a filter condition."""
        def filter_func(entry):
            entry_value = entry.get(field)
            if operator == "==":
                return entry_value == value
            elif operator == "!=":
                return entry_value != value
            elif operator == ">":
                return entry_value > value
            elif operator == ">=":
                return entry_value >= value
            elif operator == "<":
                return entry_value < value
            elif operator == "<=":
                return entry_value <= value
            elif operator == "in":
                return value in str(entry_value)
            elif operator == "contains":
                if isinstance(entry_value, list):
                    return value in entry_value
                return False
            elif operator == "regex":
                return bool(re.search(value, str(entry_value), re.IGNORECASE))
            return False
        
        self._filters.append(filter_func)
        return self
    
    def where_any(self, fields: List[str], value: str) -> 'QueryBuilder':
        """Search across multiple fields."""
        def filter_func(entry):
            search_text = value.lower()
            for field in fields:
                field_value = str(entry.get(field, "")).lower()
                if search_text in field_value:
                    return True
            return False
        
        self._filters.append(filter_func)
        return self
    
    def where_lambda(self, func: Callable[[Dict], bool]) -> 'QueryBuilder':
        """Add a custom filter function."""
        self._filters.append(func)
        return self
    
    def jmespath(self, expression: str) -> 'QueryBuilder':
        """Filter using JMESPath expression."""
        results = jmespath.search(expression, self._entries)
        if results:
            self._entries = results if isinstance(results, list) else [results]
        else:
            self._entries = []
        return self
    
    def order_by(self, field: str, descending: bool = False) -> 'QueryBuilder':
        """Set sort order."""
        self._sort_key = field
        self._sort_reverse = descending
        return self
    
    def skip(self, n: int) -> 'QueryBuilder':
        """Skip n results."""
        self._offset = n
        return self
    
    def take(self, n: int) -> 'QueryBuilder':
        """Limit results to n entries."""
        self._limit = n
        return self
    
    def execute(self) -> List[Dict[str, Any]]:
        """Execute the query and return results."""
        results = self._entries
        
        # Apply filters
        for filter_func in self._filters:
            results = [entry for entry in results if filter_func(entry)]
        
        # Apply sorting
        if self._sort_key:
            results = sorted(
                results,
                key=lambda x: x.get(self._sort_key, ""),
                reverse=self._sort_reverse
            )
        
        # Apply offset and limit
        if self._offset:
            results = results[self._offset:]
        if self._limit:
            results = results[:self._limit]
        
        return results
    
    def count(self) -> int:
        """Count matching entries."""
        return len(self.execute())
    
    def first(self) -> Optional[Dict[str, Any]]:
        """Get first matching entry."""
        results = self.take(1).execute()
        return results[0] if results else None
    
    def exists(self) -> bool:
        """Check if any matching entries exist."""
        return self.count() > 0


class Entry:
    """Fluent interface for individual library entries."""
    
    def __init__(self, data: Dict[str, Any], library: Optional['Library'] = None):
        self._data = data
        self._library = library
        self._ensure_unique_id()
    
    def _ensure_unique_id(self):
        """Ensure entry has a unique ID."""
        if 'unique_id' not in self._data:
            add_unique_id(self._data)
    
    @property
    def id(self) -> str:
        return self._data.get('unique_id', '')
    
    @property
    def title(self) -> str:
        return self._data.get('title', '')
    
    @title.setter
    def title(self, value: str):
        self._data['title'] = value
    
    @property
    def creators(self) -> List[str]:
        return self._data.get('creators', [])
    
    @creators.setter
    def creators(self, value: List[str]):
        self._data['creators'] = value
    
    @property
    def subjects(self) -> List[str]:
        return self._data.get('subjects', [])
    
    @subjects.setter
    def subjects(self, value: List[str]):
        self._data['subjects'] = value
    
    def get(self, field: str, default: Any = None) -> Any:
        """Get field value."""
        return self._data.get(field, default)
    
    def set(self, field: str, value: Any) -> 'Entry':
        """Set field value (chainable)."""
        self._data[field] = value
        return self
    
    def update(self, **kwargs) -> 'Entry':
        """Update multiple fields (chainable)."""
        self._data.update(kwargs)
        return self
    
    def add_creator(self, creator: str) -> 'Entry':
        """Add a creator (chainable)."""
        if 'creators' not in self._data:
            self._data['creators'] = []
        if creator not in self._data['creators']:
            self._data['creators'].append(creator)
        return self
    
    def add_subject(self, subject: str) -> 'Entry':
        """Add a subject (chainable)."""
        if 'subjects' not in self._data:
            self._data['subjects'] = []
        if subject not in self._data['subjects']:
            self._data['subjects'].append(subject)
        return self
    
    def add_file(self, file_path: str) -> 'Entry':
        """Add an ebook file path (chainable)."""
        if 'file_paths' not in self._data:
            self._data['file_paths'] = []
        if file_path not in self._data['file_paths']:
            self._data['file_paths'].append(file_path)
        return self
    
    def remove_file(self, file_path: str) -> 'Entry':
        """Remove an ebook file path (chainable)."""
        if 'file_paths' in self._data and file_path in self._data['file_paths']:
            self._data['file_paths'].remove(file_path)
        return self
    
    def has_file(self, file_path: str) -> bool:
        """Check if entry has a specific file."""
        return file_path in self._data.get('file_paths', [])
    
    def to_dict(self) -> Dict[str, Any]:
        """Get raw dictionary data."""
        return deepcopy(self._data)
    
    def save(self) -> 'Entry':
        """Save changes if part of a library."""
        if self._library:
            self._library.save()
        return self


class Library:
    """
    Fluent interface for ebk library operations.
    
    Example usage:
        lib = Library.open("/path/to/library")
        
        # Search and filter
        results = (lib.query()
                    .where("language", "en")
                    .where("year", 2020, ">")
                    .order_by("title")
                    .take(10)
                    .execute())
        
        # Add books
        lib.add_entry(
            title="New Book",
            creators=["Author Name"],
            subjects=["Fiction", "Adventure"]
        ).save()
        
        # Chain operations
        (lib.filter(lambda e: e.get('year', 0) > 2020)
            .tag_all("recent")
            .export_to_hugo("/path/to/hugo", organize_by="year"))
    """
    
    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        self._entries = []
        self._load()
    
    @classmethod
    def create(cls, path: Union[str, Path]) -> 'Library':
        """Create a new library."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        
        # Create empty metadata file
        metadata_file = path / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump([], f, indent=2)
        
        return cls(path)
    
    @classmethod
    def open(cls, path: Union[str, Path]) -> 'Library':
        """Open an existing library."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Library not found: {path}")
        return cls(path)
    
    @classmethod
    def from_calibre(cls, calibre_path: Union[str, Path], 
                     output_path: Union[str, Path]) -> 'Library':
        """Create library from Calibre import."""
        import_calibre(str(calibre_path), str(output_path))
        return cls(output_path)
    
    @classmethod
    def from_ebooks(cls, ebooks_path: Union[str, Path], 
                    output_path: Union[str, Path],
                    formats: Optional[List[str]] = None) -> 'Library':
        """Create library from ebook directory."""
        if formats is None:
            formats = ["pdf", "epub", "mobi", "azw3"]
        import_ebooks(str(ebooks_path), str(output_path), formats)
        return cls(output_path)
    
    def _load(self):
        """Load library metadata."""
        metadata_file = self.path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                self._entries = json.load(f)
                # Ensure all entries have unique IDs
                for entry in self._entries:
                    if 'unique_id' not in entry:
                        add_unique_id(entry)
    
    def save(self) -> 'Library':
        """Save library metadata (chainable)."""
        metadata_file = self.path / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(self._entries, f, indent=2)
        return self
    
    def __len__(self) -> int:
        """Number of entries in library."""
        return len(self._entries)
    
    def __iter__(self) -> Iterator[Entry]:
        """Iterate over entries as Entry objects."""
        for data in self._entries:
            yield Entry(data, self)
    
    def __getitem__(self, index: int) -> Entry:
        """Get entry by index."""
        return Entry(self._entries[index], self)
    
    def get_by_indices(self, indices: List[int]) -> List[Entry]:
        """Get multiple entries by indices with validation."""
        entries = []
        total = len(self)
        for index in indices:
            if index < 0 or index >= total:
                raise IndexError(f"Index {index} is out of range (0-{total - 1})")
            entries.append(self[index])
        return entries
    
    # Query methods
    
    def query(self) -> QueryBuilder:
        """Start a new query."""
        return QueryBuilder(deepcopy(self._entries))
    
    def find(self, unique_id: str) -> Optional[Entry]:
        """Find entry by unique ID."""
        for entry_data in self._entries:
            if entry_data.get('unique_id') == unique_id:
                return Entry(entry_data, self)
        return None
    
    def find_by_title(self, title: str) -> List[Entry]:
        """Find entries by exact title match."""
        results = []
        for entry_data in self._entries:
            if entry_data.get('title') == title:
                results.append(Entry(entry_data, self))
        return results
    
    def search(self, query: str, fields: Optional[List[str]] = None) -> List[Entry]:
        """Simple text search across fields."""
        if fields is None:
            fields = ['title', 'creators', 'subjects', 'description']
        
        results = []
        query_lower = query.lower()
        
        for entry_data in self._entries:
            for field in fields:
                value = entry_data.get(field, '')
                if isinstance(value, list):
                    value = ' '.join(str(v) for v in value)
                if query_lower in str(value).lower():
                    results.append(Entry(entry_data, self))
                    break
        
        return results
    
    def filter(self, predicate: Callable[[Entry], bool]) -> 'Library':
        """Filter library entries (returns new Library instance)."""
        filtered = Library.create(self.path.parent / f"{self.path.name}_filtered")
        filtered._entries = []
        
        for entry_data in self._entries:
            entry = Entry(entry_data)
            if predicate(entry):
                filtered._entries.append(deepcopy(entry_data))
        
        return filtered
    
    # Modification methods
    
    def add_entry(self, **kwargs) -> Entry:
        """Add a new entry to the library."""
        entry_data = kwargs
        add_unique_id(entry_data)
        self._entries.append(entry_data)
        return Entry(entry_data, self)
    
    def add_entries(self, entries: List[Dict[str, Any]]) -> 'Library':
        """Add multiple entries (chainable)."""
        for entry_data in entries:
            add_unique_id(entry_data)
            self._entries.append(entry_data)
        return self
    
    def remove(self, entry: Union[Entry, str]) -> 'Library':
        """Remove entry by Entry object or unique ID (chainable)."""
        if isinstance(entry, Entry):
            unique_id = entry.id
        else:
            unique_id = entry
        
        self._entries = [e for e in self._entries if e.get('unique_id') != unique_id]
        return self
    
    def remove_where(self, predicate: Callable[[Entry], bool]) -> 'Library':
        """Remove entries matching predicate (chainable)."""
        to_remove = []
        for entry_data in self._entries:
            entry = Entry(entry_data)
            if predicate(entry):
                to_remove.append(entry_data.get('unique_id'))
        
        for uid in to_remove:
            self.remove(uid)
        
        return self
    
    def update_all(self, updater: Callable[[Entry], None]) -> 'Library':
        """Update all entries using function (chainable)."""
        for entry_data in self._entries:
            entry = Entry(entry_data, self)
            updater(entry)
        return self
    
    def tag_all(self, tag: str) -> 'Library':
        """Add tag to all entries (chainable)."""
        return self.update_all(lambda e: e.add_subject(tag))
    
    def untag_all(self, tag: str) -> 'Library':
        """Remove tag from all entries (chainable)."""
        def remove_tag(entry: Entry):
            if tag in entry.subjects:
                entry.subjects.remove(tag)
        return self.update_all(remove_tag)
    
    # Merge operations
    
    def merge(self, other: 'Library', operation: str = "union") -> 'Library':
        """Merge with another library using set operations."""
        output_path = self.path.parent / f"{self.path.name}_merged"
        
        # Create temporary output
        output_path.mkdir(exist_ok=True)
        
        # Perform merge
        from .merge import merge_libraries
        merge_libraries([str(self.path), str(other.path)], str(output_path), operation)
        
        return Library(output_path)
    
    def union(self, other: 'Library') -> 'Library':
        """Union with another library."""
        return self.merge(other, "union")
    
    def intersect(self, other: 'Library') -> 'Library':
        """Intersect with another library."""
        return self.merge(other, "intersect")
    
    def difference(self, other: 'Library') -> 'Library':
        """Difference with another library."""
        return self.merge(other, "diff")
    
    # Export operations
    
    def export_to_zip(self, output_path: Union[str, Path]) -> 'Library':
        """Export to ZIP file (chainable)."""
        export_zipfile(str(self.path), str(output_path))
        return self
    
    def export_to_hugo(self, hugo_path: Union[str, Path], 
                      organize_by: str = "flat",
                      template_dir: Optional[Path] = None) -> 'Library':
        """Export to Hugo site (chainable)."""
        exporter = JinjaExporter(template_dir)
        exporter.export_hugo(str(self.path), str(hugo_path), organize_by)
        return self
    
    def export_to_symlink_dag(self, output_dir: Union[str, Path], 
                             tag_field: str = "subjects",
                             include_files: bool = True,
                             create_index: bool = True) -> 'Library':
        """Export library as navigable directory structure using symlinks."""
        from .exports.symlink_dag import export_symlink_dag
        
        export_symlink_dag(
            str(self.path), 
            str(output_dir), 
            tag_field=tag_field,
            include_files=include_files,
            create_index=create_index
        )
        return self
    
    # Statistics and analysis
    
    def stats(self) -> Dict[str, Any]:
        """Get library statistics."""
        stats = {
            'total_entries': len(self._entries),
            'total_files': sum(len(e.get('file_paths', [])) for e in self._entries),
            'languages': defaultdict(int),
            'years': defaultdict(int),
            'creators': defaultdict(int),
            'subjects': defaultdict(int),
            'formats': defaultdict(int)
        }
        
        for entry in self._entries:
            # Language stats
            lang = entry.get('language', 'unknown')
            stats['languages'][lang] += 1
            
            # Year stats
            date = entry.get('date', '')
            if date and len(date) >= 4:
                year = date[:4]
                stats['years'][year] += 1
            
            # Creator stats
            for creator in entry.get('creators', []):
                stats['creators'][creator] += 1
            
            # Subject stats
            for subject in entry.get('subjects', []):
                stats['subjects'][subject] += 1
            
            # Format stats
            for file_path in entry.get('file_paths', []):
                ext = Path(file_path).suffix.lower()
                if ext:
                    stats['formats'][ext] += 1
        
        # Convert defaultdicts to regular dicts and sort
        stats['languages'] = dict(sorted(stats['languages'].items(), 
                                       key=lambda x: x[1], reverse=True))
        stats['years'] = dict(sorted(stats['years'].items()))
        stats['creators'] = dict(sorted(stats['creators'].items(), 
                                      key=lambda x: x[1], reverse=True)[:20])
        stats['subjects'] = dict(sorted(stats['subjects'].items(), 
                                      key=lambda x: x[1], reverse=True)[:20])
        stats['formats'] = dict(sorted(stats['formats'].items(), 
                                     key=lambda x: x[1], reverse=True))
        
        return stats
    
    def group_by(self, field: str) -> Dict[str, List[Entry]]:
        """Group entries by field value."""
        groups = defaultdict(list)
        
        for entry_data in self._entries:
            entry = Entry(entry_data, self)
            value = entry.get(field)
            
            if isinstance(value, list):
                # For list fields, add to multiple groups
                for v in value:
                    groups[str(v)].append(entry)
            else:
                groups[str(value)].append(entry)
        
        return dict(groups)
    
    def duplicates(self, by: str = "title") -> List[Tuple[str, List[Entry]]]:
        """Find duplicate entries by field."""
        groups = self.group_by(by)
        duplicates = []
        
        for value, entries in groups.items():
            if len(entries) > 1:
                duplicates.append((value, entries))
        
        return duplicates
    
    # Advanced query operations
    
    def find_similar(self, entry_or_id: Union[str, Entry, dict], 
                    threshold: float = 0.7) -> List[Entry]:
        """Find entries similar to the given entry based on metadata."""
        # Get the reference entry
        if isinstance(entry_or_id, str):
            ref_entry = self.find(entry_or_id)
            if not ref_entry:
                return []
        elif isinstance(entry_or_id, Entry):
            ref_entry = entry_or_id
        else:
            ref_entry = Entry(entry_or_id)
        
        # Calculate similarity scores
        scores = []
        ref_subjects = set(ref_entry.get("subjects", []))
        ref_creators = set(ref_entry.get("creators", []))
        ref_lang = ref_entry.get("language", "")
        
        for entry_data in self._entries:
            if entry_data.get("unique_id") == ref_entry.id:
                continue  # Skip self
            
            entry = Entry(entry_data)
            score = 0.0
            weight_total = 0.0
            
            # Subject similarity (weight: 0.4)
            subjects = set(entry.get("subjects", []))
            if ref_subjects or subjects:
                subject_sim = len(ref_subjects & subjects) / len(ref_subjects | subjects)
                score += subject_sim * 0.4
                weight_total += 0.4
            
            # Creator similarity (weight: 0.3)
            creators = set(entry.get("creators", []))
            if ref_creators or creators:
                creator_sim = len(ref_creators & creators) / len(ref_creators | creators)
                score += creator_sim * 0.3
                weight_total += 0.3
            
            # Language match (weight: 0.2)
            if ref_lang:
                lang_match = 1.0 if entry.get("language") == ref_lang else 0.0
                score += lang_match * 0.2
                weight_total += 0.2
            
            # Title similarity (weight: 0.1)
            ref_title_words = set(ref_entry.title.lower().split())
            title_words = set(entry.title.lower().split())
            if ref_title_words and title_words:
                title_sim = len(ref_title_words & title_words) / len(ref_title_words | title_words)
                score += title_sim * 0.1
                weight_total += 0.1
            
            # Normalize score
            if weight_total > 0:
                score = score / weight_total
                if score >= threshold:
                    scores.append((score, entry))
        
        # Sort by score and return entries
        scores.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in scores]
    
    def recommend(self, based_on: Optional[List[str]] = None, 
                 limit: int = 10) -> List[Entry]:
        """Get book recommendations based on reading history or specific entries."""
        if not based_on:
            # Use random sampling from highly-rated or popular entries
            candidates = self.query().where_lambda(
                lambda e: e.get("rating", 0) >= 4 or len(e.get("subjects", [])) > 3
            ).execute()
            
            import random
            return [Entry(e) for e in random.sample(candidates, min(limit, len(candidates)))]
        
        # Find similar books to the given entries
        all_similar = []
        seen_ids = set(based_on)
        
        for entry_id in based_on:
            similar = self.find_similar(entry_id, threshold=0.5)
            for entry in similar:
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    all_similar.append(entry)
        
        # Sort by relevance (could be enhanced with scoring)
        return all_similar[:limit]
    
    def analyze_reading_patterns(self) -> dict:
        """Analyze patterns in the library (genres, authors, languages, etc.)."""
        stats = self.stats()
        
        # Additional analysis
        analysis = {
            "basic_stats": stats,
            "reading_diversity": {}
        }
        
        # Genre diversity (using subjects)
        subjects = stats["subjects"]
        if subjects:
            total_subject_mentions = sum(subjects.values())
            top_subjects = sorted(subjects.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Calculate entropy as diversity measure
            import math
            entropy = 0
            for count in subjects.values():
                p = count / total_subject_mentions
                if p > 0:
                    entropy -= p * math.log2(p)
            
            analysis["reading_diversity"]["subject_entropy"] = entropy
            analysis["reading_diversity"]["subject_concentration"] = {
                subject: count / total_subject_mentions 
                for subject, count in top_subjects
            }
        
        # Author diversity
        creators = stats["creators"]
        if creators:
            unique_authors = len(creators)
            total_books = stats["total_entries"]
            analysis["reading_diversity"]["authors_per_book"] = unique_authors / total_books
            analysis["reading_diversity"]["books_per_author"] = total_books / unique_authors
        
        # Time-based analysis
        years = defaultdict(int)
        for entry in self._entries:
            year = entry.get("year") or entry.get("date", "")[:4]
            if year and year.isdigit():
                years[int(year)] += 1
        
        if years:
            analysis["temporal_distribution"] = {
                "years": dict(sorted(years.items())),
                "newest_year": max(years.keys()),
                "oldest_year": min(years.keys()),
                "year_range": max(years.keys()) - min(years.keys())
            }
        
        return analysis
    
    def export_graph(self, output_file: Union[str, Path], 
                    graph_type: str = "coauthor",
                    min_connections: int = 1) -> 'Library':
        """Export library as a graph (GraphML, GEXF, or JSON)."""
        import networkx as nx
        
        G = nx.Graph()
        
        if graph_type == "coauthor":
            # Build co-authorship network
            for i, entry in enumerate(self._entries):
                creators = entry.get("creators", [])
                # Add book node
                G.add_node(f"book_{i}", 
                          type="book", 
                          title=entry.get("title", "Unknown"),
                          id=entry.get("unique_id"))
                
                # Add author nodes and edges
                for creator in creators:
                    if not G.has_node(creator):
                        G.add_node(creator, type="author")
                    G.add_edge(f"book_{i}", creator)
            
            # Create co-author edges
            authors = [n for n, d in G.nodes(data=True) if d.get("type") == "author"]
            for book_node in [n for n, d in G.nodes(data=True) if d.get("type") == "book"]:
                book_authors = list(G.neighbors(book_node))
                for i, author1 in enumerate(book_authors):
                    for author2 in book_authors[i+1:]:
                        if G.has_edge(author1, author2):
                            G[author1][author2]["weight"] += 1
                        else:
                            G.add_edge(author1, author2, weight=1)
        
        elif graph_type == "subject":
            # Build subject co-occurrence network
            for i, entry in enumerate(self._entries):
                subjects = entry.get("subjects", [])
                # Add book node
                G.add_node(f"book_{i}", 
                          type="book", 
                          title=entry.get("title", "Unknown"),
                          id=entry.get("unique_id"))
                
                # Add subject nodes and edges
                for subject in subjects:
                    if not G.has_node(subject):
                        G.add_node(subject, type="subject")
                    G.add_edge(f"book_{i}", subject)
            
            # Create subject co-occurrence edges
            subjects = [n for n, d in G.nodes(data=True) if d.get("type") == "subject"]
            for book_node in [n for n, d in G.nodes(data=True) if d.get("type") == "book"]:
                book_subjects = list(G.neighbors(book_node))
                for i, subj1 in enumerate(book_subjects):
                    for subj2 in book_subjects[i+1:]:
                        if G.has_edge(subj1, subj2):
                            G[subj1][subj2]["weight"] += 1
                        else:
                            G.add_edge(subj1, subj2, weight=1)
        
        # Filter edges by minimum connections
        if min_connections > 1:
            edges_to_remove = [(u, v) for u, v, d in G.edges(data=True) 
                              if d.get("weight", 1) < min_connections]
            G.remove_edges_from(edges_to_remove)
        
        # Export based on file extension
        output_path = Path(output_file)
        if output_path.suffix == ".graphml":
            nx.write_graphml(G, str(output_file))
        elif output_path.suffix == ".gexf":
            nx.write_gexf(G, str(output_file))
        else:
            # Default to JSON
            from networkx.readwrite import json_graph
            data = json_graph.node_link_data(G)
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
        
        return self
    
    # Batch operations
    
    def batch(self) -> 'BatchOperations':
        """Start batch operations."""
        return BatchOperations(self)
    
    def transaction(self) -> 'Transaction':
        """Start a transaction."""
        return Transaction(self)


class BatchOperations:
    """Batch operations on library."""
    
    def __init__(self, library: Library):
        self._library = library
        self._operations = []
    
    def add_entry(self, **kwargs) -> 'BatchOperations':
        """Queue entry addition."""
        self._operations.append(('add', kwargs))
        return self
    
    def remove(self, unique_id: str) -> 'BatchOperations':
        """Queue entry removal."""
        self._operations.append(('remove', unique_id))
        return self
    
    def update(self, unique_id: str, **kwargs) -> 'BatchOperations':
        """Queue entry update."""
        self._operations.append(('update', unique_id, kwargs))
        return self
    
    def execute(self) -> Library:
        """Execute all queued operations."""
        for op in self._operations:
            if op[0] == 'add':
                self._library.add_entry(**op[1])
            elif op[0] == 'remove':
                self._library.remove(op[1])
            elif op[0] == 'update':
                entry = self._library.find(op[1])
                if entry:
                    entry.update(**op[2])
        
        return self._library.save()


class Transaction:
    """Transaction support for library operations."""
    
    def __init__(self, library: Library):
        self._library = library
        self._original_entries = deepcopy(library._entries)
        self._committed = False
    
    def __enter__(self):
        return self._library
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Rollback on exception
            self._library._entries = self._original_entries
        else:
            # Commit on success
            self._library.save()
        return False
    
    def rollback(self):
        """Manually rollback changes."""
        self._library._entries = self._original_entries
    
    def commit(self):
        """Manually commit changes."""
        self._library.save()
        self._committed = True