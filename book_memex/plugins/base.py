"""
Base classes for the EBK plugin system.

This module defines abstract base classes that all plugins must inherit from.
Each plugin type has specific methods that must be implemented.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TagSuggestion:
    """Represents a suggested tag with confidence score."""
    tag: str
    confidence: float
    source: str  # Which plugin suggested it
    reason: Optional[str] = None  # Why this tag was suggested


@dataclass
class ContentAnalysis:
    """Results from content analysis."""
    reading_time: Optional[int] = None  # minutes
    difficulty_level: Optional[str] = None  # easy/medium/hard
    word_count: Optional[int] = None
    page_count: Optional[int] = None
    language: Optional[str] = None
    summary: Optional[str] = None
    key_topics: List[str] = None
    sentiment: Optional[float] = None  # -1 to 1
    quality_score: Optional[float] = None  # 0 to 1

    def __post_init__(self):
        if self.key_topics is None:
            self.key_topics = []


@dataclass
class DuplicateGroup:
    """Group of duplicate entries."""
    entries: List[Dict[str, Any]]
    similarity_score: float
    match_reason: str  # "isbn", "title_author", "content_hash", etc.


@dataclass
class ValidationResult:
    """Result of entry validation."""
    is_valid: bool
    errors: List['ValidationError']
    warnings: List['ValidationWarning']
    completeness_score: float  # 0 to 1


@dataclass
class ValidationError:
    """Validation error details."""
    field: str
    message: str
    severity: str  # "error", "warning", "info"


@dataclass
class ValidationWarning:
    """Validation warning details."""
    field: str
    message: str


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    output_path: str
    entries_exported: int
    errors: List[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class Plugin(ABC):
    """Base class for all EBK plugins."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this plugin."""
        pass
    
    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass
    
    @property
    def description(self) -> str:
        """Plugin description."""
        return ""
    
    @property
    def author(self) -> str:
        """Plugin author."""
        return ""
    
    @property
    def requires(self) -> List[str]:
        """List of required dependencies."""
        return []
    
    def initialize(self, config: Dict[str, Any] = None) -> None:
        """
        Initialize the plugin with configuration.
        
        Args:
            config: Plugin-specific configuration
        """
        self.config = config or {}
    
    def cleanup(self) -> None:
        """Cleanup resources used by the plugin."""
        pass
    
    def validate_config(self) -> bool:
        """
        Validate plugin configuration.
        
        Returns:
            True if configuration is valid
        """
        return True


class MetadataExtractor(Plugin):
    """Base class for metadata extraction plugins."""
    
    @abstractmethod
    async def extract(self, 
                     file_path: Optional[str] = None,
                     url: Optional[str] = None,
                     isbn: Optional[str] = None,
                     content: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Extract metadata from various sources.
        
        Args:
            file_path: Path to file to extract from
            url: URL to fetch metadata from
            isbn: ISBN to lookup
            content: Raw content bytes
            
        Returns:
            Dictionary with metadata fields like:
            - title, creators, subjects, description
            - publisher, date, language
            - isbn, doi, other identifiers
            - cover_url, thumbnail_url
        """
        pass
    
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported file formats."""
        pass
    
    def can_extract(self, source: str) -> bool:
        """
        Check if this extractor can handle the given source.
        
        Args:
            source: File path, URL, or identifier
            
        Returns:
            True if this extractor can handle the source
        """
        if not source:
            return False
        
        # Check file extension
        if Path(source).suffix.lower()[1:] in self.supported_formats():
            return True
        
        # Check if it's an ISBN
        if source.replace('-', '').replace(' ', '').isdigit() and len(source) in [10, 13]:
            return 'isbn' in self.supported_formats()
        
        # Check if it's a URL
        if source.startswith(('http://', 'https://')):
            return 'url' in self.supported_formats()
        
        return False


class TagSuggester(Plugin):
    """Base class for tag suggestion plugins."""
    
    @abstractmethod
    async def suggest_tags(self, 
                          entry: Dict[str, Any],
                          max_tags: int = 10,
                          confidence_threshold: float = 0.5) -> List[TagSuggestion]:
        """
        Suggest tags for an entry.
        
        Args:
            entry: Entry dictionary with metadata
            max_tags: Maximum number of tags to suggest
            confidence_threshold: Minimum confidence score
            
        Returns:
            List of TagSuggestion objects with tag and confidence score
        """
        pass
    
    @abstractmethod
    def requires_content(self) -> bool:
        """Whether this suggester needs file content."""
        pass
    
    def filter_suggestions(self, 
                          suggestions: List[TagSuggestion],
                          max_tags: int,
                          confidence_threshold: float) -> List[TagSuggestion]:
        """
        Filter suggestions by confidence and limit.
        
        Args:
            suggestions: List of suggestions to filter
            max_tags: Maximum number of tags
            confidence_threshold: Minimum confidence
            
        Returns:
            Filtered list of suggestions
        """
        # Filter by confidence
        filtered = [s for s in suggestions if s.confidence >= confidence_threshold]
        
        # Sort by confidence (descending)
        filtered.sort(key=lambda s: s.confidence, reverse=True)
        
        # Limit to max_tags
        return filtered[:max_tags]


class ContentAnalyzer(Plugin):
    """Base class for content analysis plugins."""
    
    @abstractmethod
    async def analyze(self, entry: Dict[str, Any]) -> ContentAnalysis:
        """
        Analyze entry content.
        
        Args:
            entry: Entry dictionary with metadata and content
            
        Returns:
            ContentAnalysis object with analysis results
        """
        pass
    
    def estimate_reading_time(self, word_count: int, wpm: int = 250) -> int:
        """
        Estimate reading time in minutes.
        
        Args:
            word_count: Number of words
            wpm: Words per minute (default 250)
            
        Returns:
            Estimated reading time in minutes
        """
        return max(1, round(word_count / wpm))


class SimilarityFinder(Plugin):
    """Base class for finding similar entries."""
    
    @abstractmethod
    def find_similar(self,
                    entry: Dict[str, Any],
                    candidates: List[Dict[str, Any]],
                    threshold: float = 0.8,
                    limit: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find entries similar to a given entry.
        
        Args:
            entry: Entry to find similar entries for
            candidates: List of candidate entries
            threshold: Minimum similarity score (0-1)
            limit: Maximum number of similar entries
            
        Returns:
            List of (entry, similarity_score) tuples
        """
        pass
    
    @abstractmethod
    def compute_similarity(self,
                          entry1: Dict[str, Any],
                          entry2: Dict[str, Any]) -> float:
        """
        Compute similarity between two entries.
        
        Args:
            entry1: First entry
            entry2: Second entry
            
        Returns:
            Similarity score between 0 and 1
        """
        pass


class Deduplicator(Plugin):
    """Base class for deduplication plugins."""
    
    @abstractmethod
    def find_duplicates(self, 
                       entries: List[Dict[str, Any]],
                       threshold: float = 0.9) -> List[DuplicateGroup]:
        """
        Find duplicate entries.
        
        Args:
            entries: List of entries to check
            threshold: Similarity threshold for duplicates
            
        Returns:
            List of DuplicateGroup objects
        """
        pass
    
    @abstractmethod
    def merge_duplicates(self, 
                        duplicates: DuplicateGroup,
                        strategy: str = "newest") -> Dict[str, Any]:
        """
        Merge duplicate entries into one.
        
        Args:
            duplicates: Group of duplicate entries
            strategy: Merge strategy ("newest", "oldest", "most_complete")
            
        Returns:
            Merged entry
        """
        pass
    
    def calculate_completeness(self, entry: Dict[str, Any]) -> float:
        """
        Calculate completeness score for an entry.
        
        Args:
            entry: Entry to evaluate
            
        Returns:
            Completeness score between 0 and 1
        """
        required_fields = ['title', 'creators', 'date', 'language', 'subjects']
        optional_fields = ['description', 'publisher', 'isbn', 'cover_path']
        
        # Required fields worth 70% of score
        required_score = sum(1 for f in required_fields if entry.get(f)) / len(required_fields) * 0.7
        
        # Optional fields worth 30% of score
        optional_score = sum(1 for f in optional_fields if entry.get(f)) / len(optional_fields) * 0.3
        
        return required_score + optional_score


class Validator(Plugin):
    """Base class for validation plugins."""
    
    @abstractmethod
    def validate(self, entry: Dict[str, Any]) -> ValidationResult:
        """
        Validate an entry.
        
        Args:
            entry: Entry to validate
            
        Returns:
            ValidationResult with errors and warnings
        """
        pass
    
    def check_required_fields(self, entry: Dict[str, Any]) -> List[ValidationError]:
        """
        Check for required fields.
        
        Args:
            entry: Entry to check
            
        Returns:
            List of validation errors
        """
        errors = []
        required = ['title', 'unique_id']
        
        for field in required:
            if not entry.get(field):
                errors.append(ValidationError(
                    field=field,
                    message=f"Required field '{field}' is missing",
                    severity="error"
                ))
        
        return errors
    
    def check_field_types(self, entry: Dict[str, Any]) -> List[ValidationError]:
        """
        Check field types.
        
        Args:
            entry: Entry to check
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Define expected types
        field_types = {
            'title': str,
            'creators': list,
            'subjects': list,
            'date': str,
            'language': str,
            'page_count': int,
            'rating': (int, float)
        }
        
        for field, expected_type in field_types.items():
            if field in entry and entry[field] is not None:
                if not isinstance(entry[field], expected_type):
                    errors.append(ValidationError(
                        field=field,
                        message=f"Field '{field}' should be {expected_type.__name__}",
                        severity="error"
                    ))
        
        return errors


class Exporter(Plugin):
    """Base class for export plugins."""
    
    @abstractmethod
    async def export(self,
                    entries: List[Dict[str, Any]],
                    output_path: str,
                    options: Dict[str, Any] = None) -> ExportResult:
        """
        Export entries to a specific format.
        
        Args:
            entries: List of entries to export
            output_path: Output file or directory path
            options: Export options
            
        Returns:
            ExportResult with status and details
        """
        pass
    
    @abstractmethod
    def supported_formats(self) -> List[str]:
        """Return list of supported export formats."""
        pass
    
    def validate_entries(self, entries: List[Dict[str, Any]]) -> List[str]:
        """
        Validate entries before export.
        
        Args:
            entries: Entries to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        if not entries:
            errors.append("No entries to export")
            return errors
        
        for i, entry in enumerate(entries):
            if not entry.get('unique_id'):
                errors.append(f"Entry {i} missing unique_id")
            if not entry.get('title'):
                errors.append(f"Entry {i} missing title")
        
        return errors