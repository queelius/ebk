"""Tests for the VFS REST API endpoints."""

import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from ebk.server import app, set_library
from ebk.library_db import Library


@pytest.fixture
def temp_library():
    """Create a temporary library for testing."""
    temp_dir = tempfile.mkdtemp()
    lib = Library.open(Path(temp_dir))
    yield lib
    lib.close()
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def test_library(temp_library):
    """Create a test library with sample data."""
    lib = temp_library

    # Create test files and add books
    test_file1 = lib.library_path / "test_book.txt"
    test_file1.write_text("Content for Test Book")
    lib.add_book(test_file1, metadata={
        "title": "Test Book",
        "creators": ["Test Author"],
        "description": "A test book description",
        "subjects": ["Testing", "Python"],
        "language": "en",
    }, extract_text=False, extract_cover=False)

    test_file2 = lib.library_path / "another_book.txt"
    test_file2.write_text("Content for Another Book")
    lib.add_book(test_file2, metadata={
        "title": "Another Book",
        "creators": ["Another Author", "Co-Author"],
        "description": "Another test book",
        "subjects": ["Fiction"],
        "language": "en",
    }, extract_text=False, extract_cover=False)

    return lib


@pytest.fixture
def client(test_library):
    """Create a test client with the library initialized."""
    set_library(test_library)
    return TestClient(app)


class TestVFSRoot:
    """Tests for the VFS root endpoint."""

    def test_get_root(self, client):
        """Test getting the VFS root directory."""
        response = client.get("/api/vfs/")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] == "directory"
        assert data["path"] == "/"
        assert "children" in data

        # Should have standard top-level directories
        child_names = [c["name"] for c in data["children"]]
        assert "books" in child_names
        assert "authors" in child_names

    def test_root_children_are_virtual(self, client):
        """Test that root children are virtual directories."""
        response = client.get("/api/vfs/")
        data = response.json()

        for child in data["children"]:
            assert child["type"] in ("directory", "virtual")


class TestVFSBooks:
    """Tests for the VFS /books/ endpoints."""

    def test_list_books(self, client):
        """Test listing books directory."""
        response = client.get("/api/vfs/books")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] in ("directory", "virtual")
        assert len(data["children"]) == 2  # Two test books

    def test_get_book_directory(self, client):
        """Test getting a specific book directory."""
        response = client.get("/api/vfs/books/1")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] == "directory"

        # Should have standard book children
        child_names = [c["name"] for c in data["children"]]
        assert "title" in child_names
        assert "authors" in child_names

    def test_read_book_title(self, client):
        """Test reading a book's title file."""
        response = client.get("/api/vfs/books/1/title")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] == "file"
        assert data["content"] == "Test Book"

    def test_read_book_authors(self, client):
        """Test reading a book's authors file."""
        response = client.get("/api/vfs/books/1/authors")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] == "file"
        assert "Test Author" in data["content"]

    def test_book_not_found(self, client):
        """Test 404 for non-existent book."""
        response = client.get("/api/vfs/books/999")
        assert response.status_code == 404


class TestVFSAuthors:
    """Tests for the VFS /authors/ endpoints."""

    def test_list_authors(self, client):
        """Test listing authors directory."""
        response = client.get("/api/vfs/authors")
        assert response.status_code == 200

        data = response.json()
        assert data["type"] in ("directory", "virtual")
        # Should have at least our test authors
        assert len(data["children"]) >= 1


class TestVFSChildrenInline:
    """Tests for children returned inline with directory responses."""

    def test_directory_includes_children(self, client):
        """Test that directory responses include children."""
        response = client.get("/api/vfs/books")
        assert response.status_code == 200

        data = response.json()
        assert "children" in data
        assert data["children_count"] == len(data["children"])

    def test_file_has_no_children(self, client):
        """Test that file responses don't have children."""
        response = client.get("/api/vfs/books/1/title")
        assert response.status_code == 200

        data = response.json()
        assert "children" not in data or data.get("children") is None


class TestVFSOptions:
    """Tests for VFS query options."""

    def test_follow_symlinks_option(self, client):
        """Test the follow_symlinks option."""
        # This tests the API accepts the parameter
        response = client.get("/api/vfs/books/1?follow_symlinks=false")
        assert response.status_code == 200

    def test_include_content_option(self, client):
        """Test the include_content option."""
        response = client.get("/api/vfs/books/1/title?include_content=false")
        assert response.status_code == 200

        data = response.json()
        # Content should be empty when include_content=false
        assert data["content"] == ""


class TestVFSPathNormalization:
    """Tests for path normalization."""

    def test_path_with_trailing_slash(self, client):
        """Test paths with trailing slashes."""
        response1 = client.get("/api/vfs/books/")
        response2 = client.get("/api/vfs/books")

        assert response1.status_code == 200
        assert response2.status_code == 200

        # Should return equivalent data
        assert response1.json()["path"] == response2.json()["path"]

    def test_path_without_leading_slash(self, client):
        """Test paths without leading slashes (handled by router)."""
        response = client.get("/api/vfs/books")
        assert response.status_code == 200
