"""
SQLAlchemy models for ebk database.

Clean, normalized schema with proper relationships and indexes.
"""

from datetime import datetime
from typing import List, Optional
from pathlib import Path
import hashlib

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, Float,
    DateTime, ForeignKey, Table, UniqueConstraint, Index, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property

Base = declarative_base()


# Association tables for many-to-many relationships
book_authors = Table(
    'book_authors',
    Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    Column('author_id', Integer, ForeignKey('authors.id', ondelete='CASCADE'), primary_key=True),
    Column('role', String(50), default='author'),  # author, editor, translator, contributor
    Column('position', Integer, default=0)  # For ordering
)

book_subjects = Table(
    'book_subjects',
    Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    Column('subject_id', Integer, ForeignKey('subjects.id', ondelete='CASCADE'), primary_key=True),
    Column('relevance_score', Float, default=1.0),  # How central is this topic (0-1)
    Column('source', String(50), default='user')  # calibre, ai_extracted, user_added
)

book_tags = Table(
    'book_tags',
    Base.metadata,
    Column('book_id', Integer, ForeignKey('books.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow)  # When tag was added
)


class Book(Base):
    """Core book entity with metadata."""
    __tablename__ = 'books'

    id = Column(Integer, primary_key=True)
    unique_id = Column(String(32), unique=True, nullable=False, index=True)  # Hash-based

    # Core metadata
    title = Column(String(500), nullable=False, index=True)
    subtitle = Column(String(500))
    sort_title = Column(String(500), index=True)  # For alphabetical sorting
    language = Column(String(10), index=True)  # ISO 639-1 code
    publisher = Column(String(200), index=True)
    publication_date = Column(String(50))  # Flexible: year, YYYY-MM, or YYYY-MM-DD

    # Series information
    series = Column(String(200), index=True)  # Book series name
    series_index = Column(Float)  # Position in series (e.g., 2.5)

    # Edition and rights
    edition = Column(String(100))  # "2nd Edition", "Revised", etc.
    rights = Column(Text)  # Copyright/license statement
    source = Column(String(500))  # Original source URL or reference

    # Rich content
    description = Column(Text)  # Full text indexed separately
    page_count = Column(Integer)
    word_count = Column(Integer)  # From extracted text
    keywords = Column(JSON)  # Array of keyword strings from PDF/metadata

    # User customization
    color = Column(String(7))  # Hex color code (e.g., #FF5733)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    authors = relationship('Author', secondary=book_authors, back_populates='books', lazy='selectin')
    subjects = relationship('Subject', secondary=book_subjects, back_populates='books', lazy='selectin')
    tags = relationship('Tag', secondary=book_tags, back_populates='books', lazy='selectin')
    contributors = relationship('Contributor', back_populates='book', cascade='all, delete-orphan')
    identifiers = relationship('Identifier', back_populates='book', cascade='all, delete-orphan')
    files = relationship('File', back_populates='book', cascade='all, delete-orphan')
    covers = relationship('Cover', back_populates='book', cascade='all, delete-orphan')
    concepts = relationship('BookConcept', back_populates='book', cascade='all, delete-orphan')
    sessions = relationship('ReadingSession', back_populates='book', cascade='all, delete-orphan')
    annotations = relationship('Annotation', back_populates='book', cascade='all, delete-orphan')
    personal = relationship('PersonalMetadata', back_populates='book', uselist=False, cascade='all, delete-orphan')

    # Indexes
    __table_args__ = (
        Index('idx_book_title_lang', 'title', 'language'),
        Index('idx_book_created', 'created_at'),
    )

    @hybrid_property
    def primary_file(self) -> Optional['File']:
        """Get the primary file (prefer PDF > EPUB > others)."""
        if not self.files:
            return None
        # Sort by preference
        format_priority = {'pdf': 0, 'epub': 1, 'mobi': 2, 'azw3': 3}
        sorted_files = sorted(
            self.files,
            key=lambda f: format_priority.get(f.format.lower(), 99)
        )
        return sorted_files[0] if sorted_files else None

    @hybrid_property
    def primary_cover(self) -> Optional['Cover']:
        """Get the primary cover image."""
        for cover in self.covers:
            if cover.is_primary:
                return cover
        return self.covers[0] if self.covers else None

    def __repr__(self):
        return f"<Book(id={self.id}, title='{self.title[:50]}')>"


class Author(Base):
    """Author/creator entity."""
    __tablename__ = 'authors'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    sort_name = Column(String(200), index=True)  # "Tolkien, J.R.R."
    bio = Column(Text)
    birth_year = Column(Integer)
    death_year = Column(Integer)

    # Relationships
    books = relationship('Book', secondary=book_authors, back_populates='authors')

    __table_args__ = (
        UniqueConstraint('name', name='uix_author_name'),
    )

    def __repr__(self):
        return f"<Author(id={self.id}, name='{self.name}')>"


class Subject(Base):
    """Subject/tag/genre with hierarchical support."""
    __tablename__ = 'subjects'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    parent_id = Column(Integer, ForeignKey('subjects.id', ondelete='SET NULL'))
    type = Column(String(50), default='topic')  # genre, topic, keyword, personal_tag

    # Self-referential relationship for hierarchy
    parent = relationship('Subject', remote_side=[id], backref='children')
    books = relationship('Book', secondary=book_subjects, back_populates='subjects')

    def __repr__(self):
        return f"<Subject(id={self.id}, name='{self.name}', type='{self.type}')>"


class Tag(Base):
    """User-defined hierarchical tags for organizing books.

    Tags are separate from Subjects:
    - Subjects: Bibliographic metadata (what the book is about)
    - Tags: User-defined organization (how you use/categorize the book)

    Examples:
    - path="Work/Project-2024"
    - path="Personal/To-Read"
    - path="Reference/Programming/Python"
    """
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)  # Name at this level (e.g., "Python")
    path = Column(String(500), nullable=False, unique=True, index=True)  # Full path (e.g., "Programming/Python")
    parent_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'))

    # Metadata
    description = Column(Text)  # Optional description of the tag
    color = Column(String(7))  # Hex color code for UI display (e.g., "#FF5733")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Self-referential relationship for hierarchy
    parent = relationship('Tag', remote_side=[id], backref='children')
    books = relationship('Book', secondary=book_tags, back_populates='tags')

    __table_args__ = (
        Index('idx_tag_path', 'path'),
        Index('idx_tag_parent', 'parent_id'),
    )

    @property
    def depth(self) -> int:
        """Calculate depth in hierarchy (root=0)."""
        return self.path.count('/')

    @property
    def ancestors(self) -> List['Tag']:
        """Get list of ancestor tags from root to parent."""
        ancestors = []
        current = self.parent
        while current:
            ancestors.insert(0, current)
            current = current.parent
        return ancestors

    @property
    def full_path_parts(self) -> List[str]:
        """Split path into components."""
        return self.path.split('/')

    def __repr__(self):
        return f"<Tag(id={self.id}, path='{self.path}')>"


class Contributor(Base):
    """Contributors to a book (editors, translators, illustrators, etc)."""
    __tablename__ = 'contributors'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    name = Column(String(200), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # editor, translator, illustrator, etc.
    file_as = Column(String(200))  # Sorting name

    book = relationship('Book', back_populates='contributors')

    __table_args__ = (
        Index('idx_contributor_name', 'name'),
        Index('idx_contributor_role', 'role'),
    )

    def __repr__(self):
        return f"<Contributor(name='{self.name}', role='{self.role}')>"


class Identifier(Base):
    """Flexible identifiers (ISBN, DOI, etc)."""
    __tablename__ = 'identifiers'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    scheme = Column(String(50), nullable=False, index=True)  # isbn, doi, arxiv, goodreads
    value = Column(String(200), nullable=False, index=True)

    book = relationship('Book', back_populates='identifiers')

    __table_args__ = (
        UniqueConstraint('book_id', 'scheme', 'value', name='uix_identifier'),
    )

    def __repr__(self):
        return f"<Identifier(scheme='{self.scheme}', value='{self.value}')>"


class File(Base):
    """Ebook files with extraction metadata."""
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    path = Column(String(500), nullable=False)  # Relative to library root
    format = Column(String(20), nullable=False, index=True)  # pdf, epub, mobi
    size_bytes = Column(Integer)
    file_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA256

    # File metadata
    mime_type = Column(String(100))  # Full MIME type (e.g., application/pdf)
    created_date = Column(DateTime)  # File creation time from filesystem
    modified_date = Column(DateTime)  # File modification time from filesystem
    creator_application = Column(String(200))  # PDF: Creator app (e.g., "LaTeX")

    # Text extraction status
    text_extracted = Column(Boolean, default=False)
    extraction_date = Column(DateTime)

    book = relationship('Book', back_populates='files')
    extracted_text = relationship('ExtractedText', back_populates='file', uselist=False, cascade='all, delete-orphan')
    chunks = relationship('TextChunk', back_populates='file', cascade='all, delete-orphan')

    @staticmethod
    def compute_hash(file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for block in iter(lambda: f.read(8192), b''):
                sha256.update(block)
        return sha256.hexdigest()

    def __repr__(self):
        return f"<File(id={self.id}, format='{self.format}', path='{self.path}')>"


class ExtractedText(Base):
    """Full extracted text for search."""
    __tablename__ = 'extracted_texts'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id', ondelete='CASCADE'), unique=True, nullable=False)

    content = Column(Text, nullable=False)  # Full text - will use FTS5 virtual table
    content_hash = Column(String(64), nullable=False)
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    file = relationship('File', back_populates='extracted_text')

    def __repr__(self):
        return f"<ExtractedText(file_id={self.file_id}, length={len(self.content)})>"


class TextChunk(Base):
    """Chunks for semantic search with embeddings."""
    __tablename__ = 'text_chunks'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id', ondelete='CASCADE'), nullable=False)

    chunk_index = Column(Integer, nullable=False)  # Order within file
    content = Column(Text, nullable=False)  # 500-1000 words

    # Page range (if available)
    start_page = Column(Integer)
    end_page = Column(Integer)

    # Embedding stored separately (pickle file or vector extension)
    has_embedding = Column(Boolean, default=False)

    file = relationship('File', back_populates='chunks')

    __table_args__ = (
        UniqueConstraint('file_id', 'chunk_index', name='uix_chunk'),
        Index('idx_chunk_file', 'file_id', 'chunk_index'),
    )

    def __repr__(self):
        return f"<TextChunk(id={self.id}, file_id={self.file_id}, index={self.chunk_index})>"


class Cover(Base):
    """Cover images."""
    __tablename__ = 'covers'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    path = Column(String(500), nullable=False)  # Relative to library root
    width = Column(Integer)
    height = Column(Integer)
    is_primary = Column(Boolean, default=True)
    source = Column(String(50), default='extracted')  # extracted, user_provided, downloaded

    book = relationship('Book', back_populates='covers')

    def __repr__(self):
        return f"<Cover(id={self.id}, book_id={self.book_id}, path='{self.path}')>"


class Concept(Base):
    """Knowledge graph concepts."""
    __tablename__ = 'concepts'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, unique=True, index=True)
    description = Column(Text)
    concept_type = Column(String(50), default='idea')  # definition, idea, theory, principle
    importance_score = Column(Float, default=0.0, index=True)  # PageRank score

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    book_concepts = relationship('BookConcept', back_populates='concept', cascade='all, delete-orphan')
    outgoing_relations = relationship('ConceptRelation', foreign_keys='ConceptRelation.source_id', back_populates='source', cascade='all, delete-orphan')
    incoming_relations = relationship('ConceptRelation', foreign_keys='ConceptRelation.target_id', back_populates='target', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Concept(id={self.id}, name='{self.name}')>"


class BookConcept(Base):
    """Link between books and concepts they discuss."""
    __tablename__ = 'book_concepts'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    concept_id = Column(Integer, ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)

    page_references = Column(JSON)  # Array of page numbers
    quote_examples = Column(JSON)  # Array of relevant quotes
    confidence_score = Column(Float, default=1.0)

    book = relationship('Book', back_populates='concepts')
    concept = relationship('Concept', back_populates='book_concepts')

    __table_args__ = (
        UniqueConstraint('book_id', 'concept_id', name='uix_book_concept'),
    )


class ConceptRelation(Base):
    """Relationships between concepts (knowledge graph edges)."""
    __tablename__ = 'concept_relations'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)
    target_id = Column(Integer, ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False)

    relation_type = Column(String(50), nullable=False)  # supports, contradicts, extends, examples, causes
    strength = Column(Float, default=1.0)  # 0-1
    evidence_book_id = Column(Integer, ForeignKey('books.id', ondelete='SET NULL'))

    source = relationship('Concept', foreign_keys=[source_id], back_populates='outgoing_relations')
    target = relationship('Concept', foreign_keys=[target_id], back_populates='incoming_relations')
    evidence_book = relationship('Book')

    __table_args__ = (
        UniqueConstraint('source_id', 'target_id', 'relation_type', name='uix_concept_relation'),
        Index('idx_relation_source', 'source_id'),
        Index('idx_relation_target', 'target_id'),
    )


class ReadingSession(Base):
    """Track reading sessions for active recall."""
    __tablename__ = 'reading_sessions'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)

    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime)
    pages_read = Column(Integer, default=0)

    highlights = Column(JSON)  # Array of highlight texts
    notes = Column(JSON)  # Array of note objects
    comprehension_score = Column(Float)  # From quiz results

    book = relationship('Book', back_populates='sessions')

    @hybrid_property
    def duration_minutes(self) -> Optional[float]:
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None


class Annotation(Base):
    """Highlights, notes, bookmarks."""
    __tablename__ = 'annotations'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), nullable=False)
    session_id = Column(Integer, ForeignKey('reading_sessions.id', ondelete='SET NULL'))

    annotation_type = Column(String(20), nullable=False)  # highlight, note, bookmark
    page_number = Column(Integer)
    position = Column(JSON)  # {char_offset: int} or {x: float, y: float}
    content = Column(Text, nullable=False)  # The highlighted text or note content
    color = Column(String(20))  # For highlights

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    book = relationship('Book', back_populates='annotations')
    session = relationship('ReadingSession')

    __table_args__ = (
        Index('idx_annotation_book', 'book_id', 'annotation_type'),
    )


class PersonalMetadata(Base):
    """Personal reading metadata (ratings, status, etc)."""
    __tablename__ = 'personal_metadata'

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey('books.id', ondelete='CASCADE'), unique=True, nullable=False)

    # Reading status
    rating = Column(Float)  # 0-5 stars
    reading_status = Column(String(20), default='unread')  # unread, reading, read, abandoned
    reading_progress = Column(Integer, default=0)  # 0-100 percentage

    # Collections
    favorite = Column(Boolean, default=False)
    owned = Column(Boolean, default=True)  # vs borrowed/library

    # Dates
    date_added = Column(DateTime, default=datetime.utcnow, nullable=False)
    date_started = Column(DateTime)
    date_finished = Column(DateTime)

    # Quick access tags (denormalized for performance)
    personal_tags = Column(JSON)  # Array of tag strings

    book = relationship('Book', back_populates='personal')

    __table_args__ = (
        Index('idx_personal_status', 'reading_status', 'rating'),
        Index('idx_personal_favorite', 'favorite'),
    )


# Full-Text Search Virtual Table (SQLite FTS5)
# This will be created separately as it's SQLite-specific
"""
CREATE VIRTUAL TABLE books_fts USING fts5(
    book_id UNINDEXED,
    title,
    description,
    content='extracted_texts',
    content_rowid='id'
);
"""
