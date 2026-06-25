"""
Database session management for book-memex.

Provides session factory and initialization utilities.
"""

from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session, Session
from sqlalchemy.engine import Engine

from .models import Base

# Global session factory.
#
# This is a thread-local ``scoped_session`` (see R3): the FastAPI server keeps a
# single process-global ``Library`` and reaches into ``library.session`` from
# every request, but synchronous endpoints run in a worker threadpool, so two
# concurrent requests are served on two different threads. A plain ``Session`` is
# not thread-safe; sharing one across threads risks torn writes and
# cross-request data bleed. A ``scoped_session`` hands each thread its own
# underlying ``Session`` while preserving the ``lib.session.*`` access pattern
# used throughout cli.py, server.py and mcp/. Single-threaded callers (CLI, MCP)
# see identical behaviour: one thread always resolves to one session.
_SessionFactory: Optional[scoped_session] = None
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
    @event.listens_for(_engine, "connect")
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

    # Create thread-local session factory (see module note on R3).
    _SessionFactory = scoped_session(sessionmaker(bind=_engine))

    # Run pending schema migrations. This both upgrades existing libraries
    # to the current schema and retroactively records baseline migrations
    # for freshly-created libraries (where create_all() already produced
    # the up-to-date tables).
    #
    # Imported lazily to avoid a circular import at module load time
    # (migrations.py does not import session, but keeping this local is
    # defensive against future changes and keeps import order obvious).
    from .migrations import run_all_migrations
    run_all_migrations(library_path)

    return _engine


def get_session() -> Session:
    """
    Get the current thread's database session.

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


def get_scoped_session() -> scoped_session:
    """
    Get the thread-local session registry proxy (see R3).

    Unlike :func:`get_session`, which resolves to one thread's ``Session`` at
    call time, this returns the ``scoped_session`` registry itself. Holding the
    registry (rather than a resolved ``Session``) lets a long-lived object such
    as ``Library`` be shared across threads safely: every attribute access on
    the proxy (``.query``, ``.commit``, ``.add``, ...) is dispatched to the
    calling thread's own ``Session``. This is what the FastAPI server relies on
    so that concurrent requests do not share uncommitted state.

    Raises:
        RuntimeError: If database not initialized
    """
    if _SessionFactory is None:
        raise RuntimeError(
            "Database not initialized. Call init_db() first."
        )
    return _SessionFactory


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

    # Release every thread-local Session held by the registry before the
    # engine is disposed, so no thread keeps a connection to a dead engine.
    if _SessionFactory is not None:
        _SessionFactory.remove()

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
