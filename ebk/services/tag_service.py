"""Service for managing hierarchical user tags.

Tags provide user-defined organization separate from bibliographic subjects.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from ebk.db.models import Tag, Book, book_tags


class TagService:
    """Service for CRUD operations on hierarchical tags."""

    def __init__(self, session: Session):
        """Initialize tag service.

        Args:
            session: SQLAlchemy session
        """
        self.session = session

    def get_or_create_tag(self, path: str, description: Optional[str] = None,
                          color: Optional[str] = None) -> Tag:
        """Get existing tag or create new one with full hierarchy.

        Args:
            path: Full tag path (e.g., "Work/Project-2024")
            description: Optional description
            color: Optional hex color code

        Returns:
            Tag instance

        Examples:
            >>> service.get_or_create_tag("Work/Project-2024")
            # Creates: "Work" and "Work/Project-2024" if they don't exist
        """
        # Check if tag already exists
        existing = self.session.query(Tag).filter_by(path=path).first()
        if existing:
            return existing

        # Parse path into components
        parts = path.split('/')
        parent_tag = None
        current_path = ""

        # Create hierarchy from root to leaf
        for i, name in enumerate(parts):
            # Build current path
            if current_path:
                current_path += f"/{name}"
            else:
                current_path = name

            # Check if this level exists
            tag = self.session.query(Tag).filter_by(path=current_path).first()

            if not tag:
                # Create new tag at this level
                tag = Tag(
                    name=name,
                    path=current_path,
                    parent_id=parent_tag.id if parent_tag else None
                )

                # Only set description and color on the leaf node
                if i == len(parts) - 1:
                    tag.description = description
                    tag.color = color

                self.session.add(tag)

            parent_tag = tag

        self.session.commit()
        return parent_tag

    def get_tag(self, path: str) -> Optional[Tag]:
        """Get tag by path.

        Args:
            path: Full tag path

        Returns:
            Tag instance or None
        """
        return self.session.query(Tag).filter_by(path=path).first()

    def get_all_tags(self) -> List[Tag]:
        """Get all tags ordered by path.

        Returns:
            List of all tags
        """
        return self.session.query(Tag).order_by(Tag.path).all()

    def get_root_tags(self) -> List[Tag]:
        """Get top-level tags (no parent).

        Returns:
            List of root tags
        """
        return self.session.query(Tag).filter(Tag.parent_id.is_(None)).order_by(Tag.name).all()

    def get_children(self, tag: Tag) -> List[Tag]:
        """Get immediate children of a tag.

        Args:
            tag: Parent tag

        Returns:
            List of child tags
        """
        return self.session.query(Tag).filter_by(parent_id=tag.id).order_by(Tag.name).all()

    def delete_tag(self, path: str, delete_children: bool = False) -> bool:
        """Delete a tag.

        Args:
            path: Full tag path
            delete_children: If True, delete children and all descendants too

        Returns:
            True if deleted, False if not found
        """
        tag = self.get_tag(path)
        if not tag:
            return False

        # Check if tag has children
        children = self.get_children(tag)
        if children and not delete_children:
            raise ValueError(f"Tag '{path}' has {len(children)} children. "
                           "Use delete_children=True to delete them too.")

        # If delete_children=True, explicitly delete all descendants
        if delete_children:
            # Find all tags that start with this path + "/"
            descendants = self.session.query(Tag).filter(
                Tag.path.like(f"{path}/%")
            ).all()
            for desc in descendants:
                self.session.delete(desc)

        self.session.delete(tag)
        self.session.commit()
        return True

    def rename_tag(self, old_path: str, new_path: str) -> Tag:
        """Rename a tag and update all descendant paths.

        Args:
            old_path: Current tag path
            new_path: New tag path

        Returns:
            Updated tag

        Raises:
            ValueError: If tag doesn't exist or new path already exists
        """
        tag = self.get_tag(old_path)
        if not tag:
            raise ValueError(f"Tag '{old_path}' not found")

        # Check if new path already exists
        if self.get_tag(new_path):
            raise ValueError(f"Tag '{new_path}' already exists")

        # Update this tag
        old_name = tag.name
        new_parts = new_path.split('/')
        tag.name = new_parts[-1]
        tag.path = new_path

        # Update all descendant paths
        descendants = self.session.query(Tag).filter(
            Tag.path.like(f"{old_path}/%")
        ).all()

        for desc in descendants:
            # Replace the old path prefix with new path
            desc.path = desc.path.replace(old_path, new_path, 1)

        self.session.commit()
        return tag

    def add_tag_to_book(self, book: Book, tag_path: str) -> Tag:
        """Add a tag to a book (creates tag if it doesn't exist).

        Args:
            book: Book instance
            tag_path: Full tag path

        Returns:
            Tag instance
        """
        tag = self.get_or_create_tag(tag_path)

        if tag not in book.tags:
            book.tags.append(tag)
            self.session.commit()

        return tag

    def remove_tag_from_book(self, book: Book, tag_path: str) -> bool:
        """Remove a tag from a book.

        Args:
            book: Book instance
            tag_path: Full tag path

        Returns:
            True if removed, False if book didn't have that tag
        """
        tag = self.get_tag(tag_path)
        if not tag:
            return False

        if tag in book.tags:
            book.tags.remove(tag)
            self.session.commit()
            return True

        return False

    def get_books_with_tag(self, tag_path: str, include_subtags: bool = False) -> List[Book]:
        """Get all books with a specific tag.

        Args:
            tag_path: Full tag path
            include_subtags: If True, include books from descendant tags

        Returns:
            List of books
        """
        tag = self.get_tag(tag_path)
        if not tag:
            return []

        if not include_subtags:
            return tag.books

        # Get all descendant tags
        descendant_paths = self.session.query(Tag.id).filter(
            Tag.path.like(f"{tag_path}/%")
        ).all()

        all_tag_ids = [tag.id] + [t[0] for t in descendant_paths]

        # Get books with any of these tags
        books = self.session.query(Book).join(book_tags).filter(
            book_tags.c.tag_id.in_(all_tag_ids)
        ).distinct().all()

        return books

    def get_tag_stats(self, tag_path: str) -> dict:
        """Get statistics for a tag.

        Args:
            tag_path: Full tag path

        Returns:
            Dict with stats: {book_count, subtag_count, depth}
        """
        tag = self.get_tag(tag_path)
        if not tag:
            return {}

        children = self.get_children(tag)

        return {
            'path': tag.path,
            'book_count': len(tag.books),
            'subtag_count': len(children),
            'depth': tag.depth,
            'created_at': tag.created_at,
        }
