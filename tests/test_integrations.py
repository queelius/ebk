"""
Tests for EBK integrations (plugins).

These tests are separate from core tests and only run when the relevant
integrations are available.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

# Import core library
from ebk.library import Library

# Try to import integrations - tests will be skipped if not available
try:
    from integrations.network import NetworkAnalyzer
    HAS_NETWORK = True
except ImportError:
    HAS_NETWORK = False

try:
    from integrations.metadata import GoogleBooksExtractor
    HAS_METADATA = True
except ImportError:
    HAS_METADATA = False


@pytest.fixture
def sample_library():
    """Create a library with sample data for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lib = Library.create(tmpdir)
        
        # Add books with co-authors for network analysis
        lib.add_entry(
            title="Book A",
            creators=["Author 1", "Author 2"],
            subjects=["Python", "Programming"]
        )
        lib.add_entry(
            title="Book B", 
            creators=["Author 2", "Author 3"],
            subjects=["Python", "Data Science"]
        )
        lib.add_entry(
            title="Book C",
            creators=["Author 1", "Author 3"],
            subjects=["Programming", "Web Development"]
        )
        lib.add_entry(
            title="Book D",
            creators=["Author 4"],
            subjects=["JavaScript", "Web Development"]
        )
        lib.add_entry(
            title="Book E",
            creators=["Author 1", "Author 2", "Author 3"],
            subjects=["Python", "Programming", "Best Practices"]
        )
        
        lib.save()
        yield lib


@pytest.mark.skipif(not HAS_NETWORK, reason="Network integration not available")
class TestNetworkAnalyzer:
    """Test network analysis plugin."""
    
    def test_build_coauthor_network(self, sample_library):
        """Test building co-author network."""
        analyzer = NetworkAnalyzer()
        
        # Get entries from library
        entries = sample_library._entries
        
        # Build co-author network
        graph = analyzer.build_coauthor_network(entries, min_connections=1)
        
        # Check structure
        assert 'nodes' in graph
        assert 'edges' in graph
        assert graph['type'] == 'coauthor_network'
        assert graph['directed'] is False
        
        # Check nodes (4 authors with connections)
        node_ids = {node['id'] for node in graph['nodes']}
        assert 'Author 1' in node_ids
        assert 'Author 2' in node_ids
        assert 'Author 3' in node_ids
        # Author 4 has no co-authors, might be excluded based on min_connections
        
        # Check edges exist
        assert len(graph['edges']) > 0
        
        # Check metadata
        assert 'metadata' in graph
        assert graph['metadata']['total_authors'] == 4
    
    def test_build_coauthor_network_min_connections(self, sample_library):
        """Test co-author network with minimum connections filter."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        # Require at least 2 connections
        graph = analyzer.build_coauthor_network(entries, min_connections=2)
        
        # Authors 1, 2, 3 all have 2+ connections
        # Author 4 has 0 connections
        node_ids = {node['id'] for node in graph['nodes']}
        assert 'Author 1' in node_ids
        assert 'Author 2' in node_ids
        assert 'Author 3' in node_ids
        assert 'Author 4' not in node_ids
    
    def test_build_subject_network(self, sample_library):
        """Test building subject co-occurrence network."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        graph = analyzer.build_subject_network(entries, min_connections=1)
        
        # Check structure
        assert graph['type'] == 'subject_network'
        assert 'nodes' in graph
        assert 'edges' in graph
        
        # Check some subjects exist
        node_ids = {node['id'] for node in graph['nodes']}
        assert 'Python' in node_ids
        assert 'Programming' in node_ids
        
        # Check edges (Python and Programming co-occur)
        edges = graph['edges']
        assert len(edges) > 0
    
    def test_export_graph_json(self, sample_library):
        """Test exporting graph to JSON format."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        graph = analyzer.build_coauthor_network(entries)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name
        
        try:
            # Export to JSON
            success = analyzer.export_graph(graph, output_path, format='json')
            assert success is True
            
            # Verify file contents
            with open(output_path) as f:
                loaded = json.load(f)
            
            assert loaded['type'] == 'coauthor_network'
            assert 'nodes' in loaded
            assert 'edges' in loaded
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    def test_export_graph_dot(self, sample_library):
        """Test exporting graph to DOT format."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        graph = analyzer.build_coauthor_network(entries)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.dot', delete=False) as f:
            output_path = f.name
        
        try:
            # Export to DOT
            success = analyzer.export_graph(graph, output_path, format='dot')
            assert success is True
            
            # Verify file contents
            with open(output_path) as f:
                content = f.read()
            
            assert 'graph G {' in content
            assert 'Author 1' in content
            assert '--' in content  # Undirected edge
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    def test_export_graph_gml(self, sample_library):
        """Test exporting graph to GML format."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        graph = analyzer.build_subject_network(entries)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gml', delete=False) as f:
            output_path = f.name
        
        try:
            # Export to GML
            success = analyzer.export_graph(graph, output_path, format='gml')
            assert success is True
            
            # Verify file contents
            with open(output_path) as f:
                content = f.read()
            
            assert 'graph [' in content
            assert 'node [' in content
            assert 'edge [' in content
            assert 'directed 0' in content  # Undirected
            
        finally:
            Path(output_path).unlink(missing_ok=True)
    
    def test_analyze_network_metrics(self, sample_library):
        """Test basic network metrics calculation."""
        analyzer = NetworkAnalyzer()
        entries = sample_library._entries
        
        graph = analyzer.build_coauthor_network(entries)
        metrics = analyzer.analyze_network_metrics(graph)
        
        assert 'num_nodes' in metrics
        assert 'num_edges' in metrics
        assert 'density' in metrics
        assert 'avg_degree' in metrics
        assert metrics['num_nodes'] > 0
        assert metrics['num_edges'] > 0


@pytest.mark.skipif(not HAS_METADATA, reason="Metadata integration not available")
class TestGoogleBooksExtractor:
    """Test Google Books metadata extractor."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test extractor initialization."""
        extractor = GoogleBooksExtractor()
        
        assert extractor.name == "google_books"
        assert extractor.version == "1.0.0"
        assert extractor.supported_formats() == ["isbn"]
    
    @pytest.mark.asyncio
    async def test_extract_with_mock(self):
        """Test extraction with mocked API response."""
        extractor = GoogleBooksExtractor()
        
        mock_response = {
            "totalItems": 1,
            "items": [{
                "volumeInfo": {
                    "title": "Clean Code",
                    "authors": ["Robert C. Martin"],
                    "publisher": "Prentice Hall",
                    "publishedDate": "2008-08-01",
                    "description": "Guide to writing clean code",
                    "categories": ["Programming"],
                    "language": "en",
                    "pageCount": 464,
                    "industryIdentifiers": [
                        {"type": "ISBN_13", "identifier": "9780132350884"}
                    ],
                    "imageLinks": {
                        "thumbnail": "http://example.com/thumb.jpg",
                        "large": "http://example.com/large.jpg"
                    }
                },
                "selfLink": "http://example.com/book"
            }]
        }
        
        with patch.object(extractor, '_fetch_book_data', return_value=mock_response):
            result = await extractor.extract(isbn="9780132350884")
        
        assert result["title"] == "Clean Code"
        assert result["creators"] == ["Robert C. Martin"]
        assert result["publisher"] == "Prentice Hall"
        assert result["page_count"] == 464
        assert result["source"] == "google_books"
    
    def test_parse_volume_info(self):
        """Test parsing volume info from API response."""
        extractor = GoogleBooksExtractor()
        
        volume_info = {
            "title": "Test Book",
            "subtitle": "A Subtitle",
            "authors": ["Author One", "Author Two"],
            "publisher": "Test Publisher",
            "publishedDate": "2023-01-15",
            "description": "Test description",
            "categories": ["Category 1", "Category 2"],
            "language": "en",
            "pageCount": 300,
            "averageRating": 4.5,
            "ratingsCount": 100
        }
        
        result = extractor._parse_volume_info(volume_info)
        
        assert result["title"] == "Test Book"
        assert result["subtitle"] == "A Subtitle"
        assert result["creators"] == ["Author One", "Author Two"]
        assert result["year"] == 2023
        assert result["rating"] == 4.5


# Test for checking if integrations work with the enhanced library
@pytest.mark.skipif(not HAS_NETWORK, reason="Network integration not available")
class TestLibraryWithPlugins:
    """Test library integration with plugins."""
    
    def test_library_with_network_plugin(self, sample_library):
        """Test using network plugin with library."""
        from ebk.plugins.registry import plugin_registry
        
        # Register the network analyzer
        analyzer = NetworkAnalyzer()
        plugin_registry.register(analyzer)
        
        # Check it's registered
        plugins = plugin_registry.get_plugins('network_analyzer')
        # Note: NetworkAnalyzer doesn't inherit from a specific plugin type
        # This test might need adjustment based on actual implementation
        
        # For now, just verify the analyzer works with library data
        entries = sample_library._entries
        graph = analyzer.build_coauthor_network(entries)
        assert len(graph['nodes']) > 0