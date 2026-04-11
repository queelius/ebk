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
from typing import Set

import logging

logger = logging.getLogger(__name__)

# Current schema version - increment when adding new migrations
CURRENT_SCHEMA_VERSION = 8


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


def migrate_add_reviews_table(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add reviews table for user book reviews.

    This migration adds support for detailed user reviews,
    separate from simple ratings.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    # Check if migration is needed
    if table_exists(engine, 'reviews'):
        logger.debug("Reviews table already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: reviews table does not exist")
        return True

    logger.debug("Applying migration: Adding reviews table")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE reviews (
                id INTEGER NOT NULL PRIMARY KEY,
                book_id INTEGER NOT NULL,
                title VARCHAR(255),
                content TEXT NOT NULL,
                rating FLOAT,
                review_type VARCHAR(50) DEFAULT 'personal',
                visibility VARCHAR(20) DEFAULT 'private',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE
            )
        """))

        # Create indexes
        conn.execute(text("CREATE INDEX idx_review_book ON reviews (book_id)"))
        conn.execute(text("CREATE INDEX idx_review_type ON reviews (review_type)"))
        conn.execute(text("CREATE INDEX idx_review_created ON reviews (created_at)"))

        logger.debug("Migration completed successfully")

    return True


def migrate_add_enrichment_history_table(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add enrichment_history table for tracking metadata changes.

    This migration adds support for tracking provenance of
    automated metadata enrichment.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    # Check if migration is needed
    if table_exists(engine, 'enrichment_history'):
        logger.debug("Enrichment history table already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: enrichment_history table does not exist")
        return True

    logger.debug("Applying migration: Adding enrichment_history table")

    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE enrichment_history (
                id INTEGER NOT NULL PRIMARY KEY,
                book_id INTEGER NOT NULL,
                field_name VARCHAR(100) NOT NULL,
                old_value TEXT,
                new_value TEXT,
                source_type VARCHAR(50) NOT NULL,
                source_detail VARCHAR(200),
                confidence FLOAT DEFAULT 1.0,
                applied BOOLEAN DEFAULT 1,
                reverted BOOLEAN DEFAULT 0,
                enriched_at DATETIME NOT NULL,
                FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE
            )
        """))

        # Create indexes
        conn.execute(text("CREATE INDEX idx_enrichment_book ON enrichment_history (book_id)"))
        conn.execute(text("CREATE INDEX idx_enrichment_source ON enrichment_history (source_type)"))
        conn.execute(text("CREATE INDEX idx_enrichment_field ON enrichment_history (field_name)"))
        conn.execute(text("CREATE INDEX idx_enrichment_date ON enrichment_history (enriched_at)"))

        logger.debug("Migration completed successfully")

    return True


def migrate_enhance_annotations(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add rich content fields to annotations table.

    Adds: title, content_format, category, pinned, updated_at

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
    if 'annotations' not in inspector.get_table_names():
        logger.debug("Annotations table does not exist, skipping migration")
        return False

    columns = [col['name'] for col in inspector.get_columns('annotations')]
    if 'content_format' in columns:
        logger.debug("Annotations.content_format column already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: annotations columns missing")
        return True

    logger.debug("Applying migration: Enhancing annotations table")

    with engine.begin() as conn:
        # Add new columns
        conn.execute(text("ALTER TABLE annotations ADD COLUMN title VARCHAR(255)"))
        conn.execute(text("ALTER TABLE annotations ADD COLUMN content_format VARCHAR(20) DEFAULT 'plain'"))
        conn.execute(text("ALTER TABLE annotations ADD COLUMN category VARCHAR(100)"))
        conn.execute(text("ALTER TABLE annotations ADD COLUMN pinned BOOLEAN DEFAULT 0"))
        conn.execute(text("ALTER TABLE annotations ADD COLUMN updated_at DATETIME"))

        # Create indexes for new columns
        conn.execute(text("CREATE INDEX idx_annotation_pinned ON annotations (book_id, pinned)"))
        conn.execute(text("CREATE INDEX idx_annotation_category ON annotations (category)"))

        logger.debug("Migration completed successfully")

    return True


def migrate_add_views_tables(library_path: Path, dry_run: bool = False) -> bool:
    """
    Add views and view_overrides tables for the Views DSL feature.

    This migration adds support for named, composable library views
    with per-book metadata overrides.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    # Check if migration is needed
    if table_exists(engine, 'views'):
        logger.debug("Views table already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: views tables do not exist")
        return True

    logger.debug("Applying migration: Adding views and view_overrides tables")

    with engine.begin() as conn:
        # Create views table
        conn.execute(text("""
            CREATE TABLE views (
                id INTEGER NOT NULL PRIMARY KEY,
                name VARCHAR(200) NOT NULL UNIQUE,
                description TEXT,
                definition JSON NOT NULL DEFAULT '{}',
                cached_count INTEGER,
                cached_at DATETIME,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX ix_views_name ON views (name)"))

        # Create view_overrides table
        conn.execute(text("""
            CREATE TABLE view_overrides (
                id INTEGER NOT NULL PRIMARY KEY,
                view_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                title VARCHAR(500),
                description TEXT,
                position INTEGER,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(view_id) REFERENCES views (id) ON DELETE CASCADE,
                FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE,
                UNIQUE(view_id, book_id)
            )
        """))
        conn.execute(text("CREATE INDEX ix_view_overrides_view_id ON view_overrides (view_id)"))
        conn.execute(text("CREATE INDEX ix_view_overrides_book_id ON view_overrides (book_id)"))

        logger.debug("Migration completed successfully")

    return True


def migrate_annotations_to_marginalia(library_path: Path, dry_run: bool = False) -> bool:
    """
    Replace annotations with marginalia.

    Creates marginalia + marginalia_books tables, migrates existing annotation
    data, and drops the annotations table. Also drops the vestigial highlights
    and notes JSON columns from reading_sessions.

    Args:
        library_path: Path to library directory
        dry_run: If True, only check if migration is needed

    Returns:
        True if migration was applied (or would be applied in dry_run),
        False if already up-to-date
    """
    engine = get_engine(library_path)

    if table_exists(engine, 'marginalia'):
        logger.debug("Marginalia table already exists, skipping migration")
        return False

    if dry_run:
        logger.debug("Migration needed: marginalia table does not exist")
        return True

    logger.debug("Applying migration: annotations → marginalia")

    with engine.begin() as conn:
        # Create marginalia table
        conn.execute(text("""
            CREATE TABLE marginalia (
                id INTEGER NOT NULL PRIMARY KEY,
                content TEXT,
                highlighted_text TEXT,
                page_number INTEGER,
                position JSON,
                category VARCHAR(100),
                pinned BOOLEAN DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX idx_marginalia_pinned ON marginalia (pinned)"))
        conn.execute(text("CREATE INDEX idx_marginalia_category ON marginalia (category)"))
        conn.execute(text("CREATE INDEX idx_marginalia_created ON marginalia (created_at)"))

        # Create junction table
        conn.execute(text("""
            CREATE TABLE marginalia_books (
                marginalia_id INTEGER NOT NULL,
                book_id INTEGER NOT NULL,
                PRIMARY KEY (marginalia_id, book_id),
                FOREIGN KEY(marginalia_id) REFERENCES marginalia (id) ON DELETE CASCADE,
                FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE
            )
        """))

        # Migrate existing annotations if the table exists
        if table_exists(engine, 'annotations'):
            # Insert into marginalia, mapping old fields to new
            conn.execute(text("""
                INSERT INTO marginalia (id, content, highlighted_text, page_number,
                                        position, category, pinned, created_at, updated_at)
                SELECT id,
                       CASE WHEN annotation_type = 'highlight' THEN NULL ELSE content END,
                       CASE WHEN annotation_type = 'highlight' THEN content ELSE NULL END,
                       page_number, position, category,
                       COALESCE(pinned, 0),
                       created_at,
                       updated_at
                FROM annotations
            """))

            # Create junction table entries (one book per old annotation)
            conn.execute(text("""
                INSERT INTO marginalia_books (marginalia_id, book_id)
                SELECT id, book_id FROM annotations
            """))

            conn.execute(text("DROP TABLE annotations"))

        logger.debug("Migration completed successfully")

    return True


# Migration registry: (version, name, function)
# Add new migrations here with incrementing version numbers
MIGRATIONS = [
    (1, 'add_tags', migrate_add_tags),
    (2, 'add_book_color', migrate_add_book_color),
    (3, 'descriptions_to_markdown', migrate_descriptions_to_markdown),
    (4, 'add_reviews_table', migrate_add_reviews_table),
    (5, 'add_enrichment_history_table', migrate_add_enrichment_history_table),
    (6, 'enhance_annotations', migrate_enhance_annotations),
    (7, 'add_views_tables', migrate_add_views_tables),
    (8, 'annotations_to_marginalia', migrate_annotations_to_marginalia),
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
