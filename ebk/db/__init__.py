"""
Database module for ebk.

Provides SQLAlchemy session management and initialization.
"""

from .models import (
    Base, Book, Author, Subject, Identifier, File, ExtractedText,
    TextChunk, Cover, Concept, BookConcept, ConceptRelation,
    ReadingSession, Annotation, PersonalMetadata, Tag
)
from .session import get_session, init_db, close_db
from .migrations import run_all_migrations, check_migrations

__all__ = [
    'Base',
    'Book',
    'Author',
    'Subject',
    'Identifier',
    'File',
    'ExtractedText',
    'TextChunk',
    'Cover',
    'Concept',
    'BookConcept',
    'ConceptRelation',
    'ReadingSession',
    'Annotation',
    'PersonalMetadata',
    'Tag',
    'get_session',
    'init_db',
    'close_db',
    'run_all_migrations',
    'check_migrations'
]
