"""
Database module for ebk.

Provides SQLAlchemy session management and initialization.
"""

from .models import (
    Base, Book, Author, Subject, Identifier, File, ExtractedText,
    TextChunk, Cover, Concept, BookConcept, ConceptRelation,
    ReadingSession, Annotation, PersonalMetadata
)
from .session import get_session, init_db, close_db

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
    'get_session',
    'init_db',
    'close_db'
]
