"""Database compatibility layer.

Provides a minimal `get_db_connection` used by runtime modules in environments
where the production database package is not installed.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3 connection as a safe default backend.

    Uses in-memory DB unless STUART_DB_PATH is set or a path is passed.
    """
    path = db_path or os.getenv("STUART_DB_PATH") or ":memory:"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn
