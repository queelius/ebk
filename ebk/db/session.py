"""
Database session management for ebk.

Provides session factory and initialization utilities.
"""

from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from .models import Base

# Global session factory
_SessionFactory: Optional[sessionmaker] = None
_engine: Optional[Engine] = None


def init_db(library_path: Path, echo: bool = False) -> Engine:
    """
    Initialize database and create all tables.

    Args:
        library_path: Path to library directory
        echo: If True, log all SQL statements (debug mode)

    Returns:
        SQLAlchemy engine
    """
    global _engine, _SessionFactory

    library_path = Path(library_path)
    library_path.mkdir(parents=True, exist_ok=True)

    db_path = library_path / 'library.db'
    db_url = f'sqlite:///{db_path}'

    _engine = create_engine(db_url, echo=echo)

    # Enable foreign keys for SQLite
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables
    Base.metadata.create_all(_engine)

    # Create FTS5 virtual table for full-text search
    with _engine.connect() as conn:
        # Check if FTS table exists
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='books_fts'")
        )
        if not result.fetchone():
            conn.execute(text("""
                CREATE VIRTUAL TABLE books_fts USING fts5(
                    book_id UNINDEXED,
                    title,
                    description,
                    extracted_text,
                    tokenize='porter unicode61'
                )
            """))
            conn.commit()

    # Create session factory
    _SessionFactory = sessionmaker(bind=_engine)

    return _engine


def get_session() -> Session:
    """
    Get a new database session.

    Returns:
        SQLAlchemy session

    Raises:
        RuntimeError: If database not initialized
    """
    if _SessionFactory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() first."
        )
    return _SessionFactory()


@contextmanager
def session_scope():
    """
    Provide a transactional scope around a series of operations.

    Usage:
        with session_scope() as session:
            session.add(book)
            # Automatically commits or rolls back
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def close_db():
    """Close database connection and cleanup."""
    global _engine, _SessionFactory

    if _engine:
        _engine.dispose()
        _engine = None

    _SessionFactory = None


def get_or_create(session: Session, model, **kwargs):
    """
    Get existing instance or create new one.

    Args:
        session: Database session
        model: SQLAlchemy model class
        **kwargs: Filter criteria and/or values to set

    Returns:
        Tuple of (instance, created: bool)
    """
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        session.add(instance)
        return instance, True
