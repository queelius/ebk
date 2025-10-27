"""Subject-related VFS nodes."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import VirtualNode, DirectoryNode, SymlinkNode, Node
from ebk.library_db import Library
from ebk.db.models import Subject


class SubjectsDirectoryNode(VirtualNode):
    """/subjects/ - Virtual directory listing all subjects/tags.

    Each child is a SubjectNode representing books with that subject.
    """

    def __init__(self, library: Library, parent: Optional[DirectoryNode] = None):
        """Initialize subjects directory.

        Args:
            library: Library instance
            parent: Parent node (usually root)
        """
        super().__init__(name="subjects", parent=parent)
        self.library = library

    def list_children(self) -> List[Node]:
        """List all subjects.

        Returns:
            List of SubjectNode instances
        """
        # Query all subjects from database
        subjects_query = self.library.session.query(Subject).all()

        subject_nodes = []
        for subject in subjects_query:
            # Create a slug from subject name
            slug = self._make_slug(subject.name)
            node = SubjectNode(subject, slug, self.library, parent=self)
            subject_nodes.append(node)

        return subject_nodes

    def get_child(self, name: str) -> Optional[Node]:
        """Get a subject by slug.

        Args:
            name: Subject slug (e.g., "python", "machine-learning")

        Returns:
            SubjectNode or None
        """
        # Try to find subject by matching slug
        subjects = self.library.session.query(Subject).all()

        for subject in subjects:
            slug = self._make_slug(subject.name)
            if slug == name:
                return SubjectNode(subject, slug, self.library, parent=self)

        return None

    def _make_slug(self, name: str) -> str:
        """Convert subject name to filesystem-safe slug.

        Args:
            name: Subject name

        Returns:
            Slugified name (e.g., "Machine Learning" -> "machine-learning")
        """
        # Simple slugification: lowercase, replace spaces with hyphens
        slug = name.lower().replace(" ", "-")

        # Remove special characters
        slug = "".join(c for c in slug if c.isalnum() or c == "-")
        return slug

    def get_info(self) -> Dict[str, Any]:
        """Get subjects directory info.

        Returns:
            Dict with directory information
        """
        total = self.library.session.query(Subject).count()
        return {
            "type": "virtual",
            "name": "subjects",
            "total_subjects": total,
            "path": self.get_path(),
        }


class SubjectNode(VirtualNode):
    """/subjects/python/ - Books with a specific subject/tag.

    Contains symlinks to books tagged with this subject.
    """

    def __init__(
        self,
        subject: Subject,
        slug: str,
        library: Library,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize subject node.

        Args:
            subject: Subject database model
            slug: Subject slug for URL
            library: Library instance
            parent: Parent node (usually SubjectsDirectoryNode)
        """
        super().__init__(name=slug, parent=parent)
        self.subject = subject
        self.library = library

    def list_children(self) -> List[Node]:
        """List books with this subject as symlinks.

        Returns:
            List of SymlinkNode instances
        """
        symlinks = []
        for book in self.subject.books:
            target_path = f"/books/{book.id}"
            name = str(book.id)

            # Include book metadata for display
            metadata = {
                "title": book.title or "Untitled",
            }
            if book.authors:
                metadata["author"] = ", ".join([a.name for a in book.authors])

            symlink = SymlinkNode(name, target_path, parent=self, metadata=metadata)
            symlinks.append(symlink)

        return symlinks

    def get_child(self, name: str) -> Optional[Node]:
        """Get a book symlink by ID.

        Args:
            name: Book ID as string

        Returns:
            SymlinkNode or None
        """
        try:
            book_id = int(name)
        except ValueError:
            return None

        # Check if this book has this subject
        for book in self.subject.books:
            if book.id == book_id:
                target_path = f"/books/{book.id}"

                # Include book metadata for display
                metadata = {
                    "title": book.title or "Untitled",
                }
                if book.authors:
                    metadata["author"] = ", ".join([a.name for a in book.authors])

                return SymlinkNode(name, target_path, parent=self, metadata=metadata)

        return None

    def get_info(self) -> Dict[str, Any]:
        """Get subject node info.

        Returns:
            Dict with subject information
        """
        return {
            "type": "virtual",
            "name": self.name,
            "subject": self.subject.name,
            "book_count": len(self.subject.books),
            "path": self.get_path(),
        }
