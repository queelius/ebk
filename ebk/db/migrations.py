"""
Database migration utilities for ebk.

Since this project uses SQLAlchemy's create_all() approach rather than Alembic,
this module provides simple migration functions for schema changes.

Schema versioning is tracked in the `schema_versions` table, which stores:
- version: Sequential version number
- migration_name: Name of the migration
- applied_at: Timestamp when migration was applied
"""

from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from typing import List, Optional, Set

import logging

logger = logging.getLogger(__name__)

# Current schema version - increment when adding new migrations
CURRENT_SCHEMA_VERSION = 3


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


def ensure_schema_versions_table(engine: Engine) -> None:
    """Create schema_versions table if it doesn't exist."""
    if table_exists(engine, 'schema_versions'):
        return

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE schema_versions (
                version INTEGER NOT NULL PRIMARY KEY,
                migration_name VARCHAR(200) NOT NULL,
                applied_at DATETIME NOT NULL
            )
        """))
        logger.debug("Created schema_versions table")


def get_applied_migrations(engine: Engine) -> Set[str]:
    """Get set of migration names that have been applied."""
    if not table_exists(engine, 'schema_versions'):
        return set()

    with engine.connect() as conn:
        result = conn.execute(text("SELECT migration_name FROM schema_versions"))
        return {row[0] for row in result.fetchall()}


def get_schema_version(engine: Engine) -> int:
    """Get the current schema version number."""
    if not table_exists(engine, 'schema_versions'):
        return 0

    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(version) FROM schema_versions"))
        row = result.fetchone()
        return row[0] if row and row[0] else 0


def record_migration(engine: Engine, version: int, migration_name: str) -> None:
    """Record that a migration has been applied."""
    ensure_schema_versions_table(engine)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO schema_versions (version, migration_name, applied_at)
                VALUES (:version, :migration_name, :applied_at)
            """),
            {"version": version, "migration_name": migration_name, "applied_at": datetime.now(timezone.utc)}
        )


def is_migration_applied(engine: Engine, migration_name: str) -> bool:
    """Check if a specific migration has been applied."""
    applied = get_applied_migrations(engine)
    return migration_name in applied


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
        logger.debug("Tags table already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: tags table does not exist")
        return True

    logger.debug("Applying migration: Adding tags table and book_tags association")

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

        logger.debug("Migration completed successfully")

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
        logger.debug("Books.color column already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: books.color column does not exist")
        return True

    logger.debug("Applying migration: Adding color column to books table")

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE books ADD COLUMN color VARCHAR(7)"))
        logger.debug("Migration completed successfully")

    return True


def migrate_descriptions_to_markdown(library_path: Path, dry_run: bool = False) -> bool:
    """
    Convert HTML descriptions to markdown.

    This migration converts book descriptions containing HTML to clean markdown
    for better display in console and web interfaces.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    # Check if any descriptions contain HTML
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT COUNT(*) FROM books WHERE description LIKE '%<%>%'"
        ))
        html_count = result.scalar()

    if html_count == 0:
        logger.debug("No HTML descriptions found, skipping migration")
        return False

    if dry_run:
        logger.debug(f"Migration needed: {html_count} descriptions contain HTML")
        return True

    logger.debug(f"Converting {html_count} HTML descriptions to markdown")

    try:
        from markdownify import markdownify as md
    except ImportError:
        logger.warning("markdownify not installed, using basic HTML stripping")
        md = None

    with engine.begin() as conn:
        # Fetch all descriptions with HTML
        result = conn.execute(text(
            "SELECT id, description FROM books WHERE description LIKE '%<%>%'"
        ))
        rows = result.fetchall()

        for book_id, description in rows:
            if not description:
                continue

            if md:
                # Convert HTML to markdown
                clean_desc = md(description, strip=['script', 'style'])
                # Clean up excessive whitespace
                import re
                clean_desc = re.sub(r'\n{3,}', '\n\n', clean_desc)
                clean_desc = clean_desc.strip()
            else:
                # Fallback: strip HTML tags
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(description, 'html.parser')
                clean_desc = soup.get_text(separator=' ', strip=True)

            conn.execute(
                text("UPDATE books SET description = :desc WHERE id = :id"),
                {"desc": clean_desc, "id": book_id}
            )

    logger.debug(f"Converted {len(rows)} descriptions to markdown")
    return True


# Migration registry: (version, name, function)
# Add new migrations here with incrementing version numbers
MIGRATIONS = [
    (1, 'add_tags', migrate_add_tags),
    (2, 'add_book_color', migrate_add_book_color),
    (3, 'descriptions_to_markdown', migrate_descriptions_to_markdown),
]


def run_all_migrations(library_path: Path, dry_run: bool = False) -> dict:
    """
    Run all pending migrations on a library database.

    Uses schema version tracking to determine which migrations need to run.
    Backwards compatible with databases that don't have schema_versions table.
    Retroactively records migrations that were already applied.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check which migrations are needed

    Returns:
        Dict mapping migration name to whether it was applied
    """
    results = {}
    engine = get_engine(library_path)

    # Get already applied migrations (for backwards compatibility)
    applied_migrations = get_applied_migrations(engine)

    for version, name, migration_func in MIGRATIONS:
        try:
            # Check if already recorded in schema_versions
            if name in applied_migrations:
                results[name] = False
                continue

            # Run migration (it will check internally if already applied)
            applied = migration_func(library_path, dry_run=dry_run)

            if not dry_run:
                # Record the migration (whether newly applied or retroactively)
                # This ensures proper version tracking even for already-migrated dbs
                record_migration(engine, version, name)

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
