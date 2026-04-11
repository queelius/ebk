"""MCP tool implementations for ebk."""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from ebk.db.models import Base, Book, Author, Subject, Tag, PersonalMetadata
from ebk.mcp.sql_executor import ReadOnlySQLExecutor


def get_schema_impl(session: Session) -> Dict[str, Any]:
    """Introspect the database and return a complete schema description.

    Uses SQLAlchemy's inspection API to extract table structure and
    the ORM registry to include relationship metadata.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Dict with {"tables": {table_name: {columns, foreign_keys, relationships}}}
    """
    engine = session.get_bind()
    inspector = sa_inspect(engine)

    # Build a mapping from table name -> list of relationships using ORM mappers
    table_relationships: Dict[str, list] = {}
    for mapper in Base.registry.mappers:
        table_name = mapper.local_table.name
        rels = []
        for rel in mapper.relationships:
            rels.append({
                "name": rel.key,
                "target": rel.mapper.local_table.name,
                "direction": rel.direction.name,
            })
        table_relationships[table_name] = rels

    tables = {}
    for table_name in inspector.get_table_names():
        # Columns
        pk_columns = set(
            inspector.get_pk_constraint(table_name).get("constrained_columns", [])
        )
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col["name"] in pk_columns,
            })

        # Foreign keys
        foreign_keys = []
        for fk in inspector.get_foreign_keys(table_name):
            foreign_keys.append({
                "constrained_columns": fk["constrained_columns"],
                "referred_table": fk["referred_table"],
                "referred_columns": fk["referred_columns"],
            })

        # Relationships (from ORM mappers)
        relationships = table_relationships.get(table_name, [])

        tables[table_name] = {
            "columns": columns,
            "foreign_keys": foreign_keys,
            "relationships": relationships,
        }

    return {"tables": tables}


def execute_sql_impl(
    db_path: Path,
    sql: str,
    params: Optional[List[Any]] = None,
    max_rows: int = 1000,
) -> Dict[str, Any]:
    """Execute a read-only SQL query against the library database."""
    executor = ReadOnlySQLExecutor(db_path)
    return executor.execute(sql, params=params, max_rows=max_rows)


# ---------------------------------------------------------------------------
# update_books_impl helpers
# ---------------------------------------------------------------------------

def _get_book_columns() -> Set[str]:
    """Get updatable column names from Book model."""
    mapper = sa_inspect(Book)
    skip = {"id", "unique_id", "created_at", "updated_at"}
    return {c.key for c in mapper.column_attrs if c.key not in skip}


def _get_personal_columns() -> Set[str]:
    """Get updatable column names from PersonalMetadata model."""
    mapper = sa_inspect(PersonalMetadata)
    skip = {"id", "book_id"}
    return {c.key for c in mapper.column_attrs if c.key not in skip}


_COLLECTION_OPS = {"add_tags", "remove_tags", "add_authors", "remove_authors",
                   "add_subjects", "remove_subjects"}
_SPECIAL_OPS = {"merge_into"}


def update_books_impl(
    session: Session,
    updates: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply updates to books. Returns {updated: [...], errors: {...}}."""
    book_cols = _get_book_columns()
    personal_cols = _get_personal_columns()
    updated = []
    errors = {}

    for book_id_str, fields in updates.items():
        try:
            book_id = int(book_id_str)
        except (ValueError, TypeError):
            errors[book_id_str] = f"Invalid book ID: {book_id_str!r}"
            continue

        try:
            with session.begin_nested():
                book = session.get(Book, book_id)
                if not book:
                    errors[book_id] = f"Book {book_id} not found"
                    continue

                # Check merge_into exclusivity
                if "merge_into" in fields:
                    if len(fields) > 1:
                        errors[book_id] = "merge_into is mutually exclusive with other fields"
                        continue
                    _merge_book(session, book, fields["merge_into"])
                    updated.append(book_id)
                    continue

                # Validate all fields first
                unknown = set(fields.keys()) - book_cols - personal_cols - _COLLECTION_OPS - _SPECIAL_OPS
                if unknown:
                    errors[book_id] = f"Unknown fields: {', '.join(sorted(unknown))}"
                    continue

                # Apply scalar Book fields
                for key in set(fields.keys()) & book_cols:
                    setattr(book, key, fields[key])

                # Apply PersonalMetadata fields
                pm_fields = set(fields.keys()) & personal_cols
                if pm_fields:
                    if not book.personal:
                        book.personal = PersonalMetadata(book_id=book.id)
                        session.add(book.personal)
                    for key in pm_fields:
                        setattr(book.personal, key, fields[key])

                # Apply collection operations
                _apply_collection_ops(session, book, fields)

                updated.append(book_id)
        except Exception as e:
            errors[book_id] = str(e)

    session.commit()
    return {"updated": updated, "errors": errors}


def _merge_book(session: Session, source: Book, target_id: int):
    """Merge source book into target, moving all associated data."""
    target = session.get(Book, target_id)
    if not target:
        raise ValueError(f"Target book {target_id} not found")
    # Move files and covers
    for f in source.files:
        f.book_id = target_id
    for c in source.covers:
        c.book_id = target_id
    # Merge collections (add missing)
    for a in source.authors:
        if a not in target.authors:
            target.authors.append(a)
    for s in source.subjects:
        if s not in target.subjects:
            target.subjects.append(s)
    for t in source.tags:
        if t not in target.tags:
            target.tags.append(t)
    session.delete(source)


def _apply_collection_ops(session: Session, book: Book, fields: Dict[str, Any]):
    """Apply add_/remove_ collection operations."""
    if "add_tags" in fields:
        for tag_path in fields["add_tags"]:
            _ensure_tag(session, book, tag_path)
    if "remove_tags" in fields:
        remove_paths = set(fields["remove_tags"])
        book.tags = [t for t in book.tags if t.path not in remove_paths]
    if "add_authors" in fields:
        for name in fields["add_authors"]:
            author = session.query(Author).filter_by(name=name).first()
            if not author:
                author = Author(name=name, sort_name=name)
                session.add(author)
            if author not in book.authors:
                book.authors.append(author)
    if "remove_authors" in fields:
        remove_names = set(fields["remove_authors"])
        book.authors = [a for a in book.authors if a.name not in remove_names]
    if "add_subjects" in fields:
        for name in fields["add_subjects"]:
            subject = session.query(Subject).filter_by(name=name).first()
            if not subject:
                subject = Subject(name=name)
                session.add(subject)
            if subject not in book.subjects:
                book.subjects.append(subject)
    if "remove_subjects" in fields:
        remove_names = set(fields["remove_subjects"])
        book.subjects = [s for s in book.subjects if s.name not in remove_names]


def _ensure_tag(session: Session, book: Book, tag_path: str):
    """Create tag hierarchy if needed and add to book."""
    tag = session.query(Tag).filter_by(path=tag_path).first()
    if not tag:
        parts = tag_path.split("/")
        parent = None
        for i, part in enumerate(parts):
            partial_path = "/".join(parts[:i + 1])
            existing = session.query(Tag).filter_by(path=partial_path).first()
            if existing:
                parent = existing
            else:
                new_tag = Tag(name=part, path=partial_path, parent_id=parent.id if parent else None)
                session.add(new_tag)
                session.flush()
                parent = new_tag
        tag = parent
    if tag and tag not in book.tags:
        book.tags.append(tag)
