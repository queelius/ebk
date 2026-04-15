"""Book similarity system.

This module provides a flexible system for computing similarity between books
using multiple features (content, metadata, etc.).

Basic usage:
    >>> from book_memex.similarity import BookSimilarity
    >>>
    >>> # Configure similarity
    >>> sim = BookSimilarity().balanced()
    >>>
    >>> # Fit on corpus for performance
    >>> sim.fit(all_books)
    >>>
    >>> # Find similar books
    >>> similar = sim.find_similar(my_book, all_books, top_k=10)

Advanced usage:
    >>> # Custom configuration
    >>> sim = (BookSimilarity()
    ...     .content(weight=4.0)
    ...     .authors(weight=2.0, metric=CustomMetric())
    ...     .temporal(weight=1.0, sigma=5.0))
    >>>
    >>> # Compute similarity matrix for batch processing
    >>> matrix = sim.similarity_matrix(books)
    >>>
    >>> # Save/load fitted state
    >>> sim.save(Path("cache/similarity"))
    >>> sim.load(Path("cache/similarity"))
"""

from book_memex.similarity.base import Extractor, Feature, Metric
from book_memex.similarity.core import BookSimilarity
from book_memex.similarity.extractors import (
    AuthorsExtractor,
    ContentExtractor,
    DescriptionExtractor,
    LanguageExtractor,
    PageCountExtractor,
    PublicationYearExtractor,
    PublisherExtractor,
    SubjectsExtractor,
)
from book_memex.similarity.metrics import (
    CosineMetric,
    ExactMatchMetric,
    JaccardMetric,
    NumericProximityMetric,
    TemporalDecayMetric,
    TfidfMetric,
)

__all__ = [
    # Core
    "BookSimilarity",
    # Base classes
    "Extractor",
    "Metric",
    "Feature",
    # Extractors
    "ContentExtractor",
    "DescriptionExtractor",
    "AuthorsExtractor",
    "SubjectsExtractor",
    "PublicationYearExtractor",
    "LanguageExtractor",
    "PublisherExtractor",
    "PageCountExtractor",
    # Metrics
    "TfidfMetric",
    "CosineMetric",
    "JaccardMetric",
    "ExactMatchMetric",
    "TemporalDecayMetric",
    "NumericProximityMetric",
]
