"""
Tests for the fluent library API.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
import json

from ebk.library import Library, Entry, QueryBuilder


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.create(temp_dir)
    
    # Add some test entries
    lib.add_entry(
        title="Python Programming",
        creators=["John Doe"],
        subjects=["Programming", "Python"],
        language="en",
        date="2020-01-01",
        year="2020"
    )
    
    lib.add_entry(
        title="Data Science Handbook",
        creators=["Jane Smith", "Bob Johnson"],
        subjects=["Data Science", "Python", "Statistics"],
        language="en",
        date="2021-06-15",
        year="2021"
    )
    
    lib.add_entry(
        title="Machine Learning Guide",
        creators=["Alice Brown"],
        subjects=["Machine Learning", "AI"],
        language="en",
        date="2022-03-20",
        year="2022"
    )
    
    lib.add_entry(
        title="Programmation Python",
        creators=["Pierre Dupont"],
        subjects=["Programming", "Python"],
        language="fr",
        date="2021-09-10",
        year="2021"
    )
    
    lib.save()
    
    yield lib
    
    # Cleanup
    shutil.rmtree(temp_dir)


class TestLibraryCreation:
    """Test library creation and opening."""
    
    def test_create_library(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lib = Library.create(temp_dir)
            assert len(lib) == 0
            assert (Path(temp_dir) / "metadata.json").exists()
    
    def test_open_library(self, temp_library):
        lib_path = temp_library.path
        lib2 = Library.open(lib_path)
        assert len(lib2) == 4
    
    def test_open_nonexistent_library(self):
        with pytest.raises(FileNotFoundError):
            Library.open("/nonexistent/path")


class TestQueryBuilder:
    """Test query builder functionality."""
    
    def test_simple_where(self, temp_library):
        results = temp_library.query().where("language", "en").execute()
        assert len(results) == 3
    
    def test_where_with_operators(self, temp_library):
        # Greater than
        results = temp_library.query().where("year", "2020", ">").execute()
        assert len(results) == 3  # 2021 (x2) and 2022
        
        # Contains (for lists)
        results = temp_library.query().where("subjects", "Python", "contains").execute()
        assert len(results) == 3
        
        # Regex
        results = temp_library.query().where("title", "Python|Machine", "regex").execute()
        assert len(results) == 3
    
    def test_where_any(self, temp_library):
        results = temp_library.query().where_any(["title", "subjects"], "Python").execute()
        assert len(results) == 3  # Python Programming, Data Science (subjects), Programmation Python
    
    def test_where_lambda(self, temp_library):
        results = temp_library.query().where_lambda(
            lambda e: len(e.get("creators", [])) > 1
        ).execute()
        assert len(results) == 1
        assert results[0]["title"] == "Data Science Handbook"
    
    def test_order_by(self, temp_library):
        results = temp_library.query().order_by("title").execute()
        assert results[0]["title"] == "Data Science Handbook"
        assert results[-1]["title"] == "Python Programming"
        
        # Descending
        results = temp_library.query().order_by("year", descending=True).execute()
        assert results[0]["year"] == "2022"
    
    def test_skip_take(self, temp_library):
        results = temp_library.query().order_by("title").skip(1).take(2).execute()
        assert len(results) == 2
        assert results[0]["title"] == "Machine Learning Guide"
    
    def test_count(self, temp_library):
        count = temp_library.query().where("language", "en").count()
        assert count == 3
    
    def test_first(self, temp_library):
        entry = temp_library.query().where("language", "fr").first()
        assert entry is not None
        assert entry["title"] == "Programmation Python"
    
    def test_exists(self, temp_library):
        assert temp_library.query().where("language", "fr").exists()
        assert not temp_library.query().where("language", "es").exists()


class TestEntryOperations:
    """Test Entry class operations."""
    
    def test_entry_properties(self, temp_library):
        entry = temp_library[0]
        assert entry.title == "Python Programming"
        assert entry.creators == ["John Doe"]
        assert len(entry.subjects) == 2
    
    def test_entry_setters(self, temp_library):
        entry = temp_library[0]
        entry.title = "Advanced Python Programming"
        assert entry.title == "Advanced Python Programming"
        
        entry.creators = ["John Doe", "Jane Doe"]
        assert len(entry.creators) == 2
    
    def test_entry_chaining(self, temp_library):
        entry = temp_library[0]
        result = (entry
                 .set("edition", "2nd")
                 .add_creator("Jane Doe")
                 .add_subject("Advanced"))
        
        assert result == entry  # Returns self
        assert entry.get("edition") == "2nd"
        assert "Jane Doe" in entry.creators
        assert "Advanced" in entry.subjects
    
    def test_entry_update(self, temp_library):
        entry = temp_library[0]
        entry.update(
            title="New Title",
            publisher="Tech Press",
            year="2023"
        )
        
        assert entry.title == "New Title"
        assert entry.get("publisher") == "Tech Press"
        assert entry.get("year") == "2023"


class TestLibraryModifications:
    """Test library modification operations."""
    
    def test_add_entry(self, temp_library):
        initial_count = len(temp_library)
        
        entry = temp_library.add_entry(
            title="New Book",
            creators=["New Author"],
            language="en"
        )
        
        assert len(temp_library) == initial_count + 1
        assert entry.title == "New Book"
        assert entry.id  # Has unique ID
    
    def test_remove_entry(self, temp_library):
        entry = temp_library[0]
        unique_id = entry.id
        initial_count = len(temp_library)
        
        temp_library.remove(unique_id).save()
        
        assert len(temp_library) == initial_count - 1
        assert temp_library.find(unique_id) is None
    
    def test_remove_where(self, temp_library):
        initial_count = len(temp_library)
        
        temp_library.remove_where(lambda e: e.get("language") == "fr").save()
        
        assert len(temp_library) == initial_count - 1
        assert not any(e.get("language") == "fr" for e in temp_library._entries)
    
    def test_update_all(self, temp_library):
        temp_library.update_all(lambda e: e.set("reviewed", True)).save()
        
        for entry in temp_library:
            assert entry.get("reviewed") is True
    
    def test_tag_operations(self, temp_library):
        # Add tag
        temp_library.tag_all("ebook").save()
        for entry in temp_library:
            assert "ebook" in entry.subjects
        
        # Remove tag
        temp_library.untag_all("ebook").save()
        for entry in temp_library:
            assert "ebook" not in entry.subjects


class TestSearchMethods:
    """Test various search methods."""
    
    def test_find_by_id(self, temp_library):
        entry = temp_library[0]
        found = temp_library.find(entry.id)
        assert found is not None
        assert found.title == entry.title
    
    def test_find_by_title(self, temp_library):
        results = temp_library.find_by_title("Python Programming")
        assert len(results) == 1
        assert results[0].creators == ["John Doe"]
    
    def test_search(self, temp_library):
        # Search in default fields
        results = temp_library.search("Python")
        assert len(results) >= 2
        
        # Search in specific fields
        results = temp_library.search("John", fields=["creators"])
        assert len(results) == 2  # John Doe and Bob Johnson
        # Check that Python Programming is in results
        titles = [r.title for r in results]
        assert "Python Programming" in titles
    
    def test_filter(self, temp_library):
        filtered = temp_library.filter(lambda e: e.get("year") > "2020")
        assert len(filtered) == 3  # 2021 (x2) and 2022
        assert isinstance(filtered, Library)


class TestStatistics:
    """Test statistics and analysis methods."""
    
    def test_stats(self, temp_library):
        stats = temp_library.stats()
        
        assert stats['total_entries'] == 4
        assert stats['languages']['en'] == 3
        assert stats['languages']['fr'] == 1
        assert stats['years']['2021'] == 2
        assert stats['creators']['John Doe'] == 1
        assert 'Python' in stats['subjects']
    
    def test_group_by(self, temp_library):
        # Group by single value field
        by_language = temp_library.group_by("language")
        assert len(by_language['en']) == 3
        assert len(by_language['fr']) == 1
        
        # Group by list field
        by_subject = temp_library.group_by("subjects")
        assert len(by_subject['Python']) == 3  # Python Programming, Data Science, Programmation Python
    
    def test_duplicates(self, temp_library):
        # Add duplicate
        temp_library.add_entry(
            title="Python Programming",
            creators=["Another Author"],
            language="en"
        )
        
        duplicates = temp_library.duplicates(by="title")
        assert len(duplicates) == 1
        assert duplicates[0][0] == "Python Programming"
        assert len(duplicates[0][1]) == 2


class TestBatchOperations:
    """Test batch operations."""
    
    def test_batch_operations(self, temp_library):
        initial_count = len(temp_library)
        
        (temp_library.batch()
         .add_entry(title="Book 1", creators=["Author 1"])
         .add_entry(title="Book 2", creators=["Author 2"])
         .remove(temp_library[0].id)
         .execute())
        
        assert len(temp_library) == initial_count + 1  # +2 -1


class TestTransactions:
    """Test transaction support."""
    
    def test_transaction_commit(self, temp_library):
        initial_count = len(temp_library)
        
        with temp_library.transaction() as lib:
            lib.add_entry(title="Transaction Book", creators=["TX Author"])
        
        # Changes should be committed
        assert len(temp_library) == initial_count + 1
    
    def test_transaction_rollback(self, temp_library):
        initial_count = len(temp_library)
        
        try:
            with temp_library.transaction() as lib:
                lib.add_entry(title="Transaction Book", creators=["TX Author"])
                raise Exception("Simulated error")
        except:
            pass
        
        # Changes should be rolled back
        assert len(temp_library) == initial_count


class TestMergeOperations:
    """Test library merge operations."""
    
    def test_union(self, temp_library):
        # Create second library
        with tempfile.TemporaryDirectory() as temp_dir2:
            lib2 = Library.create(temp_dir2)
            lib2.add_entry(title="Book in Lib2", creators=["Lib2 Author"])
            lib2.add_entry(title="Python Programming", creators=["John Doe"])  # Duplicate
            lib2.save()
            
            # Union
            merged = temp_library.union(lib2)
            assert len(merged) == 6  # 4 + 2 (union may not remove duplicates)


class TestExportOperations:
    """Test export operations."""
    
    def test_export_to_zip(self, temp_library):
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as temp_file:
            temp_library.export_to_zip(temp_file.name)
            assert Path(temp_file.name).exists()
            Path(temp_file.name).unlink()  # Cleanup


if __name__ == "__main__":
    pytest.main([__file__])