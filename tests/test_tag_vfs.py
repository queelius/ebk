"""
Tests for Tag VFS nodes - virtual filesystem representation.

Tests VFS nodes for hierarchical tag browsing:
- TagsDirectoryNode: /tags/ entry point
- TagNode: Individual tag directories
- TagDescriptionFile: Tag description metadata
- TagColorFile: Tag color metadata
- TagStatsFile: Tag statistics metadata
- Book symlinks within tag directories
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from ebk.library_db import Library
from ebk.services.tag_service import TagService
from ebk.vfs.nodes.tags import (
    TagsDirectoryNode,
    TagNode,
    TagDescriptionFile,
    TagColorFile,
    TagStatsFile
)
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


@pytest.fixture
def tag_service(temp_library):
    """Create a TagService instance."""
    return TagService(temp_library.session)


@pytest.fixture
def sample_hierarchy(tag_service, temp_library):
    """Create a sample tag hierarchy with books."""
    # Create hierarchy
    tag_service.get_or_create_tag("Work", description="Work projects", color="#FF5733")
    tag_service.get_or_create_tag("Work/Project-2024")
    tag_service.get_or_create_tag("Work/Project-2024/Backend")
    tag_service.get_or_create_tag("Work/Project-2025")
    tag_service.get_or_create_tag("Personal", description="Personal reading")
    tag_service.get_or_create_tag("Reference")

    # Create and tag books
    book1 = create_book(temp_library, "book1.txt", "Book 1")
    book2 = create_book(temp_library, "book2.txt", "Book 2")
    book3 = create_book(temp_library, "book3.txt", "Book 3")

    tag_service.add_tag_to_book(book1, "Work")
    tag_service.add_tag_to_book(book2, "Work/Project-2024")
    tag_service.add_tag_to_book(book3, "Personal")

    return {
        'library': temp_library,
        'tag_service': tag_service,
        'books': [book1, book2, book3]
    }


def create_book(library, filename, title):
    """Helper to create a test book."""
    test_file = library.library_path / filename
    test_file.write_text(f"Content for {title}")
    return library.add_book(
        test_file,
        metadata={"title": title, "creators": ["Test Author"]},
        extract_text=False
    )


class TestTagsDirectoryNode:
    """Test the /tags/ root directory node."""

    def test_creation(self, temp_library):
        """Test creating TagsDirectoryNode."""
        node = TagsDirectoryNode(temp_library)

        assert node.name == "tags"
        assert node.library == temp_library

    def test_list_children_empty(self, temp_library):
        """Test listing children when no tags exist."""
        node = TagsDirectoryNode(temp_library)
        children = node.list_children()

        assert len(children) == 0

    def test_list_children_root_tags_only(self, sample_hierarchy):
        """Test listing root-level tags."""
        node = TagsDirectoryNode(sample_hierarchy['library'])
        children = node.list_children()

        # Should have 3 root tags: Work, Personal, Reference
        assert len(children) == 3

        # All should be TagNode instances
        assert all(isinstance(child, TagNode) for child in children)

        # Check names
        child_names = {child.name for child in children}
        assert child_names == {"Work", "Personal", "Reference"}

    def test_get_child_exists(self, sample_hierarchy):
        """Test getting a specific root tag by name."""
        node = TagsDirectoryNode(sample_hierarchy['library'])
        child = node.get_child("Work")

        assert child is not None
        assert isinstance(child, TagNode)
        assert child.name == "Work"
        assert child.tag.path == "Work"

    def test_get_child_not_exists(self, sample_hierarchy):
        """Test getting a non-existent tag."""
        node = TagsDirectoryNode(sample_hierarchy['library'])
        child = node.get_child("NonExistent")

        assert child is None

    def test_get_child_nested_tag_returns_none(self, sample_hierarchy):
        """Test that nested tags cannot be accessed directly from root."""
        node = TagsDirectoryNode(sample_hierarchy['library'])
        child = node.get_child("Project-2024")

        # Should not be accessible from root (needs to go through Work)
        assert child is None

    def test_get_info(self, sample_hierarchy):
        """Test getting directory info."""
        node = TagsDirectoryNode(sample_hierarchy['library'])
        info = node.get_info()

        assert info['type'] == 'virtual'
        assert info['name'] == 'tags'
        assert info['total_tags'] == 6  # Work, Work/P-24, Work/P-24/Backend, Work/P-25, Personal, Reference
        assert info['root_tags'] == 3
        assert 'path' in info

    def test_get_path(self, temp_library):
        """Test VFS path construction."""
        node = TagsDirectoryNode(temp_library)
        path = node.get_path()

        # Node with no parent returns "/"
        # In a real VFS, this would be mounted under a root node
        assert path == "/"


class TestTagNode:
    """Test individual tag directory nodes."""

    def test_creation(self, sample_hierarchy):
        """Test creating a TagNode."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        assert node.name == "Work"
        assert node.tag == tag
        assert node.library == sample_hierarchy['library']

    def test_list_children_empty_tag(self, tag_service, temp_library):
        """Test listing children of a tag with no children or books."""
        tag = tag_service.get_or_create_tag("Empty")
        node = TagNode(tag, temp_library)

        children = node.list_children()

        # Should have 3 metadata files (always shown, even if empty)
        assert len(children) == 3
        metadata_files = [c for c in children if isinstance(c, (TagDescriptionFile, TagColorFile, TagStatsFile))]
        assert len(metadata_files) == 3

    def test_list_children_with_subtags(self, sample_hierarchy):
        """Test listing children includes child tags."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        children = node.list_children()

        # Should have: Project-2024, Project-2025, book (1), description, color, stats
        tag_nodes = [c for c in children if isinstance(c, TagNode)]
        assert len(tag_nodes) == 2

        child_names = {child.name for child in tag_nodes}
        assert child_names == {"Project-2024", "Project-2025"}

    def test_list_children_with_books(self, sample_hierarchy):
        """Test listing children includes book symlinks."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        children = node.list_children()

        # Find book symlinks
        book_links = [c for c in children if isinstance(c, SymlinkNode)]
        assert len(book_links) == 1

        # Check symlink points to /books/ID
        book = sample_hierarchy['books'][0]
        assert book_links[0].name == str(book.id)
        assert book_links[0].target_path == f"/books/{book.id}"

    def test_list_children_with_description(self, sample_hierarchy):
        """Test that tags with description show description file."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        children = node.list_children()

        # Should have description file
        desc_files = [c for c in children if isinstance(c, TagDescriptionFile)]
        assert len(desc_files) == 1

    def test_list_children_with_color(self, sample_hierarchy):
        """Test that tags with color show color file."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        children = node.list_children()

        # Should have color file
        color_files = [c for c in children if isinstance(c, TagColorFile)]
        assert len(color_files) == 1

    def test_list_children_stats_always_present(self, sample_hierarchy):
        """Test that stats file is always present."""
        tag = sample_hierarchy['tag_service'].get_tag("Reference")  # No metadata
        node = TagNode(tag, sample_hierarchy['library'])

        children = node.list_children()

        # Should have stats file
        stats_files = [c for c in children if isinstance(c, TagStatsFile)]
        assert len(stats_files) == 1

    def test_get_child_subtag(self, sample_hierarchy):
        """Test getting a child tag by name."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("Project-2024")

        assert child is not None
        assert isinstance(child, TagNode)
        assert child.tag.path == "Work/Project-2024"

    def test_get_child_book(self, sample_hierarchy):
        """Test getting a book by ID."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        book = sample_hierarchy['books'][0]
        child = node.get_child(str(book.id))

        assert child is not None
        assert isinstance(child, SymlinkNode)
        assert child.target_path == f"/books/{book.id}"

    def test_get_child_description_file(self, sample_hierarchy):
        """Test getting description metadata file."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("description")

        assert child is not None
        assert isinstance(child, TagDescriptionFile)

    def test_get_child_color_file(self, sample_hierarchy):
        """Test getting color metadata file."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("color")

        assert child is not None
        assert isinstance(child, TagColorFile)

    def test_get_child_stats_file(self, sample_hierarchy):
        """Test getting stats metadata file."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("stats")

        assert child is not None
        assert isinstance(child, TagStatsFile)

    def test_get_child_not_exists(self, sample_hierarchy):
        """Test getting a non-existent child."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("NonExistent")

        assert child is None

    def test_get_child_invalid_book_id(self, sample_hierarchy):
        """Test getting child with invalid book ID."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        child = node.get_child("99999")  # Non-existent book ID

        assert child is None

    def test_get_child_book_not_tagged(self, sample_hierarchy):
        """Test getting a book that exists but isn't tagged with this tag."""
        tag = sample_hierarchy['tag_service'].get_tag("Personal")
        node = TagNode(tag, sample_hierarchy['library'])

        # Try to get book1 which is tagged with "Work", not "Personal"
        book1 = sample_hierarchy['books'][0]
        child = node.get_child(str(book1.id))

        assert child is None

    def test_get_info(self, sample_hierarchy):
        """Test getting tag info."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        node = TagNode(tag, sample_hierarchy['library'])

        info = node.get_info()

        assert info['type'] == 'virtual'
        assert info['name'] == 'Work'
        assert info['path'] == 'Work'
        assert info['depth'] == 0
        assert info['book_count'] == 1
        assert info['child_tags'] == 2
        assert info['description'] == "Work projects"
        assert info['color'] == "#FF5733"
        assert 'created_at' in info

    def test_get_path_root_tag(self, sample_hierarchy):
        """Test VFS path for root-level tag."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        parent = TagsDirectoryNode(sample_hierarchy['library'])
        node = TagNode(tag, sample_hierarchy['library'], parent=parent)

        path = node.get_path()

        # Parent (TagsDirectoryNode) has no parent, so it's at "/"
        # This node's path is /Work
        assert path == "/Work"

    def test_get_path_nested_tag(self, sample_hierarchy):
        """Test VFS path for nested tag."""
        # Build hierarchy: /tags -> Work -> Project-2024
        tags_dir = TagsDirectoryNode(sample_hierarchy['library'])
        work_tag = sample_hierarchy['tag_service'].get_tag("Work")
        work_node = TagNode(work_tag, sample_hierarchy['library'], parent=tags_dir)

        project_tag = sample_hierarchy['tag_service'].get_tag("Work/Project-2024")
        project_node = TagNode(project_tag, sample_hierarchy['library'], parent=work_node)

        path = project_node.get_path()

        # tags_dir parent is None -> "/"
        # Path is /Work/Project-2024
        assert path == "/Work/Project-2024"


class TestTagDescriptionFile:
    """Test tag description metadata file."""

    def test_creation(self, sample_hierarchy):
        """Test creating TagDescriptionFile."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagDescriptionFile(tag, sample_hierarchy['library'])

        assert file_node.name == "description"
        assert file_node.tag == tag

    def test_read_content(self, sample_hierarchy):
        """Test reading description content."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagDescriptionFile(tag, sample_hierarchy['library'])

        content = file_node.read_content()

        assert content == "Work projects"

    def test_read_content_empty(self, tag_service, temp_library):
        """Test reading description when none exists."""
        tag = tag_service.get_or_create_tag("NoDesc")
        file_node = TagDescriptionFile(tag, temp_library)

        content = file_node.read_content()

        assert content == ""

    def test_parent_relationship(self, sample_hierarchy):
        """Test that file has correct parent."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        tag_node = TagNode(tag, sample_hierarchy['library'])
        file_node = TagDescriptionFile(tag, sample_hierarchy['library'], parent=tag_node)

        assert file_node.parent == tag_node


class TestTagColorFile:
    """Test tag color metadata file."""

    def test_creation(self, sample_hierarchy):
        """Test creating TagColorFile."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagColorFile(tag, sample_hierarchy['library'])

        assert file_node.name == "color"
        assert file_node.tag == tag

    def test_read_content(self, sample_hierarchy):
        """Test reading color content."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagColorFile(tag, sample_hierarchy['library'])

        content = file_node.read_content()

        assert content == "#FF5733"

    def test_read_content_empty(self, tag_service, temp_library):
        """Test reading color when none exists."""
        tag = tag_service.get_or_create_tag("NoColor")
        file_node = TagColorFile(tag, temp_library)

        content = file_node.read_content()

        assert content == ""

    def test_parent_relationship(self, sample_hierarchy):
        """Test that file has correct parent."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        tag_node = TagNode(tag, sample_hierarchy['library'])
        file_node = TagColorFile(tag, sample_hierarchy['library'], parent=tag_node)

        assert file_node.parent == tag_node


class TestTagStatsFile:
    """Test tag statistics metadata file."""

    def test_creation(self, sample_hierarchy):
        """Test creating TagStatsFile."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagStatsFile(tag, sample_hierarchy['tag_service'])

        assert file_node.name == "stats"
        assert file_node.tag == tag
        assert file_node.tag_service == sample_hierarchy['tag_service']

    def test_read_content(self, sample_hierarchy):
        """Test reading stats content."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        file_node = TagStatsFile(tag, sample_hierarchy['tag_service'])

        content = file_node.read_content()

        # Check that stats are formatted correctly
        assert "Tag: Work" in content
        assert "Name: Work" in content
        assert "Depth: 0" in content
        assert "Books: 1" in content
        assert "Subtags: 2" in content
        assert "Description: Work projects" in content
        assert "Color: #FF5733" in content
        assert "Created:" in content

    def test_read_content_minimal_tag(self, tag_service, temp_library):
        """Test reading stats for tag with no metadata."""
        tag = tag_service.get_or_create_tag("Minimal")
        file_node = TagStatsFile(tag, tag_service)

        content = file_node.read_content()

        assert "Tag: Minimal" in content
        assert "Name: Minimal" in content
        assert "Depth: 0" in content
        assert "Books: 0" in content
        assert "Subtags: 0" in content
        # Should not have description or color lines
        assert "Description:" not in content
        assert "Color:" not in content

    def test_read_content_nested_tag(self, sample_hierarchy):
        """Test reading stats for nested tag."""
        tag = sample_hierarchy['tag_service'].get_tag("Work/Project-2024")
        file_node = TagStatsFile(tag, sample_hierarchy['tag_service'])

        content = file_node.read_content()

        assert "Tag: Work/Project-2024" in content
        assert "Name: Project-2024" in content
        assert "Depth: 1" in content
        assert "Books: 1" in content
        assert "Subtags: 1" in content  # Backend

    def test_parent_relationship(self, sample_hierarchy):
        """Test that file has correct parent."""
        tag = sample_hierarchy['tag_service'].get_tag("Work")
        tag_node = TagNode(tag, sample_hierarchy['library'])
        file_node = TagStatsFile(tag, sample_hierarchy['tag_service'], parent=tag_node)

        assert file_node.parent == tag_node


class TestHierarchicalNavigation:
    """Test navigating through the tag hierarchy."""

    def test_navigate_to_nested_tag(self, sample_hierarchy):
        """Test navigating from root to nested tag."""
        # Start at /tags
        tags_dir = TagsDirectoryNode(sample_hierarchy['library'])

        # Navigate to Work
        work_node = tags_dir.get_child("Work")
        assert work_node is not None
        assert work_node.name == "Work"

        # Navigate to Project-2024
        project_node = work_node.get_child("Project-2024")
        assert project_node is not None
        assert project_node.tag.path == "Work/Project-2024"

        # Navigate to Backend
        backend_node = project_node.get_child("Backend")
        assert backend_node is not None
        assert backend_node.tag.path == "Work/Project-2024/Backend"

    def test_list_children_at_each_level(self, sample_hierarchy):
        """Test listing children at each hierarchy level."""
        tags_dir = TagsDirectoryNode(sample_hierarchy['library'])

        # Root level
        root_children = tags_dir.list_children()
        assert len(root_children) == 3

        # Work level
        work_node = tags_dir.get_child("Work")
        work_children = work_node.list_children()
        # Should have: 2 subtags, 1 book, description, color, stats = 6
        assert len(work_children) == 6

        # Project-2024 level
        project_node = work_node.get_child("Project-2024")
        project_children = project_node.list_children()
        # Should have: 1 subtag (Backend), 1 book, 3 metadata files (description, color, stats) = 5
        assert len(project_children) == 5


class TestEmptyTags:
    """Test behavior with empty tags."""

    def test_empty_tag_no_children_no_books(self, tag_service, temp_library):
        """Test tag with no children and no books."""
        tag = tag_service.get_or_create_tag("Empty")
        node = TagNode(tag, temp_library)

        children = node.list_children()

        # Should have 3 metadata files (always shown, even if empty)
        assert len(children) == 3
        metadata_files = [c for c in children if isinstance(c, (TagDescriptionFile, TagColorFile, TagStatsFile))]
        assert len(metadata_files) == 3

    def test_empty_tag_info(self, tag_service, temp_library):
        """Test info for empty tag."""
        tag = tag_service.get_or_create_tag("Empty")
        node = TagNode(tag, temp_library)

        info = node.get_info()

        assert info['book_count'] == 0
        assert info['child_tags'] == 0

    def test_empty_tags_directory(self, temp_library):
        """Test tags directory with no tags."""
        node = TagsDirectoryNode(temp_library)

        children = node.list_children()
        info = node.get_info()

        assert len(children) == 0
        assert info['total_tags'] == 0
        assert info['root_tags'] == 0


class TestMultipleBooks:
    """Test tags with multiple books."""

    def test_tag_with_many_books(self, tag_service, temp_library):
        """Test tag node with multiple books."""
        tag = tag_service.get_or_create_tag("Popular")

        # Create and tag 5 books
        books = []
        for i in range(5):
            book = create_book(temp_library, f"book{i}.txt", f"Book {i}")
            tag_service.add_tag_to_book(book, "Popular")
            books.append(book)

        # Create node and list children
        node = TagNode(tag, temp_library)
        children = node.list_children()

        # Should have 5 book symlinks + stats file
        book_links = [c for c in children if isinstance(c, SymlinkNode)]
        assert len(book_links) == 5

        # Check all books are represented
        book_ids = {int(link.name) for link in book_links}
        expected_ids = {book.id for book in books}
        assert book_ids == expected_ids

    def test_access_each_book(self, tag_service, temp_library):
        """Test accessing each book individually."""
        tag = tag_service.get_or_create_tag("Popular")

        # Create and tag books
        books = []
        for i in range(3):
            book = create_book(temp_library, f"book{i}.txt", f"Book {i}")
            tag_service.add_tag_to_book(book, "Popular")
            books.append(book)

        # Access each book by ID
        node = TagNode(tag, temp_library)
        for book in books:
            child = node.get_child(str(book.id))
            assert child is not None
            assert isinstance(child, SymlinkNode)
            assert child.target_path == f"/books/{book.id}"
