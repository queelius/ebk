"""
Network/Graph analysis plugin for EBK.

This plugin provides graph analysis capabilities without adding
dependencies to the core library. Users can optionally install
NetworkX or other graph libraries for advanced features.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict

from ebk.plugins.base import Plugin


class NetworkAnalyzer(Plugin):
    """
    Analyzes relationships in the library as network graphs.
    
    Provides co-author networks, subject co-occurrence graphs,
    and other relationship analyses.
    """
    
    @property
    def name(self) -> str:
        return "network_analyzer"
    
    @property
    def version(self) -> str:
        return "1.0.0"
    
    @property
    def description(self) -> str:
        return "Network and graph analysis for ebook libraries"
    
    @property
    def author(self) -> str:
        return "EBK Team"
    
    def build_coauthor_network(self, entries: List[Dict[str, Any]], 
                               min_connections: int = 1) -> Dict[str, Any]:
        """
        Build co-author collaboration network.
        
        Args:
            entries: List of library entries
            min_connections: Minimum collaborations to include author
            
        Returns:
            Graph data with nodes and edges
        """
        # Build co-author relationships
        coauthors = defaultdict(set)
        author_books = defaultdict(list)
        collaborations = defaultdict(int)
        
        for entry in entries:
            creators = entry.get('creators', [])
            entry_id = entry.get('unique_id', '')
            
            # Track books per author
            for author in creators:
                author_books[author].append(entry_id)
            
            # Track collaborations
            for i, author1 in enumerate(creators):
                for author2 in creators[i+1:]:
                    coauthors[author1].add(author2)
                    coauthors[author2].add(author1)
                    # Count collaboration frequency
                    collab_key = tuple(sorted([author1, author2]))
                    collaborations[collab_key] += 1
        
        # Filter by minimum connections
        included_authors = {
            author for author, connections in coauthors.items()
            if len(connections) >= min_connections
        }
        
        # Build nodes with rich metadata
        nodes = []
        for author in included_authors:
            nodes.append({
                'id': author,
                'label': author,
                'type': 'author',
                'books': len(author_books[author]),
                'collaborators': len(coauthors[author]),
                'book_ids': author_books[author]
            })
        
        # Build edges with weights
        edges = []
        seen_edges = set()
        
        for (author1, author2), count in collaborations.items():
            if author1 in included_authors and author2 in included_authors:
                edge_key = tuple(sorted([author1, author2]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        'source': author1,
                        'target': author2,
                        'weight': count,
                        'type': 'collaboration'
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'type': 'coauthor_network',
            'directed': False,
            'metadata': {
                'total_authors': len(author_books),
                'included_authors': len(included_authors),
                'total_collaborations': len(collaborations)
            }
        }
    
    def build_subject_network(self, entries: List[Dict[str, Any]], 
                             min_connections: int = 1) -> Dict[str, Any]:
        """
        Build subject co-occurrence network.
        
        Args:
            entries: List of library entries
            min_connections: Minimum co-occurrences to include subject
            
        Returns:
            Graph data with nodes and edges
        """
        # Build subject relationships
        cooccurrences = defaultdict(set)
        subject_books = defaultdict(list)
        cooccurrence_counts = defaultdict(int)
        
        for entry in entries:
            subjects = entry.get('subjects', [])
            entry_id = entry.get('unique_id', '')
            
            # Track books per subject
            for subject in subjects:
                subject_books[subject].append(entry_id)
            
            # Track co-occurrences
            for i, subject1 in enumerate(subjects):
                for subject2 in subjects[i+1:]:
                    cooccurrences[subject1].add(subject2)
                    cooccurrences[subject2].add(subject1)
                    # Count co-occurrence frequency
                    cooc_key = tuple(sorted([subject1, subject2]))
                    cooccurrence_counts[cooc_key] += 1
        
        # Filter by minimum connections
        included_subjects = {
            subject for subject, connections in cooccurrences.items()
            if len(connections) >= min_connections
        }
        
        # Build nodes
        nodes = []
        for subject in included_subjects:
            nodes.append({
                'id': subject,
                'label': subject,
                'type': 'subject',
                'books': len(subject_books[subject]),
                'related_subjects': len(cooccurrences[subject]),
                'book_ids': subject_books[subject]
            })
        
        # Build edges
        edges = []
        seen_edges = set()
        
        for (subject1, subject2), count in cooccurrence_counts.items():
            if subject1 in included_subjects and subject2 in included_subjects:
                edge_key = tuple(sorted([subject1, subject2]))
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        'source': subject1,
                        'target': subject2,
                        'weight': count,
                        'type': 'cooccurrence'
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'type': 'subject_network',
            'directed': False,
            'metadata': {
                'total_subjects': len(subject_books),
                'included_subjects': len(included_subjects),
                'total_cooccurrences': len(cooccurrence_counts)
            }
        }
    
    def build_citation_network(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build citation network (if entries have citation data).
        
        Args:
            entries: List of library entries
            
        Returns:
            Graph data for citation network
        """
        nodes = []
        edges = []
        
        # Build entry lookup
        entry_lookup = {e.get('unique_id'): e for e in entries}
        
        for entry in entries:
            entry_id = entry.get('unique_id', '')
            
            # Add node for this entry
            nodes.append({
                'id': entry_id,
                'label': entry.get('title', 'Unknown'),
                'type': 'work',
                'year': entry.get('year'),
                'authors': entry.get('creators', []),
                'subjects': entry.get('subjects', [])
            })
            
            # Check for citations (might be in custom fields)
            citations = entry.get('citations', [])
            references = entry.get('references', [])
            
            for cited_id in citations + references:
                if cited_id in entry_lookup:
                    edges.append({
                        'source': entry_id,
                        'target': cited_id,
                        'type': 'citation'
                    })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'type': 'citation_network',
            'directed': True,
            'metadata': {
                'total_works': len(nodes),
                'total_citations': len(edges)
            }
        }
    
    def export_graph(self, graph_data: Dict[str, Any], 
                    output_path: str,
                    format: str = 'json') -> bool:
        """
        Export graph data to various formats.
        
        Args:
            graph_data: Graph data dictionary
            output_path: Output file path
            format: Export format (json, dot, gml, graphml)
            
        Returns:
            True if successful
        """
        path = Path(output_path)
        
        if format == 'json':
            with open(path, 'w') as f:
                json.dump(graph_data, f, indent=2)
        
        elif format == 'dot':
            self._export_dot(graph_data, path)
        
        elif format == 'gml':
            self._export_gml(graph_data, path)
        
        elif format == 'graphml':
            self._export_graphml(graph_data, path)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return True
    
    def _export_dot(self, graph_data: Dict[str, Any], path: Path) -> None:
        """Export to Graphviz DOT format."""
        directed = graph_data.get('directed', False)
        graph_type = 'digraph' if directed else 'graph'
        edge_op = '->' if directed else '--'
        
        lines = [f'{graph_type} G {{']
        
        # Add nodes
        for node in graph_data['nodes']:
            label = node['label'].replace('"', '\\"')
            attrs = [f'label="{label}"']
            if 'books' in node:
                attrs.append(f'weight={node["books"]}')
            lines.append(f'  "{node["id"]}" [{", ".join(attrs)}];')
        
        # Add edges
        for edge in graph_data['edges']:
            attrs = []
            if 'weight' in edge:
                attrs.append(f'weight={edge["weight"]}')
            attr_str = f' [{", ".join(attrs)}]' if attrs else ''
            lines.append(f'  "{edge["source"]}" {edge_op} "{edge["target"]}"{attr_str};')
        
        lines.append('}')
        
        with open(path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _export_gml(self, graph_data: Dict[str, Any], path: Path) -> None:
        """Export to GML format."""
        lines = ['graph [']
        lines.append(f'  directed {1 if graph_data.get("directed") else 0}')
        
        # Create node ID mapping
        node_map = {node['id']: i for i, node in enumerate(graph_data['nodes'])}
        
        # Add nodes
        for i, node in enumerate(graph_data['nodes']):
            lines.extend([
                '  node [',
                f'    id {i}',
                f'    label "{node["label"]}"'
            ])
            if 'books' in node:
                lines.append(f'    books {node["books"]}')
            lines.append('  ]')
        
        # Add edges
        for edge in graph_data['edges']:
            lines.extend([
                '  edge [',
                f'    source {node_map[edge["source"]]}',
                f'    target {node_map[edge["target"]]}'
            ])
            if 'weight' in edge:
                lines.append(f'    weight {edge["weight"]}')
            lines.append('  ]')
        
        lines.append(']')
        
        with open(path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _export_graphml(self, graph_data: Dict[str, Any], path: Path) -> None:
        """Export to GraphML format."""
        # Note: This is a simplified GraphML export
        # For full GraphML support, consider using NetworkX
        lines = ['<?xml version="1.0" encoding="UTF-8"?>']
        lines.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
        lines.append('  <graph edgedefault="{}">'.format(
            'directed' if graph_data.get('directed') else 'undirected'
        ))
        
        # Add nodes
        for node in graph_data['nodes']:
            lines.append(f'    <node id="{node["id"]}"/>')
        
        # Add edges
        for i, edge in enumerate(graph_data['edges']):
            lines.append(f'    <edge id="e{i}" source="{edge["source"]}" target="{edge["target"]}"/>')
        
        lines.append('  </graph>')
        lines.append('</graphml>')
        
        with open(path, 'w') as f:
            f.write('\n'.join(lines))
    
    def analyze_network_metrics(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate basic network metrics without external dependencies.
        
        For advanced metrics, NetworkX integration would be needed.
        """
        nodes = graph_data['nodes']
        edges = graph_data['edges']
        
        # Calculate degree for each node
        degree = defaultdict(int)
        for edge in edges:
            degree[edge['source']] += 1
            degree[edge['target']] += 1
        
        # Basic metrics
        metrics = {
            'num_nodes': len(nodes),
            'num_edges': len(edges),
            'density': 2 * len(edges) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0,
            'avg_degree': sum(degree.values()) / len(nodes) if nodes else 0,
            'max_degree': max(degree.values()) if degree else 0,
            'min_degree': min(degree.values()) if degree else 0,
            'isolated_nodes': sum(1 for n in nodes if n['id'] not in degree)
        }
        
        # Find most connected nodes
        if degree:
            sorted_nodes = sorted(degree.items(), key=lambda x: x[1], reverse=True)
            metrics['most_connected'] = sorted_nodes[:10]
        
        return metrics


# Optional: NetworkX-enhanced version (requires networkx)
class NetworkXAnalyzer(NetworkAnalyzer):
    """
    Enhanced network analyzer using NetworkX for advanced metrics.
    
    This is optional and only loaded if NetworkX is installed.
    """
    
    @property
    def name(self) -> str:
        return "networkx_analyzer"
    
    @property
    def requires(self) -> List[str]:
        return ["networkx", "matplotlib"]  # Optional dependencies
    
    def analyze_advanced_metrics(self, graph_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate advanced network metrics using NetworkX.
        
        Includes centrality measures, clustering, communities, etc.
        """
        try:
            import networkx as nx
            
            # Convert to NetworkX graph
            G = nx.Graph() if not graph_data.get('directed') else nx.DiGraph()
            
            for node in graph_data['nodes']:
                G.add_node(node['id'], **node)
            
            for edge in graph_data['edges']:
                G.add_edge(edge['source'], edge['target'], 
                          weight=edge.get('weight', 1))
            
            # Calculate advanced metrics
            metrics = {
                'basic': {
                    'num_nodes': G.number_of_nodes(),
                    'num_edges': G.number_of_edges(),
                    'density': nx.density(G),
                    'is_connected': nx.is_connected(G) if not G.is_directed() else nx.is_weakly_connected(G),
                    'num_components': nx.number_connected_components(G) if not G.is_directed() else nx.number_weakly_connected_components(G)
                },
                'centrality': {
                    'degree': dict(nx.degree_centrality(G)),
                    'betweenness': dict(nx.betweenness_centrality(G)),
                    'closeness': dict(nx.closeness_centrality(G)),
                    'eigenvector': dict(nx.eigenvector_centrality(G, max_iter=100)) if not G.is_directed() else {}
                },
                'clustering': {
                    'avg_clustering': nx.average_clustering(G) if not G.is_directed() else 0,
                    'transitivity': nx.transitivity(G)
                }
            }
            
            # Find communities (for undirected graphs)
            if not G.is_directed():
                import networkx.algorithms.community as nx_comm
                communities = list(nx_comm.greedy_modularity_communities(G))
                metrics['communities'] = {
                    'num_communities': len(communities),
                    'modularity': nx_comm.modularity(G, communities),
                    'sizes': [len(c) for c in communities]
                }
            
            return metrics
            
        except ImportError:
            # NetworkX not installed, fall back to basic metrics
            return self.analyze_network_metrics(graph_data)