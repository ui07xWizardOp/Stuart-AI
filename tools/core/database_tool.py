"""
Database Query Tool (Task 15.4)

Provides safe, read-only generic SQL bindings for querying local or external databases.
Actively denies data mutation patterns like INSERT, UPDATE, or DROP.
"""

import sqlite3
import re
from typing import Dict, Any, List

from tools.base import BaseTool, CapabilityDescriptor, ToolRiskLevel, ToolResult


class DatabaseQueryTool(BaseTool):
    
    name = "database_query"
    description = "Executes read-only (SELECT) queries against a local SQLite database."
    version = "1.0.0"
    category = "database"
    risk_level = ToolRiskLevel.MEDIUM
    
    parameter_schema = {
        "type": "object",
        "properties": {
            "db_path": {"type": "string", "description": "Absolute or relative path to the SQLite DB file."},
            "query": {"type": "string", "description": "The SQL SELECT query to run."},
            "params": {"type": ["array", "object"], "description": "Parameters to bind preventing SQL injection."}
        },
        "required": ["db_path", "query"]
    }
    
    capabilities = [
        CapabilityDescriptor("execute_query", "Execute a read-only SQL SELECT Query.", ["db_path", "query"])
    ]

    def _is_safe_query(self, query: str) -> bool:
        """
        Regex heuristic to block modifications.
        This provides a software defense layer. The best defense is a properly restricted DB user,
        but since SQLite lacks user roles, we rely heavily on explicit pattern blocking.
        """
        # Remove comments to avoid hiding dangerous commands
        q_no_comments = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
        q_no_comments = re.sub(r'/\*.*?\*/', '', q_no_comments, flags=re.DOTALL)
        
        # Check against explicitly dangerous DML/DDL starting commands
        q_upper = q_no_comments.strip().upper()
        
        # Must start with SELECT or PRAGMA (sometimes needed for table info)
        if not (q_upper.startswith("SELECT ") or q_upper.startswith("PRAGMA ")):
             return False
             
        # Additionally, scan for banned substrings anywhere in the query just in case 
        # there are multi-statements like `SELECT * FROM users; DROP TABLE users;`
        banned_phrases = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ", "TRUNCATE ", "REPLACE ", "GRANT ", "REVOKE "]
        
        for phrase in banned_phrases:
            if re.search(r'\b' + phrase, q_upper):
                return False
                
        return True

    def execute(self, action: str, parameters: Dict[str, Any], context: Any = None) -> ToolResult:
        if action != "execute_query":
             return ToolResult(success=False, error=f"Unknown capability action: {action}", output=None)

        db_path = parameters["db_path"]
        query = parameters["query"]
        params = parameters.get("params", ())
        
        # 1. SQL Injection / Mutation Protection
        if not self._is_safe_query(query):
            return ToolResult(
                success=False, 
                error="Query rejected. Only standalone SELECT/PRAGMA statements are permitted. Mutations (INSERT/UPDATE/DROP/multiple statements) are forbidden.",
                output=None
            )

        # 2. Execution
        try:
            # Note: We enforce read-only locally using regex and `uri=True` SQLite read-only mode if Python supports it for local files.
            # Convert to uri format string
            uri_path = f"file:{db_path}?mode=ro"
            
            # Use check_same_thread=False since this is short lived, and uri=True
            with sqlite3.connect(uri_path, uri=True) as conn:
                conn.row_factory = sqlite3.Row  # To return dict-style rows
                cursor = conn.cursor()
                
                # Use parameterized query execution
                if isinstance(params, list):
                    cursor.execute(query, tuple(params))
                else:
                    cursor.execute(query, params)
                    
                records = [dict(row) for row in cursor.fetchall()]

            return ToolResult(success=True, output=records)

        except sqlite3.Error as e:
            return ToolResult(success=False, error=f"SQLite Error: {str(e)}", output=None)
        except Exception as e:
            return ToolResult(success=False, error=f"Database tool error: {str(e)}", output=None)
