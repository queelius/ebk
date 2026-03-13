"""MCP tool implementations for ebk."""
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import create_engine, inspect as sa_inspect

from ebk.db.models import Base


def get_schema_impl(db_path: Path) -> Dict[str, Any]:
    """Introspect the database and return a complete schema description.

    Uses SQLAlchemy's inspection API to extract table structure and
    the ORM registry to include relationship metadata.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Dict with {"tables": {table_name: {columns, foreign_keys, relationships}}}
    """
    engine = create_engine(f"sqlite:///{db_path}")
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
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("name") in {
                    pk_col for pk_col in (
                        inspector.get_pk_constraint(table_name).get("constrained_columns", [])
                    )
                },
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

    engine.dispose()
    return {"tables": tables}
