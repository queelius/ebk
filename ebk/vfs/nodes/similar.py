"""Similar books VFS node."""

from typing import List, Optional, Dict, Any

from ebk.vfs.base import VirtualNode, DirectoryNode, SymlinkNode, Node
from ebk.library_db import Library
from ebk.db.models import Book


class SimilarDirectoryNode(VirtualNode):
    """/books/42/similar/ - Virtual directory of similar books.

    Computes similar books on-demand using the similarity system.
    Each child is a symlink to another book with similarity score.
    """

    def __init__(
        self,
        book: Book,
        library: Library,
        parent: Optional[DirectoryNode] = None,
        top_k: int = 10,
    ):
        """Initialize similar books directory.

        Args:
            book: Query book
            library: Library instance
            parent: Parent node (usually BookNode)
            top_k: Number of similar books to show (default 10)
        """
        super().__init__(name="similar", parent=parent)
        self.book = book
        self.library = library
        self.top_k = top_k
        self._similar_cache: Optional[List[tuple]] = None

    def list_children(self) -> List[Node]:
        """List similar books as symlinks.

        Returns:
            List of SymlinkNode instances pointing to similar books
        """
        if self._similar_cache is None:
            self._compute_similar()

        symlinks = []
        for similar_book, score in self._similar_cache:
            # Create symlink to the similar book
            target_path = f"/books/{similar_book.id}"
            name = str(similar_book.id)

            # Create a SimilarBookSymlink with score info
            symlink = SimilarBookSymlink(
                name=name,
                target_path=target_path,
                similar_book=similar_book,
                score=score,
                parent=self,
            )
            symlinks.append(symlink)

        return symlinks

    def get_child(self, name: str) -> Optional[Node]:
        """Get a similar book symlink by ID.

        Args:
            name: Book ID as string

        Returns:
            SimilarBookSymlink or None
        """
        if self._similar_cache is None:
            self._compute_similar()

        # Find by ID
        try:
            book_id = int(name)
        except ValueError:
            return None

        for similar_book, score in self._similar_cache:
            if similar_book.id == book_id:
                target_path = f"/books/{similar_book.id}"
                return SimilarBookSymlink(
                    name=name,
                    target_path=target_path,
                    similar_book=similar_book,
                    score=score,
                    parent=self,
                )

        return None

    def _compute_similar(self) -> None:
        """Compute similar books using similarity system."""
        try:
            # Use library's find_similar method
            results = self.library.find_similar(
                self.book.id,
                top_k=self.top_k,
                filter_language=True,
            )
            self._similar_cache = results
        except Exception:
            # If similarity computation fails, return empty list
            self._similar_cache = []

    def get_info(self) -> Dict[str, Any]:
        """Get similar directory info.

        Returns:
            Dict with directory information
        """
        if self._similar_cache is None:
            self._compute_similar()

        return {
            "type": "virtual",
            "name": "similar",
            "count": len(self._similar_cache),
            "path": self.get_path(),
        }


class SimilarBookSymlink(SymlinkNode):
    """Symlink to a similar book with similarity score.

    Extends SymlinkNode to include similarity score information.
    """

    def __init__(
        self,
        name: str,
        target_path: str,
        similar_book: Book,
        score: float,
        parent: Optional[DirectoryNode] = None,
    ):
        """Initialize similar book symlink.

        Args:
            name: Link name (book ID)
            target_path: Path to target book
            similar_book: The similar book
            score: Similarity score [0, 1]
            parent: Parent node
        """
        super().__init__(name, target_path, parent)
        self.similar_book = similar_book
        self.score = score

    def get_info(self) -> Dict[str, Any]:
        """Get symlink info with similarity score.

        Returns:
            Dict with symlink information including score
        """
        info = super().get_info()
        info["score"] = self.score
        info["title"] = self.similar_book.title
        authors_str = ", ".join(a.name for a in self.similar_book.authors) if self.similar_book.authors else ""
        info["authors"] = authors_str
        return info
