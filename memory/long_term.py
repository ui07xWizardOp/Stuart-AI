"""
Long-Term Memory System (Task 16.2)

Provides persistent Key-Value and Fact-based storage backed by SQLite.
Endures across complete device restarts and agent sessions to support persistent preferences.
"""

import sqlite3
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from observability import get_logging_system


class LongTermMemory:
    """
    Houses durable facts and preferences categorized logically.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.logger = get_logging_system()
        
        if db_path is None:
            # Default to a db inside the database folder
            base_dir = Path(__file__).parent.parent / "database"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(base_dir / "long_term_memory.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
        self._initialize_schema()
        self.logger.info(f"Long-Term Memory initialized at {self.db_path}")

    def _initialize_schema(self) -> None:
        """Create fact storage tables if they do not exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    UNIQUE(category, key)
                )
            """)
            conn.commit()

    def store_fact(self, category: str, key: str, value: Any) -> None:
        """
        Stores an arbitrary fact in persistent memory. Upserts if key exists in category.
        Values are serialized to JSON.
        """
        val_str = json.dumps(value)
        ts = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_facts (category, key, value, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(category, key) DO UPDATE SET
                    value=excluded.value,
                    timestamp=excluded.timestamp
            """, (category, key, val_str, ts))
            conn.commit()
            
        self.logger.debug(f"Stored long term fact -> [{category}] {key}")

    def retrieve_fact(self, category: str, key: str) -> Optional[Any]:
        """Fetches a specific entry from memory."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT value FROM memory_facts WHERE category=? AND key=?
            """, (category, key))
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0] # Fallback raw
        return None

    def retrieve_category(self, category: str) -> Dict[str, Any]:
        """Fetches an entire category of memory (e.g. 'user_preferences')."""
        results = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT key, value FROM memory_facts WHERE category=?
            """, (category,))
            rows = cursor.fetchall()
            
            for key, value_str in rows:
                try:
                    results[key] = json.loads(value_str)
                except json.JSONDecodeError:
                    results[key] = value_str
                    
        return results

    def search_facts(self, query: str) -> List[Dict[str, Any]]:
        """
        Provides crude keyword searching over keys and values.
        (Semantic semantic search comes in Task 17).
        """
        like_query = f"%{query}%"
        matches = []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT category, key, value, timestamp 
                FROM memory_facts 
                WHERE key LIKE ? OR value LIKE ?
                ORDER BY timestamp DESC
                LIMIT 50
            """, (like_query, like_query))
            
            for row in cursor.fetchall():
                d = dict(row)
                try:
                    d["value"] = json.loads(d["value"])
                except json.JSONDecodeError:
                    pass
                matches.append(d)
                
        return matches

    def delete_fact(self, category: str, key: str) -> bool:
        """Removes a fact from memory."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_facts WHERE category=? AND key=?", (category, key))
            conn.commit()
            return cursor.rowcount > 0
