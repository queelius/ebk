"""
Database migration utilities for book-memex.

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
CURRENT_SCHEMA_VERSION = 12


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


def migrate_add_archived_at(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 9: add archived_at TIMESTAMP NULL to soft-deletable tables.

    Tables: books, authors, subjects, tags, files, covers, personal_metadata,
    marginalia, reading_sessions. New column defaults to NULL (= not archived).

    The runner (``run_all_migrations``) is responsible for recording the
    migration in ``schema_versions``; we only mutate schema here. This matches
    the pattern of the earlier ``migrate_*`` helpers in this module.
    """
    name = "add_archived_at"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        logger.debug(f"Migration {name} already applied")
        return False

    tables = [
        "books", "authors", "subjects", "tags",
        "files", "covers", "personal_metadata",
        "marginalia", "reading_sessions",
    ]

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    # Per-table check: if every target table already has archived_at, the
    # migration is effectively a no-op even if it was not recorded. This
    # lets callers invoke the function directly and get idempotent behaviour
    # without touching the schema_versions table.
    all_columns_present = True
    for table in tables:
        if table not in existing_tables:
            continue
        cols = {c["name"] for c in inspector.get_columns(table)}
        if "archived_at" not in cols:
            all_columns_present = False
            break

    if all_columns_present:
        logger.debug(f"{name}: archived_at already present on all target tables")
        return False

    if dry_run:
        logger.info(f"DRY RUN: would add archived_at to: {tables}")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        for table in tables:
            if table not in existing_tables:
                logger.debug(f"  skipping {table}: table does not exist")
                continue
            # SQLite is happy to add a nullable column with no default.
            # Check that the column is not already there (defensive).
            cols = {c["name"] for c in inspector.get_columns(table)}
            if "archived_at" in cols:
                logger.debug(f"  skipping {table}: archived_at already present")
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN archived_at TIMESTAMP NULL"))
            logger.debug(f"  added archived_at to {table}")

    return True


def _backfill_uuids(conn, uuid_mod) -> None:
    """Populate NULL uuid columns with uuid4().hex values.

    Idempotent: only touches rows where uuid IS NULL. Safe to call twice.
    """
    for table in ("marginalia", "reading_sessions"):
        rows = list(conn.execute(text(
            f"SELECT id FROM {table} WHERE uuid IS NULL"
        )))
        for (rid,) in rows:
            conn.execute(
                text(f"UPDATE {table} SET uuid = :u WHERE id = :i"),
                {"u": uuid_mod.uuid4().hex, "i": rid},
            )


def migrate_add_uri_columns(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 10: add uuid + color + anchors + progress_anchor.

    - Marginalia: uuid (UNIQUE), color
    - ReadingSession: uuid (UNIQUE), start_anchor (JSON), end_anchor (JSON)
    - PersonalMetadata: progress_anchor (JSON)

    Existing rows get their uuid backfilled with uuid4().hex. Partial unique
    indexes are created on the new uuid columns (WHERE uuid IS NOT NULL) so
    that the backfill window stays legal and future inserts stay unique.

    The runner (``run_all_migrations``) records the migration in
    ``schema_versions``; we only mutate schema here, matching the pattern
    of the earlier ``migrate_*`` helpers in this module.
    """
    import uuid as _uuid

    name = "add_uri_columns"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        # Even if the migration record is present, backfill any NULL uuids
        # (defensive; this handles partial or hand-edited prior states).
        with engine.begin() as conn:
            _backfill_uuids(conn, _uuid)
        logger.debug(f"Migration {name} already applied (ran defensive backfill)")
        return False

    if dry_run:
        logger.info("DRY RUN: would add uuid, color, anchors, progress_anchor")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        inspector = inspect(engine)

        # Marginalia: uuid, color
        mcols = {c["name"] for c in inspector.get_columns("marginalia")}
        if "uuid" not in mcols:
            conn.execute(text("ALTER TABLE marginalia ADD COLUMN uuid VARCHAR(36)"))
        if "color" not in mcols:
            conn.execute(text("ALTER TABLE marginalia ADD COLUMN color VARCHAR(7)"))

        # ReadingSession: uuid, start_anchor, end_anchor
        rcols = {c["name"] for c in inspector.get_columns("reading_sessions")}
        if "uuid" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN uuid VARCHAR(36)"))
        if "start_anchor" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN start_anchor JSON"))
        if "end_anchor" not in rcols:
            conn.execute(text("ALTER TABLE reading_sessions ADD COLUMN end_anchor JSON"))

        # PersonalMetadata: progress_anchor
        pcols = {c["name"] for c in inspector.get_columns("personal_metadata")}
        if "progress_anchor" not in pcols:
            conn.execute(text("ALTER TABLE personal_metadata ADD COLUMN progress_anchor JSON"))

        # Backfill UUIDs for existing rows
        _backfill_uuids(conn, _uuid)

        # Unique indexes on uuid (partial to allow NULL during backfill window)
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_marginalia_uuid "
            "ON marginalia (uuid) WHERE uuid IS NOT NULL"
        ))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uix_reading_sessions_uuid "
            "ON reading_sessions (uuid) WHERE uuid IS NOT NULL"
        ))

    return True


def migrate_rename_text_chunks_to_book_content(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 11: rename text_chunks -> book_content with refined schema.

    - RENAME TABLE text_chunks -> book_content.
    - RENAME COLUMN chunk_index -> segment_index.
    - ADD COLUMN segment_type (default 'chunk-legacy' for existing rows).
    - ADD COLUMN title (nullable).
    - ADD COLUMN anchor (JSON, default '{}' for existing rows).
    - ADD COLUMN extractor_version (default 'legacy' for existing rows).
    - ADD COLUMN extraction_status (default 'ok').
    - ADD COLUMN archived_at (nullable).
    - DROP COLUMN has_embedding (per workspace 'no embeddings in archives').

    Existing rows are left in place with placeholder values marking them as
    legacy. The reindex-content CLI rewrites them from extracted files.
    """
    name = "rename_text_chunks_to_book_content"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        logger.debug(f"Migration {name} already applied")
        return False

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    if dry_run:
        logger.info("DRY RUN: would rename text_chunks -> book_content and refine schema")
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        # RENAME table if present and target not yet present.
        if "text_chunks" in tables and "book_content" not in tables:
            conn.execute(text("ALTER TABLE text_chunks RENAME TO book_content"))
        elif "book_content" not in tables:
            # Fresh install without text_chunks and without book_content.
            # Create a minimal book_content table; Base.metadata.create_all
            # may have already added it via the updated ORM; verify after.
            pass

        # Refresh inspector after rename.
        inspector = inspect(engine)
        if "book_content" not in set(inspector.get_table_names()):
            # ORM hasn't created it yet and no legacy table existed. Nothing to do.
            return True

        cols = {c["name"] for c in inspector.get_columns("book_content")}

        # RENAME chunk_index -> segment_index.
        if "chunk_index" in cols and "segment_index" not in cols:
            conn.execute(text("ALTER TABLE book_content RENAME COLUMN chunk_index TO segment_index"))

        # ADD COLUMNs (idempotent per-column).
        add_columns = [
            ("segment_type", "VARCHAR(20) NOT NULL DEFAULT 'chunk-legacy'"),
            ("title", "VARCHAR(500)"),
            ("anchor", "JSON NOT NULL DEFAULT '{}'"),
            ("extractor_version", "VARCHAR(50) NOT NULL DEFAULT 'legacy'"),
            ("extraction_status", "VARCHAR(20) NOT NULL DEFAULT 'ok'"),
            ("archived_at", "TIMESTAMP NULL"),
        ]
        cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
        for col_name, col_ddl in add_columns:
            if col_name not in cols:
                conn.execute(text(f"ALTER TABLE book_content ADD COLUMN {col_name} {col_ddl}"))

        # DROP has_embedding if present.
        cols = {c["name"] for c in inspect(engine).get_columns("book_content")}
        if "has_embedding" in cols:
            conn.execute(text("ALTER TABLE book_content DROP COLUMN has_embedding"))

        # Rebuild unique index on (file_id, segment_type, segment_index).
        # Old unique was (file_id, chunk_index); drop it if present.
        # Also drop the legacy non-unique idx_chunk_file index so that the
        # ORM's untouched-in-this-task TextChunk class can still call
        # create_all() on subsequent opens without colliding on the index
        # name (the index moved with the renamed table).
        existing_indexes = {ix["name"] for ix in inspect(engine).get_indexes("book_content")}
        if "uix_chunk" in existing_indexes:
            conn.execute(text("DROP INDEX uix_chunk"))
        if "idx_chunk_file" in existing_indexes:
            conn.execute(text("DROP INDEX idx_chunk_file"))
        if "uix_book_content_file_seg" not in existing_indexes:
            conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uix_book_content_file_seg "
                "ON book_content (file_id, segment_type, segment_index)"
            ))

    return True


def migrate_add_book_content_fts(library_path: Path, dry_run: bool = False) -> bool:
    """Migration 12: add book_content_fts virtual table plus sync triggers.

    FTS5 mirrors book_content's `content` + `title` columns. Uses external
    content addressing (content='book_content', content_rowid='id') so the
    FTS index and the row table stay in sync via AFTER INSERT/UPDATE/DELETE
    triggers. Matches the existing books_fts pattern.
    """
    name = "add_book_content_fts"
    engine = get_engine(library_path)
    ensure_schema_versions_table(engine)

    if is_migration_applied(engine, name):
        return False

    if dry_run:
        logger.info("DRY RUN: would create book_content_fts virtual table + triggers")
        return True

    inspector = inspect(engine)
    if "book_content" not in set(inspector.get_table_names()):
        # Nothing to index yet. The migration is still considered applied so
        # it isn't retried; run_all_migrations records it.
        return True

    logger.debug(f"Applying migration: {name}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS book_content_fts USING fts5(
                text,
                title,
                book_id UNINDEXED,
                content_id UNINDEXED,
                content='book_content',
                content_rowid='id',
                tokenize='porter unicode61'
            )
        """))

        # Populate from any existing rows.
        conn.execute(text("""
            INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
            SELECT bc.id, bc.content, COALESCE(bc.title, ''),
                   COALESCE(f.book_id, 0), bc.id
            FROM book_content bc
            LEFT JOIN files f ON f.id = bc.file_id
        """))

        # AFTER INSERT trigger.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_ai AFTER INSERT ON book_content BEGIN
                INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
                VALUES (new.id, new.content, COALESCE(new.title, ''),
                        (SELECT book_id FROM files WHERE id = new.file_id), new.id);
            END
        """))

        # AFTER UPDATE trigger (delete-then-reinsert for external content FTS5).
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_au AFTER UPDATE ON book_content BEGIN
                INSERT INTO book_content_fts (book_content_fts, rowid, text, title, book_id, content_id)
                VALUES ('delete', old.id, old.content, COALESCE(old.title, ''),
                        (SELECT book_id FROM files WHERE id = old.file_id), old.id);
                INSERT INTO book_content_fts (rowid, text, title, book_id, content_id)
                VALUES (new.id, new.content, COALESCE(new.title, ''),
                        (SELECT book_id FROM files WHERE id = new.file_id), new.id);
            END
        """))

        # AFTER DELETE trigger.
        conn.execute(text("""
            CREATE TRIGGER IF NOT EXISTS book_content_ad AFTER DELETE ON book_content BEGIN
                INSERT INTO book_content_fts (book_content_fts, rowid, text, title, book_id, content_id)
                VALUES ('delete', old.id, old.content, COALESCE(old.title, ''),
                        (SELECT book_id FROM files WHERE id = old.file_id), old.id);
            END
        """))

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
    (9, 'add_archived_at', migrate_add_archived_at),
    (10, 'add_uri_columns', migrate_add_uri_columns),
    (11, 'rename_text_chunks_to_book_content', migrate_rename_text_chunks_to_book_content),
    (12, 'add_book_content_fts', migrate_add_book_content_fts),
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
