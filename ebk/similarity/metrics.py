"""Concrete metric implementations."""

import math
import pickle
from pathlib import Path
from typing import Dict, Optional, Set

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ebk.similarity.base import Metric


class JaccardMetric(Metric[Set[str]]):
    """Jaccard similarity for sets.

    Computes |A ∩ B| / |A ∪ B|

    Returns:
        1.0 if sets are identical
        0.0 if sets have no overlap
    """

    def similarity(self, value1: Set[str], value2: Set[str]) -> float:
        """Compute Jaccard similarity between two sets.

        Args:
            value1: First set
            value2: Second set

        Returns:
            Jaccard similarity in [0, 1]
        """
        if not value1 and not value2:
            return 1.0  # Both empty = identical

        if not value1 or not value2:
            return 0.0  # One empty = no overlap

        intersection = len(value1 & value2)
        union = len(value1 | value2)

        if union == 0:
            return 0.0

        return intersection / union


class ExactMatchMetric(Metric):
    """Exact match metric for any comparable values.

    Returns:
        1.0 if values are equal
        0.0 if values are different
    """

    def similarity(self, value1, value2) -> float:
        """Compute exact match similarity.

        Args:
            value1: First value
            value2: Second value

        Returns:
            1.0 if equal, 0.0 otherwise
        """
        if value1 is None or value2 is None:
            return 0.0

        return 1.0 if value1 == value2 else 0.0


class TemporalDecayMetric(Metric[Optional[int]]):
    """Gaussian decay based on time difference.

    Similarity decays as Gaussian: exp(-((y1 - y2) / sigma)^2)

    Attributes:
        sigma: Standard deviation for Gaussian (controls decay rate)
               Default 10 years means ~60% similarity for 10-year gap
    """

    def __init__(self, sigma: float = 10.0):
        """Initialize temporal decay metric.

        Args:
            sigma: Standard deviation in years (default 10.0)
        """
        self.sigma = sigma

    def similarity(self, value1: Optional[int], value2: Optional[int]) -> float:
        """Compute temporal similarity with Gaussian decay.

        Args:
            value1: First year
            value2: Second year

        Returns:
            Similarity in [0, 1] based on Gaussian decay
        """
        if value1 is None or value2 is None:
            return 0.0

        diff = abs(value1 - value2)
        return math.exp(-((diff / self.sigma) ** 2))


class NumericProximityMetric(Metric[Optional[int]]):
    """Similarity based on numeric proximity with normalization.

    Computes: 1 - |v1 - v2| / max_diff

    Useful for page counts, ratings, etc.

    Attributes:
        max_diff: Maximum expected difference for normalization
    """

    def __init__(self, max_diff: float):
        """Initialize numeric proximity metric.

        Args:
            max_diff: Maximum expected difference (e.g., 1000 pages)
        """
        self.max_diff = max_diff

    def similarity(self, value1: Optional[int], value2: Optional[int]) -> float:
        """Compute numeric proximity similarity.

        Args:
            value1: First value
            value2: Second value

        Returns:
            Similarity in [0, 1] based on proximity
        """
        if value1 is None or value2 is None:
            return 0.0

        diff = abs(value1 - value2)
        normalized = min(diff / self.max_diff, 1.0)
        return 1.0 - normalized


class TfidfMetric(Metric[str]):
    """TF-IDF cosine similarity for text.

    This metric needs fitting to build vocabulary and cache vectors.

    Attributes:
        max_features: Maximum number of features for TF-IDF (default 5000)
        min_df: Minimum document frequency (default 2)
        max_df: Maximum document frequency (default 0.95)
    """

    def __init__(
        self,
        max_features: int = 5000,
        min_df: int = 2,
        max_df: float = 0.95,
    ):
        """Initialize TF-IDF metric.

        Args:
            max_features: Maximum number of features (default 5000)
            min_df: Minimum document frequency (default 2)
            max_df: Maximum document frequency (default 0.95)
        """
        self.max_features = max_features
        self.min_df = min_df
        self.max_df = max_df

        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            min_df=min_df,
            max_df=max_df,
            stop_words="english",
        )

        self._vectors: Dict[int, np.ndarray] = {}
        self._fitted = False

    def fit(self, data: Dict[int, str]) -> None:
        """Fit vectorizer and cache all vectors.

        This dramatically speeds up similarity computation by pre-computing
        TF-IDF vectors for all books.

        Args:
            data: Dictionary mapping book IDs to text content
        """
        if not data:
            return

        # Fit vectorizer on all texts
        book_ids = list(data.keys())
        texts = [data[book_id] for book_id in book_ids]

        # Fit and transform
        vectors = self.vectorizer.fit_transform(texts)

        # Cache sparse vectors by book_id
        for book_id, vector in zip(book_ids, vectors):
            self._vectors[book_id] = vector

        self._fitted = True

    def similarity(self, value1: str, value2: str) -> float:
        """Compute TF-IDF cosine similarity.

        If not fitted, transforms texts on-the-fly (slow).
        If fitted, uses cached vectors (fast).

        Args:
            value1: First text
            value2: Second text

        Returns:
            Cosine similarity in [0, 1]
        """
        if not value1 or not value2:
            return 0.0

        # Transform texts to vectors
        if not self._fitted:
            # Not fitted - transform on the fly (slow path)
            try:
                vectors = self.vectorizer.fit_transform([value1, value2])
                v1, v2 = vectors[0], vectors[1]
            except ValueError:
                # Empty vocabulary
                return 0.0
        else:
            # Fitted - transform using learned vocabulary
            try:
                v1 = self.vectorizer.transform([value1])
                v2 = self.vectorizer.transform([value2])
            except ValueError:
                return 0.0

        # Compute cosine similarity
        sim = cosine_similarity(v1, v2)[0, 0]

        # Ensure [0, 1] range (cosine can be negative for sparse vectors)
        return max(0.0, min(1.0, sim))

    def similarity_from_cache(self, book1_id: int, book2_id: int) -> float:
        """Fast similarity using pre-computed vectors.

        Args:
            book1_id: ID of first book
            book2_id: ID of second book

        Returns:
            Cosine similarity in [0, 1]

        Raises:
            KeyError: If book IDs not in cache (need to call fit() first)
        """
        if not self._fitted:
            raise RuntimeError("Must call fit() before similarity_from_cache()")

        v1 = self._vectors[book1_id]
        v2 = self._vectors[book2_id]

        sim = cosine_similarity(v1, v2)[0, 0]
        return max(0.0, min(1.0, sim))

    def save(self, path: Path) -> None:
        """Save fitted state to disk.

        Args:
            path: Path to save to (will create .pkl file)
        """
        if not self._fitted:
            raise RuntimeError("Must call fit() before save()")

        state = {
            "vectorizer": self.vectorizer,
            "vectors": self._vectors,
            "max_features": self.max_features,
            "min_df": self.min_df,
            "max_df": self.max_df,
        }

        with open(path, "wb") as f:
            pickle.dump(state, f)

    def load(self, path: Path) -> None:
        """Load fitted state from disk.

        Args:
            path: Path to load from
        """
        with open(path, "rb") as f:
            state = pickle.load(f)

        self.vectorizer = state["vectorizer"]
        self._vectors = state["vectors"]
        self.max_features = state["max_features"]
        self.min_df = state["min_df"]
        self.max_df = state["max_df"]
        self._fitted = True


class CosineMetric(Metric[str]):
    """Simple cosine similarity without TF-IDF weighting.

    Uses CountVectorizer instead of TF-IDF. Faster but less accurate
    than TfidfMetric.
    """

    def __init__(self, max_features: int = 5000):
        """Initialize cosine metric.

        Args:
            max_features: Maximum number of features (default 5000)
        """
        from sklearn.feature_extraction.text import CountVectorizer

        self.max_features = max_features
        self.vectorizer = CountVectorizer(
            max_features=max_features,
            stop_words="english",
        )
        self._vectors: Dict[int, np.ndarray] = {}
        self._fitted = False

    def fit(self, data: Dict[int, str]) -> None:
        """Fit vectorizer and cache all vectors.

        Args:
            data: Dictionary mapping book IDs to text content
        """
        if not data:
            return

        book_ids = list(data.keys())
        texts = [data[book_id] for book_id in book_ids]

        vectors = self.vectorizer.fit_transform(texts)

        for book_id, vector in zip(book_ids, vectors):
            self._vectors[book_id] = vector

        self._fitted = True

    def similarity(self, value1: str, value2: str) -> float:
        """Compute cosine similarity.

        Args:
            value1: First text
            value2: Second text

        Returns:
            Cosine similarity in [0, 1]
        """
        if not value1 or not value2:
            return 0.0

        if not self._fitted:
            try:
                vectors = self.vectorizer.fit_transform([value1, value2])
                v1, v2 = vectors[0], vectors[1]
            except ValueError:
                return 0.0
        else:
            try:
                v1 = self.vectorizer.transform([value1])
                v2 = self.vectorizer.transform([value2])
            except ValueError:
                return 0.0

        sim = cosine_similarity(v1, v2)[0, 0]
        return max(0.0, min(1.0, sim))
