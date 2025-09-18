"""
Semantic search using vector embeddings for intelligent content discovery.
"""

import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import logging
from collections import defaultdict

# Use sentence-transformers for embeddings if available
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False
    logging.warning("sentence-transformers not installed. Using fallback embedding method.")

# Fallback: simple TF-IDF based embeddings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


@dataclass
class EmbeddedDocument:
    """A document with its embedding vector."""
    id: str
    text: str
    embedding: np.ndarray
    metadata: Dict[str, Any]

    def similarity(self, other_embedding: np.ndarray) -> float:
        """Calculate cosine similarity with another embedding."""
        return float(cosine_similarity(
            self.embedding.reshape(1, -1),
            other_embedding.reshape(1, -1)
        )[0, 0])


class EmbeddingStore:
    """
    Store and retrieve document embeddings for semantic search.
    Provides a simple vector database for similarity search.
    """

    def __init__(self, library_path: Path, model_name: str = "all-MiniLM-L6-v2"):
        self.library_path = Path(library_path)
        self.store_path = self.library_path / '.embeddings'
        self.store_path.mkdir(exist_ok=True)

        self.model_name = model_name
        self.embeddings: Dict[str, EmbeddedDocument] = {}
        self.index_metadata: Dict[str, Any] = {}

        # Initialize embedding model
        if HAS_SENTENCE_TRANSFORMERS:
            try:
                self.model = SentenceTransformer(model_name)
                self.embedding_dim = self.model.get_sentence_embedding_dimension()
                self.use_transformer = True
            except Exception as e:
                logger.warning(f"Failed to load SentenceTransformer: {e}. Using TF-IDF fallback.")
                self._init_tfidf()
        else:
            self._init_tfidf()

        self.load_embeddings()

    def _init_tfidf(self):
        """Initialize TF-IDF vectorizer as fallback."""
        self.vectorizer = TfidfVectorizer(max_features=768, stop_words='english')
        self.use_transformer = False
        self.embedding_dim = 768
        self.fitted_texts = []

    def add_document(self, text: str, metadata: Dict[str, Any] = None) -> str:
        """Add a document and compute its embedding."""
        # Generate ID
        doc_id = self._generate_id(text)

        # Compute embedding
        embedding = self._compute_embedding(text)

        # Store document
        self.embeddings[doc_id] = EmbeddedDocument(
            id=doc_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {}
        )

        return doc_id

    def add_batch(self, texts: List[str], metadata_list: List[Dict[str, Any]] = None) -> List[str]:
        """Add multiple documents efficiently."""
        if metadata_list is None:
            metadata_list = [{}] * len(texts)

        # Compute embeddings in batch
        embeddings = self._compute_embeddings_batch(texts)

        doc_ids = []
        for text, embedding, metadata in zip(texts, embeddings, metadata_list):
            doc_id = self._generate_id(text)
            self.embeddings[doc_id] = EmbeddedDocument(
                id=doc_id,
                text=text,
                embedding=embedding,
                metadata=metadata
            )
            doc_ids.append(doc_id)

        return doc_ids

    def search(self, query: str, top_k: int = 10,
              min_similarity: float = 0.0,
              filter_metadata: Dict[str, Any] = None) -> List[Tuple[EmbeddedDocument, float]]:
        """
        Search for similar documents using semantic similarity.
        """
        # Compute query embedding
        query_embedding = self._compute_embedding(query)

        # Calculate similarities
        results = []
        for doc_id, doc in self.embeddings.items():
            # Apply metadata filter
            if filter_metadata:
                if not self._matches_filter(doc.metadata, filter_metadata):
                    continue

            # Calculate similarity
            similarity = doc.similarity(query_embedding)

            if similarity >= min_similarity:
                results.append((doc, similarity))

        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)

        return results[:top_k]

    def find_similar(self, doc_id: str, top_k: int = 10,
                    min_similarity: float = 0.0) -> List[Tuple[EmbeddedDocument, float]]:
        """Find documents similar to a given document."""
        if doc_id not in self.embeddings:
            return []

        source_doc = self.embeddings[doc_id]
        results = []

        for other_id, other_doc in self.embeddings.items():
            if other_id == doc_id:
                continue

            similarity = source_doc.similarity(other_doc.embedding)

            if similarity >= min_similarity:
                results.append((other_doc, similarity))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_document(self, doc_id: str) -> Optional[EmbeddedDocument]:
        """Retrieve a document by ID."""
        return self.embeddings.get(doc_id)

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from the store."""
        if doc_id in self.embeddings:
            del self.embeddings[doc_id]
            return True
        return False

    def save_embeddings(self):
        """Save embeddings to disk."""
        # Save embeddings
        embeddings_file = self.store_path / 'embeddings.pkl'
        with open(embeddings_file, 'wb') as f:
            pickle.dump(self.embeddings, f)

        # Save metadata
        metadata_file = self.store_path / 'metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump({
                'model_name': self.model_name,
                'use_transformer': self.use_transformer,
                'embedding_dim': self.embedding_dim,
                'num_documents': len(self.embeddings)
            }, f, indent=2)

        # Save TF-IDF vectorizer if used
        if not self.use_transformer and hasattr(self, 'vectorizer'):
            vectorizer_file = self.store_path / 'vectorizer.pkl'
            with open(vectorizer_file, 'wb') as f:
                pickle.dump(self.vectorizer, f)

    def load_embeddings(self):
        """Load embeddings from disk."""
        embeddings_file = self.store_path / 'embeddings.pkl'
        metadata_file = self.store_path / 'metadata.json'

        if embeddings_file.exists():
            with open(embeddings_file, 'rb') as f:
                self.embeddings = pickle.load(f)

        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                self.index_metadata = json.load(f)

        # Load TF-IDF vectorizer if needed
        if not self.use_transformer:
            vectorizer_file = self.store_path / 'vectorizer.pkl'
            if vectorizer_file.exists():
                with open(vectorizer_file, 'rb') as f:
                    self.vectorizer = pickle.load(f)

    def _compute_embedding(self, text: str) -> np.ndarray:
        """Compute embedding for a single text."""
        if self.use_transformer:
            return self.model.encode(text, convert_to_numpy=True)
        else:
            # TF-IDF fallback
            if not hasattr(self, 'vectorizer') or not self.fitted_texts:
                # First text - fit the vectorizer
                self.fitted_texts = [text]
                embeddings = self.vectorizer.fit_transform([text])
            else:
                # Transform using existing vocabulary
                try:
                    embeddings = self.vectorizer.transform([text])
                except:
                    # Refit with all texts if vocabulary changed
                    self.fitted_texts.append(text)
                    embeddings = self.vectorizer.fit_transform(self.fitted_texts)

            return embeddings.toarray()[0]

    def _compute_embeddings_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Compute embeddings for multiple texts efficiently."""
        if self.use_transformer:
            return self.model.encode(texts, convert_to_numpy=True)
        else:
            # TF-IDF fallback
            if not hasattr(self, 'vectorizer') or not self.fitted_texts:
                self.fitted_texts = texts
                embeddings = self.vectorizer.fit_transform(texts)
            else:
                try:
                    embeddings = self.vectorizer.transform(texts)
                except:
                    self.fitted_texts.extend(texts)
                    embeddings = self.vectorizer.fit_transform(self.fitted_texts)

            return [embeddings[i].toarray()[0] for i in range(len(texts))]

    def _generate_id(self, text: str) -> str:
        """Generate unique ID for a document."""
        return hashlib.md5(text.encode()).hexdigest()[:16]

    def _matches_filter(self, metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        """Check if metadata matches filter criteria."""
        for key, value in filter_dict.items():
            if key not in metadata:
                return False
            if isinstance(value, list):
                if metadata[key] not in value:
                    return False
            else:
                if metadata[key] != value:
                    return False
        return True


class SemanticSearch:
    """
    High-level semantic search interface for ebook libraries.
    """

    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self.embedding_store = EmbeddingStore(library_path)
        self.book_chunks: Dict[str, List[str]] = {}  # book_id -> chunk_ids

    def index_book(self, book_id: str, text: str, chunk_size: int = 500):
        """
        Index a book by splitting into chunks and computing embeddings.
        """
        # Split text into chunks
        chunks = self._split_into_chunks(text, chunk_size)

        # Add chunks to embedding store
        chunk_ids = []
        for i, chunk in enumerate(chunks):
            metadata = {
                'book_id': book_id,
                'chunk_index': i,
                'chunk_total': len(chunks)
            }
            chunk_id = self.embedding_store.add_document(chunk, metadata)
            chunk_ids.append(chunk_id)

        self.book_chunks[book_id] = chunk_ids
        self.embedding_store.save_embeddings()

    def search_library(self, query: str, top_k: int = 10,
                      book_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search across the entire library or specific books.
        """
        # Prepare filter
        filter_metadata = None
        if book_ids:
            filter_metadata = {'book_id': book_ids}

        # Perform search
        results = self.embedding_store.search(
            query, top_k=top_k, filter_metadata=filter_metadata
        )

        # Format results
        formatted_results = []
        for doc, similarity in results:
            formatted_results.append({
                'book_id': doc.metadata.get('book_id'),
                'text': doc.text,
                'similarity': similarity,
                'chunk_index': doc.metadata.get('chunk_index'),
                'metadata': doc.metadata
            })

        return formatted_results

    def find_cross_references(self, book_id: str, passage: str,
                            other_books: List[str] = None) -> List[Dict[str, Any]]:
        """
        Find similar passages in other books (cross-references).
        """
        # Search in other books
        filter_metadata = None
        if other_books:
            filter_metadata = {'book_id': other_books}
        else:
            # Search all books except the source
            filter_metadata = {}

        results = self.embedding_store.search(
            passage, top_k=10, filter_metadata=filter_metadata
        )

        # Filter out results from the same book
        cross_refs = []
        for doc, similarity in results:
            if doc.metadata.get('book_id') != book_id:
                cross_refs.append({
                    'book_id': doc.metadata.get('book_id'),
                    'text': doc.text,
                    'similarity': similarity,
                    'metadata': doc.metadata
                })

        return cross_refs

    def get_book_summary_vectors(self, book_ids: List[str]) -> Dict[str, np.ndarray]:
        """
        Get summary embedding vectors for books (average of all chunks).
        """
        book_vectors = {}

        for book_id in book_ids:
            if book_id not in self.book_chunks:
                continue

            # Get all chunk embeddings
            embeddings = []
            for chunk_id in self.book_chunks[book_id]:
                doc = self.embedding_store.get_document(chunk_id)
                if doc:
                    embeddings.append(doc.embedding)

            if embeddings:
                # Average embeddings
                book_vectors[book_id] = np.mean(embeddings, axis=0)

        return book_vectors

    def find_similar_books(self, book_id: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Find books similar to a given book based on content similarity.
        """
        # Get summary vector for source book
        source_vectors = self.get_book_summary_vectors([book_id])
        if book_id not in source_vectors:
            return []

        source_vector = source_vectors[book_id]

        # Get vectors for all other books
        all_book_ids = list(self.book_chunks.keys())
        all_book_ids.remove(book_id) if book_id in all_book_ids else None

        other_vectors = self.get_book_summary_vectors(all_book_ids)

        # Calculate similarities
        similarities = []
        for other_id, other_vector in other_vectors.items():
            similarity = float(cosine_similarity(
                source_vector.reshape(1, -1),
                other_vector.reshape(1, -1)
            )[0, 0])
            similarities.append((other_id, similarity))

        # Sort and return top-k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _split_into_chunks(self, text: str, chunk_size: int) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        overlap = chunk_size // 4  # 25% overlap

        for i in range(0, len(words), chunk_size - overlap):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)

        return chunks