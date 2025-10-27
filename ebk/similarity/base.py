"""Base classes for the similarity system.

This module defines the core abstractions:
- Extractor: Extracts values from books
- Metric: Computes similarity between values
- Feature: Combines an extractor and a metric
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generic, TypeVar

from ebk.db.models import Book

T = TypeVar("T")


class Extractor(ABC, Generic[T]):
    """Extracts a value from a book for similarity comparison.

    Examples:
        - ContentExtractor: Extracts full text
        - AuthorsExtractor: Extracts set of author names
        - SubjectsExtractor: Extracts set of subjects
        - PublicationYearExtractor: Extracts publication year
    """

    @abstractmethod
    def extract(self, book: Book) -> T:
        """Extract a value from the book.

        Args:
            book: Book to extract value from

        Returns:
            Extracted value (type depends on extractor)
        """
        pass


class Metric(ABC, Generic[T]):
    """Computes similarity between two values.

    All similarity scores must be normalized to [0, 1] where:
    - 0 = completely dissimilar
    - 1 = identical

    Examples:
        - TfidfMetric: Computes cosine similarity of TF-IDF vectors
        - JaccardMetric: Computes set overlap
        - ExactMatchMetric: Returns 1 if equal, 0 otherwise
        - TemporalDecayMetric: Gaussian decay based on time difference
    """

    @abstractmethod
    def similarity(self, value1: T, value2: T) -> float:
        """Compute similarity between two values.

        Args:
            value1: First value
            value2: Second value

        Returns:
            Similarity score in [0, 1]
        """
        pass

    def fit(self, data: Dict[int, T]) -> None:
        """Fit metric on a corpus (optional).

        Override this for metrics that need pre-computation, such as:
        - TF-IDF: Fit vectorizer and cache vectors
        - Embeddings: Compute and cache embeddings

        Default implementation is no-op for metrics that don't need fitting
        (e.g., Jaccard, exact match, temporal decay).

        Args:
            data: Dictionary mapping book IDs to extracted values
        """
        pass  # No-op by default

    def save(self, path: Path) -> None:
        """Save fitted state to disk (optional).

        Override this for metrics that cache expensive computations.
        Default implementation is no-op.

        Args:
            path: Path to save fitted state
        """
        pass  # No-op by default

    def load(self, path: Path) -> None:
        """Load fitted state from disk (optional).

        Override this for metrics that cache expensive computations.
        Default implementation is no-op.

        Args:
            path: Path to load fitted state from
        """
        pass  # No-op by default


class Feature:
    """Combines an extractor and a metric with a weight.

    A Feature represents one aspect of book similarity, such as:
    - Content similarity (text + TF-IDF)
    - Author overlap (authors + Jaccard)
    - Temporal proximity (pub year + Gaussian decay)

    Attributes:
        extractor: Extractor for getting values from books
        metric: Metric for computing similarity between values
        weight: Weight for this feature (default 1.0)
        name: Optional name for this feature
    """

    def __init__(
        self,
        extractor: Extractor,
        metric: Metric,
        weight: float = 1.0,
        name: str = None,
    ):
        """Initialize a feature.

        Args:
            extractor: Extractor for getting values from books
            metric: Metric for computing similarity between values
            weight: Weight for this feature (default 1.0)
            name: Optional name for this feature
        """
        self.extractor = extractor
        self.metric = metric
        self.weight = weight
        self.name = name or f"{extractor.__class__.__name__}+{metric.__class__.__name__}"

    def similarity(self, book1: Book, book2: Book) -> float:
        """Compute weighted similarity between two books.

        Args:
            book1: First book
            book2: Second book

        Returns:
            Weighted similarity score
        """
        value1 = self.extractor.extract(book1)
        value2 = self.extractor.extract(book2)
        sim = self.metric.similarity(value1, value2)
        return sim * self.weight
