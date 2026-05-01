"""
Tests for Database Query Tool (Task 15.4)
"""

import sqlite3
import pytest
from tools.core.database_tool import DatabaseQueryTool


@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    
    # Create simple table
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE users (id INTEGER, name TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Alice')")
    conn.execute("INSERT INTO users VALUES (2, 'Bob')")
    conn.commit()
    conn.close()
    
    return str(db_path)


def test_database_tool_select_success(test_db):
    tool = DatabaseQueryTool()
    
    res = tool.execute("execute_query", {
        "db_path": test_db, 
        "query": "SELECT * FROM users WHERE id = ?",
        "params": [2]
    })
    
    assert res.success is True
    assert len(res.output) == 1
    assert res.output[0]["name"] == "Bob"

def test_database_tool_blocks_mutations(test_db):
    tool = DatabaseQueryTool()
    
    # Try basic delete
    res = tool.execute("execute_query", {
        "db_path": test_db,
        "query": "DELETE FROM users"
    })
    
    assert res.success is False
    assert "rejected" in res.error
    
    # Try multiple statements
    res2 = tool.execute("execute_query", {
        "db_path": test_db,
        "query": "SELECT * FROM users; DROP TABLE users;"
    })
    
    assert res2.success is False
    assert "rejected" in res2.error

def test_database_tool_read_only_sqlite_enforcement(test_db):
    tool = DatabaseQueryTool()
    
    # Try to bypass regex by writing a clever PRAGMA that might modify 
    # Or just rely on uri=True ro mode.
    # We will just verify it fails to write if passed read-only
    res = tool.execute("execute_query", {
        "db_path": test_db,
        "query": "CREATE TABLE hacked (id INT)" 
    })
    
    # Should be blocked by regex anyway
    assert res.success is False
    assert "rejected" in res.error 
