"""
Tests for advanced features in the fluent API.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import json
import os

from ebk.library import Library


@pytest.fixture
def rich_library():
    """Create a library with diverse entries for testing advanced features."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.create(temp_dir)
    
    # Add diverse entries
    entries = [
        {
            "title": "Python Programming",
            "creators": ["John Doe", "Jane Smith"],
            "subjects": ["Programming", "Programming/Python", "Education"],
            "language": "en",
            "date": "2020-01-01",
            "rating": 4.5
        },
        {
            "title": "Advanced Python",
            "creators": ["John Doe"],
            "subjects": ["Programming/Python", "Programming/Python/Advanced"],
            "language": "en",
            "date": "2021-01-01",
            "rating": 4.8
        },
        {
            "title": "Django Web Development",
            "creators": ["Jane Smith", "Bob Wilson"],
            "subjects": ["Programming/Python/Web", "Web Development"],
            "language": "en",
            "date": "2021-06-15",
            "rating": 4.2
        },
        {
            "title": "Machine Learning with Python",
            "creators": ["Alice Brown"],
            "subjects": ["Programming/Python", "AI/Machine Learning", "Data Science"],
            "language": "en",
            "date": "2022-01-01",
            "rating": 4.7
        },
        {
            "title": "JavaScript Basics",
            "creators": ["Bob Wilson"],
            "subjects": ["Programming/JavaScript", "Web Development"],
            "language": "en",
            "date": "2020-06-01",
            "rating": 3.9
        },
        {
            "title": "Programmation Python",
            "creators": ["Pierre Dupont"],
            "subjects": ["Programming/Python", "Education"],
            "language": "fr",
            "date": "2021-09-10",
            "rating": 4.1
        },
        {
            "title": "Data Science Handbook",
            "creators": ["Alice Brown", "John Doe"],
            "subjects": ["Data Science", "Programming/Python", "Statistics"],
            "language": "en",
            "date": "2022-03-20",
            "rating": 4.6
        }
    ]
    
    for entry in entries:
        lib.add_entry(**entry)
    
    lib.save()
    
    yield lib
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestSimilarityAndRecommendations:
    """Test similarity and recommendation features."""
    
    def test_find_similar_by_id(self, rich_library):
        # Find entry about Python
        python_book = rich_library.find_by_title("Python Programming")[0]
        
        # Find similar books
        similar = rich_library.find_similar(python_book.id, threshold=0.5)
        
        # Should find other Python books
        assert len(similar) > 0
        titles = [e.title for e in similar]
        assert "Advanced Python" in titles
        # Note: "Programmation Python" may not be included due to language difference
    
    def test_find_similar_by_entry(self, rich_library):
        # Find by Entry object
        entry = rich_library[0]
        similar = rich_library.find_similar(entry, threshold=0.3)
        
        assert len(similar) > 0
        assert all(isinstance(e, type(entry)) for e in similar)
    
    def test_find_similar_threshold(self, rich_library):
        entry_id = rich_library[0].id
        
        # Higher threshold = fewer results
        similar_high = rich_library.find_similar(entry_id, threshold=0.8)
        similar_low = rich_library.find_similar(entry_id, threshold=0.3)
        
        assert len(similar_low) >= len(similar_high)
    
    def test_recommend_random(self, rich_library):
        # Get random recommendations
        recommendations = rich_library.recommend(limit=3)
        
        assert len(recommendations) <= 3
        assert all(hasattr(e, 'title') for e in recommendations)
    
    def test_recommend_based_on(self, rich_library):
        # Get Python books
        python_books = rich_library.search("Python")
        python_ids = [b.id for b in python_books[:2]]
        
        # Get recommendations based on Python books
        recommendations = rich_library.recommend(based_on=python_ids, limit=5)
        
        assert len(recommendations) > 0
        # Should recommend other programming or data science books
        subjects = []
        for r in recommendations:
            subjects.extend(r.subjects)
        
        assert any("Programming" in s or "Data Science" in s for s in subjects)


class TestAnalysis:
    """Test analysis and statistics features."""
    
    def test_analyze_reading_patterns(self, rich_library):
        analysis = rich_library.analyze_reading_patterns()
        
        # Check basic structure
        assert "basic_stats" in analysis
        assert "reading_diversity" in analysis
        
        # Check diversity metrics
        diversity = analysis["reading_diversity"]
        assert "subject_entropy" in diversity
        assert diversity["subject_entropy"] > 0  # Should have some diversity
        
        assert "authors_per_book" in diversity
        assert "books_per_author" in diversity
        
        # Check temporal analysis
        assert "temporal_distribution" in analysis
        temporal = analysis["temporal_distribution"]
        assert "years" in temporal
        assert temporal["oldest_year"] == 2020
        assert temporal["newest_year"] == 2022


class TestSymlinkDAGExport:
    """Test symlink DAG export functionality."""
    
    def test_basic_symlink_export(self, rich_library):
        with tempfile.TemporaryDirectory() as output_dir:
            rich_library.export_to_symlink_dag(output_dir)
            
            output_path = Path(output_dir)
            
            # Check basic structure
            assert (output_path / "_books").exists()
            assert (output_path / "README.md").exists()
            assert (output_path / "Programming").exists()
            
            # Check hierarchical structure
            assert (output_path / "Programming" / "Python").exists()
            assert (output_path / "Programming" / "Python" / "Web").exists()
    
    def test_symlink_with_different_field(self, rich_library):
        with tempfile.TemporaryDirectory() as output_dir:
            # Organize by creators instead of subjects
            rich_library.export_to_symlink_dag(
                output_dir,
                tag_field="creators"
            )
            
            output_path = Path(output_dir)
            
            # Should have creator directories
            assert (output_path / "John Doe").exists()
            assert (output_path / "Jane Smith").exists()
    
    def test_symlink_without_files(self, rich_library):
        with tempfile.TemporaryDirectory() as output_dir:
            rich_library.export_to_symlink_dag(
                output_dir,
                include_files=False
            )
            
            output_path = Path(output_dir)
            
            # Should still have structure but no file copies
            assert (output_path / "_books").exists()
            assert (output_path / "Programming").exists()
            
            # Check that metadata exists but no ebook files
            books_dir = output_path / "_books"
            for book_dir in books_dir.iterdir():
                if book_dir.is_dir():
                    assert (book_dir / "metadata.json").exists()
    
    def test_symlink_html_indexes(self, rich_library):
        with tempfile.TemporaryDirectory() as output_dir:
            rich_library.export_to_symlink_dag(
                output_dir,
                create_index=True
            )
            
            output_path = Path(output_dir)
            
            # Check index files exist
            assert (output_path / "index.html").exists()
            assert (output_path / "Programming" / "index.html").exists()
            assert (output_path / "Programming" / "Python" / "index.html").exists()
            
            # Check index content
            with open(output_path / "Programming" / "Python" / "index.html") as f:
                content = f.read()
                assert "Python" in content
                assert "Subcategories" in content or "Books" in content

# Graph export tests moved to test_integrations.py
# since graph functionality is now a plugin

class TestMethodChaining:
    """Test that new methods support proper chaining."""
    
    def test_export_chaining(self, rich_library):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Should be able to chain exports
            result = (rich_library
                     .filter(lambda e: e.get("language") == "en")
                     .export_to_symlink_dag(Path(temp_dir) / "english"))
            
            # Result should be a Library instance
            assert isinstance(result, Library)
    
    def test_complex_chaining(self, rich_library):
        # Complex chain of operations
        with tempfile.TemporaryDirectory() as temp_dir:
            result = (rich_library
                     .filter(lambda e: "Python" in str(e.get("subjects", [])))
                     .tag_all("python-book")
                     .export_to_symlink_dag(Path(temp_dir) / "python-books"))
            
            assert isinstance(result, Library)


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_find_similar_nonexistent_id(self, rich_library):
        similar = rich_library.find_similar("nonexistent-id")
        assert similar == []
    
    def test_recommend_empty_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_lib = Library.create(temp_dir)
            recommendations = empty_lib.recommend()
            assert recommendations == []
    
    def test_analyze_empty_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_lib = Library.create(temp_dir)
            analysis = empty_lib.analyze_reading_patterns()
            
            assert analysis["basic_stats"]["total_entries"] == 0
            assert analysis["reading_diversity"] == {}