"""
Database migration utilities for ebk.

Since this project uses SQLAlchemy's create_all() approach rather than Alembic,
this module provides simple migration functions for schema changes.
"""

from pathlib import Path
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from typing import Optional

import logging

logger = logging.getLogger(__name__)


def get_engine(library_path: Path) -> Engine:
    """Get database engine for a library."""
    db_path = library_path / 'library.db'
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    db_url = f'sqlite:///{db_path}'
    return create_engine(db_url, echo=False)


def table_exists(engine: Engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate_add_tags(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add tags table and book_tags association table to existing database.

    This migration adds support for hierarchical user-defined tags,
    separate from bibliographic subjects.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    # Check if migration is needed
    if table_exists(engine, 'tags'):
        logger.info("Tags table already exists, skipping migration")
        return False

    if dry_run:
        logger.info("Migration needed: tags table does not exist")
        return True

    logger.info("Applying migration: Adding tags table and book_tags association")

    with engine.begin() as conn:
        # Create tags table
        conn.execute(text("""
            CREATE TABLE tags (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                path VARCHAR(500) NOT NULL UNIQUE,
                parent_id INTEGER,
                description TEXT,
                color VARCHAR(7),
                created_at DATETIME NOT NULL,
                FOREIGN KEY(parent_id) REFERENCES tags (id) ON DELETE CASCADE
            )
        """))

        # Create indexes on tags table
        conn.execute(text("CREATE INDEX idx_tag_path ON tags (path)"))
        conn.execute(text("CREATE INDEX idx_tag_parent ON tags (parent_id)"))
        conn.execute(text("CREATE INDEX ix_tags_name ON tags (name)"))

        # Create book_tags association table
        conn.execute(text("""
            CREATE TABLE book_tags (
                book_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                created_at DATETIME,
                PRIMARY KEY (book_id, tag_id),
                FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE,
                FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
        """))

        logger.info("Migration completed successfully")

    return True


def migrate_add_book_color(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add color column to books table.

    This migration adds a color field to books for user customization.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)
    inspector = inspect(engine)

    # Check if migration is needed
    if 'books' not in inspector.get_table_names():
        logger.error("Books table does not exist")
        return False

    columns = [col['name'] for col in inspector.get_columns('books')]
    if 'color' in columns:
        logger.info("Books.color column already exists, skipping migration")
        return False

    if dry_run:
        logger.info("Migration needed: books.color column does not exist")
        return True

    logger.info("Applying migration: Adding color column to books table")

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE books ADD COLUMN color VARCHAR(7)"))
        logger.info("Migration completed successfully")

    return True


def run_all_migrations(library_path: Path, dry_run: bool = False) -> dict:
    """
    Run all pending migrations on a library database.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check which migrations are needed

    Returns:
        Dict mapping migration name to whether it was applied
    """
    results = {}

    # Add future migrations here
    migrations = [
        ('add_tags', migrate_add_tags),
        ('add_book_color', migrate_add_book_color),
    ]

    for name, migration_func in migrations:
        try:
            applied = migration_func(library_path, dry_run=dry_run)
            results[name] = applied
        except Exception as e:
            logger.error(f"Migration '{name}' failed: {e}")
            results[name] = False
            raise

    return results


def check_migrations(library_path: Path) -> dict:
    """
    Check which migrations need to be applied.

    Args:
        library_path: Path to library directory

    Returns:
        Dict mapping migration name to whether it's needed
    """
    return run_all_migrations(library_path, dry_run=True)
