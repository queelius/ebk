"""Read-only SQL executor with 3-layer security defense."""
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_AUTHORIZER_ALLOWED = frozenset({
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
})

_SELECT_PREFIX = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_MULTI_STATEMENT = re.compile(r";\s*\S")

DEFAULT_MAX_ROWS = 1000


def _sqlite_authorizer(action, arg1, arg2, db_name, trigger_name):
    """SQLite authorizer callback — only allows SELECT/READ/FUNCTION."""
    if action in _AUTHORIZER_ALLOWED:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


class ReadOnlySQLExecutor:
    """Execute read-only SQL against a library database with defense-in-depth."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def execute(
        self,
        sql: str,
        params: Optional[List[Any]] = None,
        max_rows: int = DEFAULT_MAX_ROWS,
    ) -> Dict[str, Any]:
        """Execute a read-only SQL query and return results as dict."""
        # Layer 1: Prefix check
        if not _SELECT_PREFIX.match(sql):
            return {"error": "Only SELECT queries are allowed"}

        # Check for multi-statement
        if _MULTI_STATEMENT.search(sql):
            return {"error": "Multiple SQL statements are not allowed"}

        try:
            # Layer 2: Read-only connection
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
            try:
                # Layer 3: Authorizer callback
                conn.set_authorizer(_sqlite_authorizer)
                cursor = conn.execute(sql, params or [])
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                rows = cursor.fetchmany(max_rows + 1)

                truncated = len(rows) > max_rows
                if truncated:
                    rows = rows[:max_rows]

                result = {
                    "columns": columns,
                    "rows": [list(row) for row in rows],
                    "row_count": len(rows),
                }
                if truncated:
                    result["truncated"] = True
                return result
            finally:
                conn.close()
        except sqlite3.Error as e:
            return {"error": str(e)}
