"""Core BookSimilarity class with fluent API."""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ebk.db.models import Book
from ebk.similarity.base import Feature, Metric
from ebk.similarity.extractors import (
    AuthorsExtractor,
    ContentExtractor,
    DescriptionExtractor,
    LanguageExtractor,
    PageCountExtractor,
    PublicationYearExtractor,
    PublisherExtractor,
    SubjectsExtractor,
)
from ebk.similarity.metrics import (
    CosineMetric,
    ExactMatchMetric,
    JaccardMetric,
    NumericProximityMetric,
    TemporalDecayMetric,
    TfidfMetric,
)


class BookSimilarity:
    """Compute similarity between books using multiple features.

    This class uses a fluent API for configuration:

    Example:
        >>> sim = (BookSimilarity()
        ...     .content(weight=4.0)
        ...     .authors(weight=2.0)
        ...     .subjects(weight=1.0)
        ...     .temporal(weight=0.5))
        >>> sim.fit(books)
        >>> score = sim.similarity(book1, book2)

    Each method adds a feature (extractor + metric + weight) to the similarity
    computation. The final similarity is the weighted average of all features.

    Three-tier API:
    - Tier 1: Presets (.balanced(), .content_only())
    - Tier 2: Semantic methods (.content(), .authors()) with defaults
    - Tier 3: Escape hatch (.custom()) for power users
    """

    def __init__(self):
        """Initialize empty similarity configuration."""
        self.features: List[Feature] = []
        self._fitted = False

    # ===== Tier 1: Presets =====

    def balanced(self) -> "BookSimilarity":
        """Balanced preset with reasonable defaults.

        Weights:
        - Content (TF-IDF): 4.0
        - Authors (Jaccard): 2.0
        - Subjects (Jaccard): 1.0
        - Temporal (Gaussian): 0.5

        Returns:
            Self for chaining
        """
        return (
            self.content(weight=4.0)
            .authors(weight=2.0)
            .subjects(weight=1.0)
            .temporal(weight=0.5)
        )

    def content_only(self, metric: Optional[Metric] = None) -> "BookSimilarity":
        """Content-only preset (pure semantic similarity).

        Uses TF-IDF by default, but can override metric.

        Args:
            metric: Optional custom metric (default TfidfMetric)

        Returns:
            Self for chaining
        """
        return self.content(weight=1.0, metric=metric)

    def metadata_only(self) -> "BookSimilarity":
        """Metadata-only preset (no content similarity).

        Weights:
        - Authors (Jaccard): 3.0
        - Subjects (Jaccard): 2.0
        - Temporal (Gaussian): 1.0
        - Language (Exact): 1.0
        - Publisher (Exact): 0.5

        Returns:
            Self for chaining
        """
        return (
            self.authors(weight=3.0)
            .subjects(weight=2.0)
            .temporal(weight=1.0)
            .language(weight=1.0)
            .publisher(weight=0.5)
        )

    # ===== Tier 2: Semantic Methods =====

    def content(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add content similarity (full text).

        Default metric: TfidfMetric (cosine similarity of TF-IDF vectors)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default TfidfMetric)

        Returns:
            Self for chaining
        """
        metric = metric or TfidfMetric()
        extractor = ContentExtractor()
        self.features.append(Feature(extractor, metric, weight, "content"))
        return self

    def description(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add description similarity (book summary/blurb).

        Default metric: TfidfMetric (delegates to content provider)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default TfidfMetric)

        Returns:
            Self for chaining
        """
        metric = metric or TfidfMetric()
        extractor = DescriptionExtractor()
        self.features.append(Feature(extractor, metric, weight, "description"))
        return self

    def authors(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add author overlap similarity.

        Default metric: JaccardMetric (set overlap)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default JaccardMetric)

        Returns:
            Self for chaining
        """
        metric = metric or JaccardMetric()
        extractor = AuthorsExtractor()
        self.features.append(Feature(extractor, metric, weight, "authors"))
        return self

    def subjects(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add subject/tag overlap similarity.

        Default metric: JaccardMetric (set overlap)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default JaccardMetric)

        Returns:
            Self for chaining
        """
        metric = metric or JaccardMetric()
        extractor = SubjectsExtractor()
        self.features.append(Feature(extractor, metric, weight, "subjects"))
        return self

    def temporal(
        self, weight: float = 1.0, metric: Optional[Metric] = None, sigma: float = 10.0
    ) -> "BookSimilarity":
        """Add temporal proximity similarity (publication date).

        Default metric: TemporalDecayMetric (Gaussian decay)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default TemporalDecayMetric)
            sigma: Standard deviation in years for Gaussian decay (default 10.0)

        Returns:
            Self for chaining
        """
        metric = metric or TemporalDecayMetric(sigma=sigma)
        extractor = PublicationYearExtractor()
        self.features.append(Feature(extractor, metric, weight, "temporal"))
        return self

    def language(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add language match similarity.

        Default metric: ExactMatchMetric (1 if same language, 0 otherwise)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default ExactMatchMetric)

        Returns:
            Self for chaining
        """
        metric = metric or ExactMatchMetric()
        extractor = LanguageExtractor()
        self.features.append(Feature(extractor, metric, weight, "language"))
        return self

    def publisher(
        self, weight: float = 1.0, metric: Optional[Metric] = None
    ) -> "BookSimilarity":
        """Add publisher match similarity.

        Default metric: ExactMatchMetric (1 if same publisher, 0 otherwise)

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default ExactMatchMetric)

        Returns:
            Self for chaining
        """
        metric = metric or ExactMatchMetric()
        extractor = PublisherExtractor()
        self.features.append(Feature(extractor, metric, weight, "publisher"))
        return self

    def page_count(
        self,
        weight: float = 1.0,
        metric: Optional[Metric] = None,
        max_diff: float = 1000.0,
    ) -> "BookSimilarity":
        """Add page count proximity similarity.

        Default metric: NumericProximityMetric

        Args:
            weight: Weight for this feature (default 1.0)
            metric: Optional custom metric (default NumericProximityMetric)
            max_diff: Maximum expected difference in pages (default 1000)

        Returns:
            Self for chaining
        """
        metric = metric or NumericProximityMetric(max_diff=max_diff)
        extractor = PageCountExtractor()
        self.features.append(Feature(extractor, metric, weight, "page_count"))
        return self

    # ===== Tier 3: Escape Hatch =====

    def custom(
        self, feature: Feature, name: Optional[str] = None
    ) -> "BookSimilarity":
        """Add a custom feature for power users.

        Args:
            feature: Custom Feature (extractor + metric + weight)
            name: Optional name for this feature

        Returns:
            Self for chaining
        """
        if name:
            feature.name = name
        self.features.append(feature)
        return self

    # ===== Core Functionality =====

    def fit(self, books: List[Book]) -> "BookSimilarity":
        """Fit all metrics on the corpus.

        This pre-computes expensive features (e.g., TF-IDF vectors) for
        dramatic performance improvements.

        Args:
            books: List of books to fit on

        Returns:
            Self for chaining
        """
        if not books:
            return self

        # For each feature, extract values and fit metric
        for feature in self.features:
            # Extract values for all books
            data = {}
            for book in books:
                try:
                    value = feature.extractor.extract(book)
                    data[book.id] = value
                except Exception:
                    # Skip books that fail extraction
                    continue

            # Fit metric (no-op for most metrics)
            feature.metric.fit(data)

        self._fitted = True
        return self

    def similarity(self, book1: Book, book2: Book) -> float:
        """Compute similarity between two books.

        Returns weighted average of all feature similarities.

        Args:
            book1: First book
            book2: Second book

        Returns:
            Similarity score in [0, 1]
        """
        if not self.features:
            raise ValueError("No features configured. Use .content(), .authors(), etc.")

        total_weighted_sim = 0.0
        total_weight = 0.0

        for feature in self.features:
            try:
                weighted_sim = feature.similarity(book1, book2)
                total_weighted_sim += weighted_sim
                total_weight += feature.weight
            except Exception:
                # Skip features that fail
                continue

        if total_weight == 0:
            return 0.0

        return total_weighted_sim / total_weight

    def similarity_matrix(self, books: List[Book]) -> np.ndarray:
        """Compute pairwise similarity matrix for all books.

        Returns NxN matrix where matrix[i][j] = similarity(books[i], books[j])

        This is much faster than computing similarities one by one.

        Args:
            books: List of books

        Returns:
            NxN numpy array of similarities
        """
        n = len(books)
        matrix = np.zeros((n, n))

        # Diagonal is always 1.0 (book is identical to itself)
        np.fill_diagonal(matrix, 1.0)

        # Compute upper triangle (matrix is symmetric)
        for i in range(n):
            for j in range(i + 1, n):
                sim = self.similarity(books[i], books[j])
                matrix[i][j] = sim
                matrix[j][i] = sim  # Symmetric

        return matrix

    def find_similar(
        self, book: Book, candidates: List[Book], top_k: int = 10
    ) -> List[Tuple[Book, float]]:
        """Find top-k most similar books from candidates.

        Args:
            book: Query book
            candidates: Candidate books to compare against
            top_k: Number of results to return (default 10)

        Returns:
            List of (book, similarity) tuples, sorted by similarity descending
        """
        # Compute similarities
        similarities = []
        for candidate in candidates:
            if candidate.id == book.id:
                continue  # Skip self

            sim = self.similarity(book, candidate)
            similarities.append((candidate, sim))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Return top-k
        return similarities[:top_k]

    def save(self, path: Path) -> None:
        """Save fitted state to disk.

        Args:
            path: Directory to save to (will create multiple files)
        """
        if not self._fitted:
            raise RuntimeError("Must call fit() before save()")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save each feature's metric
        for i, feature in enumerate(self.features):
            metric_path = path / f"metric_{i}_{feature.name}.pkl"
            feature.metric.save(metric_path)

    def load(self, path: Path) -> None:
        """Load fitted state from disk.

        Args:
            path: Directory to load from
        """
        path = Path(path)

        # Load each feature's metric
        for i, feature in enumerate(self.features):
            metric_path = path / f"metric_{i}_{feature.name}.pkl"
            if metric_path.exists():
                feature.metric.load(metric_path)

        self._fitted = True
