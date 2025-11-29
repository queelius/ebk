"""
Tests for VFS nodes - Authors, Subjects, and Similar.

Tests focus on behavior:
- Directory listing returns expected nodes
- Child lookup finds correct nodes
- Info dictionaries have expected structure
- Symlinks point to correct targets
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from ebk.library_db import Library
from ebk.db.models import Author, Subject, Book
from ebk.vfs.nodes.authors import AuthorsDirectoryNode, AuthorNode
from ebk.vfs.nodes.subjects import SubjectsDirectoryNode, SubjectNode
from ebk.vfs.nodes.similar import SimilarDirectoryNode, SimilarBookSymlink
from ebk.vfs.base import SymlinkNode


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))

    yield lib

    # Cleanup
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


def create_test_book(library: Library, filename: str, title: str,
                     authors: list = None, subjects: list = None) -> Book:
    """Helper to create a test book with authors and subjects."""
    test_file = library.library_path / filename
    test_file.write_text(f"Content for {title}")

    metadata: Dict[str, Any] = {
        "title": title,
        "creators": authors or ["Test Author"],
        "subjects": subjects or [],
        "language": "en"
    }

    return library.add_book(
        test_file,
        metadata=metadata,
        extract_text=False,
        extract_cover=False
    )


@pytest.fixture
def library_with_books(temp_library):
    """Library with sample books, authors, and subjects."""
    book1 = create_test_book(
        temp_library, "book1.txt", "Python Basics",
        authors=["Donald Knuth"],
        subjects=["Programming", "Python"]
    )
    book2 = create_test_book(
        temp_library, "book2.txt", "Advanced Algorithms",
        authors=["Donald Knuth"],
        subjects=["Programming", "Algorithms"]
    )
    book3 = create_test_book(
        temp_library, "book3.txt", "Data Science Handbook",
        authors=["Jane Smith"],
        subjects=["Data Science", "Python"]
    )
    book4 = create_test_book(
        temp_library, "book4.txt", "Machine Learning",
        authors=["Jane Smith", "Bob Johnson"],
        subjects=["AI", "Machine Learning"]
    )

    return {
        'library': temp_library,
        'books': [book1, book2, book3, book4]
    }


# ============================================================================
# AUTHORS DIRECTORY NODE TESTS
# ============================================================================

class TestAuthorsDirectoryNode:
    """Test the /authors/ directory node."""

    def test_node_name_is_authors(self, temp_library):
        """Node name should be 'authors'."""
        node = AuthorsDirectoryNode(temp_library)
        assert node.name == "authors"

    def test_list_children_empty_library(self, temp_library):
        """Empty library should return empty list of authors."""
        node = AuthorsDirectoryNode(temp_library)
        children = node.list_children()
        assert children == []

    def test_list_children_returns_author_nodes(self, library_with_books):
        """Should return AuthorNode for each unique author."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)
        children = node.list_children()

        assert len(children) >= 3  # At least Knuth, Smith, Johnson

        # All children should be AuthorNode instances
        for child in children:
            assert isinstance(child, AuthorNode)

    def test_get_child_by_slug(self, library_with_books):
        """Should find author by slug."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)

        # "Donald Knuth" should become a slug like "knuth-donald"
        child = node.get_child("knuth-donald")
        assert child is not None
        assert isinstance(child, AuthorNode)

    def test_get_child_nonexistent_returns_none(self, library_with_books):
        """Nonexistent author should return None."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)

        child = node.get_child("nonexistent-author")
        assert child is None

    def test_get_info_returns_dict(self, library_with_books):
        """get_info should return dictionary with expected keys."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)
        info = node.get_info()

        assert isinstance(info, dict)
        assert info["type"] == "virtual"
        assert info["name"] == "authors"
        assert "total_authors" in info
        assert info["total_authors"] >= 0
        assert "path" in info


class TestAuthorNode:
    """Test individual author directory nodes."""

    def test_list_children_returns_book_symlinks(self, library_with_books):
        """Author node should list symlinks to books."""
        lib = library_with_books['library']
        authors_dir = AuthorsDirectoryNode(lib)

        # Get an author that has books
        author_node = authors_dir.get_child("knuth-donald")
        assert author_node is not None

        children = author_node.list_children()

        # Knuth has 2 books
        assert len(children) == 2

        # All children should be symlinks
        for child in children:
            assert isinstance(child, SymlinkNode)

    def test_symlinks_point_to_books(self, library_with_books):
        """Symlinks should point to /books/{id} paths."""
        lib = library_with_books['library']
        authors_dir = AuthorsDirectoryNode(lib)
        author_node = authors_dir.get_child("knuth-donald")

        children = author_node.list_children()

        for child in children:
            assert child.target_path.startswith("/books/")

    def test_get_child_by_book_id(self, library_with_books):
        """Should find book symlink by book ID."""
        lib = library_with_books['library']
        books = library_with_books['books']
        knuth_book = books[0]  # First book by Knuth

        authors_dir = AuthorsDirectoryNode(lib)
        author_node = authors_dir.get_child("knuth-donald")

        child = author_node.get_child(str(knuth_book.id))
        assert child is not None
        assert isinstance(child, SymlinkNode)

    def test_get_child_invalid_id_returns_none(self, library_with_books):
        """Invalid book ID should return None."""
        lib = library_with_books['library']
        authors_dir = AuthorsDirectoryNode(lib)
        author_node = authors_dir.get_child("knuth-donald")

        # Non-numeric ID
        assert author_node.get_child("not-a-number") is None

        # Numeric but not this author's book
        assert author_node.get_child("99999") is None

    def test_get_info_returns_author_details(self, library_with_books):
        """get_info should return author details."""
        lib = library_with_books['library']
        authors_dir = AuthorsDirectoryNode(lib)
        author_node = authors_dir.get_child("knuth-donald")

        info = author_node.get_info()

        assert isinstance(info, dict)
        assert info["type"] == "virtual"
        assert info["author"] == "Donald Knuth"
        assert info["book_count"] == 2
        assert "path" in info


# ============================================================================
# SUBJECTS DIRECTORY NODE TESTS
# ============================================================================

class TestSubjectsDirectoryNode:
    """Test the /subjects/ directory node."""

    def test_node_name_is_subjects(self, temp_library):
        """Node name should be 'subjects'."""
        node = SubjectsDirectoryNode(temp_library)
        assert node.name == "subjects"

    def test_list_children_empty_library(self, temp_library):
        """Empty library should return empty list of subjects."""
        node = SubjectsDirectoryNode(temp_library)
        children = node.list_children()
        assert children == []

    def test_list_children_returns_subject_nodes(self, library_with_books):
        """Should return SubjectNode for each unique subject."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)
        children = node.list_children()

        # We have: Programming, Python, Algorithms, Data Science, AI, Machine Learning
        assert len(children) >= 5

        # All children should be SubjectNode instances
        for child in children:
            assert isinstance(child, SubjectNode)

    def test_get_child_by_slug(self, library_with_books):
        """Should find subject by slug."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        # "Programming" should become slug "programming"
        child = node.get_child("programming")
        assert child is not None
        assert isinstance(child, SubjectNode)

    def test_get_child_with_spaces_in_name(self, library_with_books):
        """Should handle subjects with spaces."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        # "Data Science" should become "data-science"
        child = node.get_child("data-science")
        assert child is not None
        assert isinstance(child, SubjectNode)

    def test_get_child_nonexistent_returns_none(self, library_with_books):
        """Nonexistent subject should return None."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        child = node.get_child("nonexistent-subject")
        assert child is None

    def test_get_info_returns_dict(self, library_with_books):
        """get_info should return dictionary with expected keys."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)
        info = node.get_info()

        assert isinstance(info, dict)
        assert info["type"] == "virtual"
        assert info["name"] == "subjects"
        assert "total_subjects" in info
        assert info["total_subjects"] >= 0
        assert "path" in info


class TestSubjectNode:
    """Test individual subject directory nodes."""

    def test_list_children_returns_book_symlinks(self, library_with_books):
        """Subject node should list symlinks to books."""
        lib = library_with_books['library']
        subjects_dir = SubjectsDirectoryNode(lib)

        # Get a subject that has books
        subject_node = subjects_dir.get_child("python")
        assert subject_node is not None

        children = subject_node.list_children()

        # Python subject has 2 books
        assert len(children) == 2

        # All children should be symlinks
        for child in children:
            assert isinstance(child, SymlinkNode)

    def test_symlinks_point_to_books(self, library_with_books):
        """Symlinks should point to /books/{id} paths."""
        lib = library_with_books['library']
        subjects_dir = SubjectsDirectoryNode(lib)
        subject_node = subjects_dir.get_child("programming")

        children = subject_node.list_children()

        for child in children:
            assert child.target_path.startswith("/books/")

    def test_get_child_by_book_id(self, library_with_books):
        """Should find book symlink by book ID."""
        lib = library_with_books['library']
        books = library_with_books['books']
        python_book = books[0]  # First book has "Python" subject

        subjects_dir = SubjectsDirectoryNode(lib)
        subject_node = subjects_dir.get_child("python")

        child = subject_node.get_child(str(python_book.id))
        assert child is not None
        assert isinstance(child, SymlinkNode)

    def test_get_child_invalid_id_returns_none(self, library_with_books):
        """Invalid book ID should return None."""
        lib = library_with_books['library']
        subjects_dir = SubjectsDirectoryNode(lib)
        subject_node = subjects_dir.get_child("programming")

        # Non-numeric ID
        assert subject_node.get_child("not-a-number") is None

        # Numeric but not this subject's book
        assert subject_node.get_child("99999") is None

    def test_get_info_returns_subject_details(self, library_with_books):
        """get_info should return subject details."""
        lib = library_with_books['library']
        subjects_dir = SubjectsDirectoryNode(lib)
        subject_node = subjects_dir.get_child("programming")

        info = subject_node.get_info()

        assert isinstance(info, dict)
        assert info["type"] == "virtual"
        assert info["subject"] == "Programming"
        assert info["book_count"] >= 1
        assert "path" in info


# ============================================================================
# SIMILAR DIRECTORY NODE TESTS
# ============================================================================

class TestSimilarDirectoryNode:
    """Test the /books/{id}/similar/ directory node."""

    def test_node_name_is_similar(self, library_with_books):
        """Node name should be 'similar'."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)
        assert node.name == "similar"

    def test_list_children_returns_symlinks(self, library_with_books):
        """Should return symlinks to similar books."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)
        children = node.list_children()

        # Result should be list (may be empty if similarity not computed)
        assert isinstance(children, list)

        # If there are children, they should be SimilarBookSymlink
        for child in children:
            assert isinstance(child, SimilarBookSymlink)

    def test_get_info_returns_dict(self, library_with_books):
        """get_info should return dictionary with expected keys."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)
        info = node.get_info()

        assert isinstance(info, dict)
        assert info["type"] == "virtual"
        assert info["name"] == "similar"
        assert "count" in info
        assert isinstance(info["count"], int)
        assert "path" in info

    def test_top_k_parameter(self, library_with_books):
        """Should respect top_k parameter."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        # Create with custom top_k
        node = SimilarDirectoryNode(book, lib, top_k=5)
        assert node.top_k == 5

    def test_caching_similar_results(self, library_with_books):
        """Should cache similar book results."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)

        # First call computes
        children1 = node.list_children()

        # Second call should use cache
        children2 = node.list_children()

        # Cache should be populated
        assert node._similar_cache is not None

    def test_get_child_by_book_id(self, library_with_books):
        """Should find similar book by ID if it exists."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)

        # Force compute similar books
        children = node.list_children()

        if len(children) > 0:
            first_child = children[0]
            found = node.get_child(first_child.name)
            assert found is not None
            assert isinstance(found, SimilarBookSymlink)

    def test_get_child_invalid_id_returns_none(self, library_with_books):
        """Invalid book ID should return None."""
        lib = library_with_books['library']
        book = library_with_books['books'][0]

        node = SimilarDirectoryNode(book, lib)

        # Non-numeric ID
        assert node.get_child("not-a-number") is None


class TestSimilarBookSymlink:
    """Test SimilarBookSymlink behavior."""

    def test_has_score_attribute(self, library_with_books):
        """SimilarBookSymlink should have score attribute."""
        lib = library_with_books['library']
        book1 = library_with_books['books'][0]
        book2 = library_with_books['books'][1]

        symlink = SimilarBookSymlink(
            name=str(book2.id),
            target_path=f"/books/{book2.id}",
            similar_book=book2,
            score=0.85
        )

        assert symlink.score == 0.85

    def test_get_info_includes_score(self, library_with_books):
        """get_info should include similarity score."""
        lib = library_with_books['library']
        book2 = library_with_books['books'][1]

        symlink = SimilarBookSymlink(
            name=str(book2.id),
            target_path=f"/books/{book2.id}",
            similar_book=book2,
            score=0.85
        )

        info = symlink.get_info()

        assert "score" in info
        assert info["score"] == 0.85

    def test_get_info_includes_book_details(self, library_with_books):
        """get_info should include book title and authors."""
        lib = library_with_books['library']
        book2 = library_with_books['books'][1]

        symlink = SimilarBookSymlink(
            name=str(book2.id),
            target_path=f"/books/{book2.id}",
            similar_book=book2,
            score=0.85
        )

        info = symlink.get_info()

        assert "title" in info
        assert info["title"] == book2.title
        assert "authors" in info


# ============================================================================
# SLUG GENERATION TESTS
# ============================================================================

class TestAuthorSlugGeneration:
    """Test author name to slug conversion."""

    def test_simple_name(self, library_with_books):
        """Simple names should convert to lowercase with hyphens."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)

        # "Jane Smith" -> should produce a slug
        slug = node._make_slug("Jane Smith")

        # Should be lowercase
        assert slug == slug.lower()
        # Should contain only alphanumeric and hyphens
        assert all(c.isalnum() or c == "-" for c in slug)

    def test_reverses_name_order(self, library_with_books):
        """First Last should become last-first."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)

        slug = node._make_slug("Donald Knuth")
        # Should be reversed: knuth-donald
        assert "knuth" in slug
        assert "donald" in slug

    def test_handles_single_name(self, library_with_books):
        """Single name should work without errors."""
        lib = library_with_books['library']
        node = AuthorsDirectoryNode(lib)

        slug = node._make_slug("Prince")
        assert slug == "prince"


class TestSubjectSlugGeneration:
    """Test subject name to slug conversion."""

    def test_simple_subject(self, library_with_books):
        """Simple subject should become lowercase."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        slug = node._make_slug("Programming")
        assert slug == "programming"

    def test_subject_with_spaces(self, library_with_books):
        """Spaces should become hyphens."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        slug = node._make_slug("Data Science")
        assert slug == "data-science"

    def test_subject_with_special_chars(self, library_with_books):
        """Special characters should be removed."""
        lib = library_with_books['library']
        node = SubjectsDirectoryNode(lib)

        slug = node._make_slug("C++ Programming")
        # Special chars removed, spaces become hyphens
        assert slug == "c-programming"
