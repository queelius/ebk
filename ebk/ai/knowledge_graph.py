"""
Knowledge Graph implementation for connecting concepts across books.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import networkx as nx
import numpy as np
from collections import defaultdict


@dataclass
class ConceptNode:
    """Represents a concept/idea extracted from books."""
    id: str
    name: str
    description: str
    source_books: List[str] = field(default_factory=list)
    contexts: List[Dict[str, Any]] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    importance_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def add_context(self, book_id: str, page: int, quote: str, chapter: str = None):
        """Add a context where this concept appears."""
        self.contexts.append({
            'book_id': book_id,
            'page': page,
            'quote': quote,
            'chapter': chapter,
            'timestamp': datetime.now().isoformat()
        })
        if book_id not in self.source_books:
            self.source_books.append(book_id)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'source_books': self.source_books,
            'contexts': self.contexts,
            'keywords': self.keywords,
            'importance_score': self.importance_score,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class ConceptRelation:
    """Represents a relationship between two concepts."""
    source_id: str
    target_id: str
    relation_type: str  # 'supports', 'contradicts', 'extends', 'examples', 'causes', etc.
    strength: float = 1.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)

    def add_evidence(self, book_id: str, description: str):
        """Add evidence for this relationship."""
        self.evidence.append({
            'book_id': book_id,
            'description': description,
            'timestamp': datetime.now().isoformat()
        })


class KnowledgeGraph:
    """
    A knowledge graph that connects concepts across multiple books.
    Uses NetworkX for graph operations and provides rich querying capabilities.
    """

    def __init__(self, library_path: Path):
        self.library_path = Path(library_path)
        self.graph_path = self.library_path / '.knowledge_graph'
        self.graph_path.mkdir(exist_ok=True)

        self.graph = nx.DiGraph()
        self.concepts: Dict[str, ConceptNode] = {}
        self.concept_index: Dict[str, List[str]] = defaultdict(list)  # keyword -> concept_ids
        self.book_concepts: Dict[str, Set[str]] = defaultdict(set)  # book_id -> concept_ids

        self.load_graph()

    def generate_concept_id(self, name: str, context: str = "") -> str:
        """Generate a unique ID for a concept."""
        content = f"{name.lower()}:{context}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def add_concept(self, name: str, description: str,
                   book_id: str = None, page: int = None,
                   quote: str = None, keywords: List[str] = None) -> ConceptNode:
        """Add a new concept or update existing one."""
        concept_id = self.generate_concept_id(name, description[:50])

        if concept_id in self.concepts:
            concept = self.concepts[concept_id]
            if book_id and quote:
                concept.add_context(book_id, page, quote)
        else:
            concept = ConceptNode(
                id=concept_id,
                name=name,
                description=description,
                keywords=keywords or self._extract_keywords(name, description)
            )
            if book_id and quote:
                concept.add_context(book_id, page, quote)

            self.concepts[concept_id] = concept
            self.graph.add_node(concept_id, **concept.to_dict())

            # Update indices
            for keyword in concept.keywords:
                self.concept_index[keyword.lower()].append(concept_id)
            if book_id:
                self.book_concepts[book_id].add(concept_id)

        return concept

    def add_relation(self, source_name: str, target_name: str,
                    relation_type: str, strength: float = 1.0,
                    book_id: str = None, evidence: str = None) -> ConceptRelation:
        """Add a relationship between two concepts."""
        source_id = self.generate_concept_id(source_name, "")
        target_id = self.generate_concept_id(target_name, "")

        # Ensure both concepts exist
        if source_id not in self.concepts or target_id not in self.concepts:
            raise ValueError(f"Both concepts must exist before creating a relation")

        relation = ConceptRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            strength=strength
        )

        if book_id and evidence:
            relation.add_evidence(book_id, evidence)

        self.graph.add_edge(
            source_id, target_id,
            type=relation_type,
            strength=strength,
            evidence=relation.evidence
        )

        return relation

    def find_concept_path(self, start_concept: str, end_concept: str) -> List[str]:
        """Find the shortest path between two concepts."""
        start_id = self.generate_concept_id(start_concept, "")
        end_id = self.generate_concept_id(end_concept, "")

        if start_id not in self.graph or end_id not in self.graph:
            return []

        try:
            path = nx.shortest_path(self.graph, start_id, end_id)
            return [self.concepts[node_id].name for node_id in path]
        except nx.NetworkXNoPath:
            return []

    def find_related_concepts(self, concept_name: str,
                            max_distance: int = 2,
                            min_strength: float = 0.5) -> List[Tuple[str, float]]:
        """Find concepts related to a given concept within a certain distance."""
        concept_id = self.generate_concept_id(concept_name, "")

        if concept_id not in self.graph:
            # Try fuzzy matching
            concept_id = self._fuzzy_find_concept(concept_name)
            if not concept_id:
                return []

        related = []
        visited = set()

        # BFS with distance tracking
        queue = [(concept_id, 0, 1.0)]

        while queue:
            current_id, distance, accumulated_strength = queue.pop(0)

            if current_id in visited or distance > max_distance:
                continue

            visited.add(current_id)

            if current_id != concept_id and accumulated_strength >= min_strength:
                concept = self.concepts[current_id]
                related.append((concept.name, accumulated_strength))

            # Explore neighbors
            for neighbor in self.graph.neighbors(current_id):
                edge_data = self.graph[current_id][neighbor]
                new_strength = accumulated_strength * edge_data.get('strength', 1.0)
                queue.append((neighbor, distance + 1, new_strength))

        # Sort by relevance (accumulated strength)
        related.sort(key=lambda x: x[1], reverse=True)
        return related

    def get_concept_connections(self, book_id: str) -> Dict[str, List[str]]:
        """Get all concept connections for a specific book."""
        book_concept_ids = self.book_concepts.get(book_id, set())
        connections = {}

        for concept_id in book_concept_ids:
            concept = self.concepts[concept_id]
            neighbors = []

            for neighbor_id in self.graph.neighbors(concept_id):
                neighbor = self.concepts[neighbor_id]
                edge_data = self.graph[concept_id][neighbor_id]
                neighbors.append({
                    'name': neighbor.name,
                    'relation': edge_data.get('type', 'related'),
                    'strength': edge_data.get('strength', 1.0)
                })

            if neighbors:
                connections[concept.name] = neighbors

        return connections

    def generate_reading_path(self, start_topic: str,
                            end_topic: str,
                            available_books: List[str]) -> List[Dict[str, Any]]:
        """
        Generate a reading path from one topic to another using available books.
        Returns a sequence of books and the concepts they'll teach.
        """
        start_concepts = self._find_concepts_by_topic(start_topic)
        end_concepts = self._find_concepts_by_topic(end_topic)

        if not start_concepts or not end_concepts:
            return []

        # Find paths between all concept pairs
        all_paths = []
        for start_id in start_concepts:
            for end_id in end_concepts:
                try:
                    path = nx.shortest_path(self.graph, start_id, end_id)
                    all_paths.append(path)
                except nx.NetworkXNoPath:
                    continue

        if not all_paths:
            return []

        # Select the best path (shortest with most book coverage)
        best_path = min(all_paths, key=len)

        # Map concepts to books
        reading_sequence = []
        covered_concepts = set()

        for concept_id in best_path:
            if concept_id in covered_concepts:
                continue

            concept = self.concepts[concept_id]
            # Find which available book best covers this concept
            best_book = None
            max_coverage = 0

            for book_id in concept.source_books:
                if book_id in available_books:
                    coverage = len([c for c in concept.contexts if c['book_id'] == book_id])
                    if coverage > max_coverage:
                        max_coverage = coverage
                        best_book = book_id

            if best_book:
                reading_sequence.append({
                    'book_id': best_book,
                    'concept': concept.name,
                    'description': concept.description,
                    'why': f"Bridges understanding from {start_topic} towards {end_topic}"
                })
                covered_concepts.add(concept_id)

        return reading_sequence

    def calculate_concept_importance(self) -> Dict[str, float]:
        """
        Calculate importance scores for all concepts using PageRank-like algorithm.
        """
        if not self.graph.nodes():
            return {}

        # Calculate PageRank
        pagerank_scores = nx.pagerank(self.graph, weight='strength')

        # Update concept importance scores
        for concept_id, score in pagerank_scores.items():
            if concept_id in self.concepts:
                self.concepts[concept_id].importance_score = score

        return pagerank_scores

    def get_key_concepts(self, top_n: int = 10) -> List[ConceptNode]:
        """Get the most important concepts in the knowledge graph."""
        self.calculate_concept_importance()

        sorted_concepts = sorted(
            self.concepts.values(),
            key=lambda c: c.importance_score,
            reverse=True
        )

        return sorted_concepts[:top_n]

    def export_for_visualization(self) -> Dict[str, Any]:
        """Export graph data for visualization tools."""
        nodes = []
        edges = []

        for concept_id, concept in self.concepts.items():
            nodes.append({
                'id': concept_id,
                'label': concept.name,
                'title': concept.description,
                'value': concept.importance_score * 100,
                'group': len(concept.source_books)  # Group by number of source books
            })

        for source, target, data in self.graph.edges(data=True):
            edges.append({
                'from': source,
                'to': target,
                'label': data.get('type', 'related'),
                'value': data.get('strength', 1.0)
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'metadata': {
                'total_concepts': len(self.concepts),
                'total_relations': self.graph.number_of_edges(),
                'books_indexed': len(self.book_concepts)
            }
        }

    def save_graph(self):
        """Persist the knowledge graph to disk."""
        # Save concepts
        concepts_data = {
            cid: concept.to_dict()
            for cid, concept in self.concepts.items()
        }
        with open(self.graph_path / 'concepts.json', 'w') as f:
            json.dump(concepts_data, f, indent=2)

        # Save graph structure
        graph_data = nx.node_link_data(self.graph)
        with open(self.graph_path / 'graph.json', 'w') as f:
            json.dump(graph_data, f, indent=2)

        # Save indices
        indices = {
            'concept_index': dict(self.concept_index),
            'book_concepts': {k: list(v) for k, v in self.book_concepts.items()}
        }
        with open(self.graph_path / 'indices.json', 'w') as f:
            json.dump(indices, f, indent=2)

    def load_graph(self):
        """Load the knowledge graph from disk."""
        concepts_file = self.graph_path / 'concepts.json'
        graph_file = self.graph_path / 'graph.json'
        indices_file = self.graph_path / 'indices.json'

        if concepts_file.exists():
            with open(concepts_file, 'r') as f:
                concepts_data = json.load(f)
                for cid, cdata in concepts_data.items():
                    # Reconstruct ConceptNode
                    cdata['created_at'] = datetime.fromisoformat(cdata['created_at'])
                    self.concepts[cid] = ConceptNode(**{
                        k: v for k, v in cdata.items()
                        if k in ConceptNode.__dataclass_fields__
                    })

        if graph_file.exists():
            with open(graph_file, 'r') as f:
                graph_data = json.load(f)
                self.graph = nx.node_link_graph(graph_data)

        if indices_file.exists():
            with open(indices_file, 'r') as f:
                indices = json.load(f)
                self.concept_index = defaultdict(list, indices.get('concept_index', {}))
                self.book_concepts = defaultdict(
                    set,
                    {k: set(v) for k, v in indices.get('book_concepts', {}).items()}
                )

    def _extract_keywords(self, name: str, description: str) -> List[str]:
        """Extract keywords from concept name and description."""
        # Simple keyword extraction - can be enhanced with NLP
        import re
        text = f"{name} {description}".lower()
        words = re.findall(r'\b[a-z]+\b', text)
        # Filter common words and return unique keywords
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'as', 'is', 'was', 'are', 'been'}
        keywords = list(set(w for w in words if w not in stopwords and len(w) > 3))
        return keywords[:10]  # Limit to 10 keywords

    def _fuzzy_find_concept(self, name: str) -> Optional[str]:
        """Find concept by fuzzy matching the name."""
        name_lower = name.lower()
        for concept_id, concept in self.concepts.items():
            if name_lower in concept.name.lower() or concept.name.lower() in name_lower:
                return concept_id
        return None

    def _find_concepts_by_topic(self, topic: str) -> List[str]:
        """Find all concepts related to a topic."""
        topic_lower = topic.lower()
        related_concepts = []

        # Search in concept names and descriptions
        for concept_id, concept in self.concepts.items():
            if (topic_lower in concept.name.lower() or
                topic_lower in concept.description.lower() or
                any(topic_lower in kw.lower() for kw in concept.keywords)):
                related_concepts.append(concept_id)

        # Search in concept index
        for keyword in topic_lower.split():
            related_concepts.extend(self.concept_index.get(keyword, []))

        return list(set(related_concepts))