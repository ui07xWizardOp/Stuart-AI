"""
Tests for FileManagerTool (Task 15.1)
"""

import os
from pathlib import Path
import pytest
from file_manager import FileManagerTool


def test_file_manager_happy_path(tmp_path):
    tool = FileManagerTool(sandbox_dir=str(tmp_path))
    
    # Write a file
    res = tool.execute("write_file", {"path": "test.txt", "content": "Hello World"})
    assert res.success is True
    
    # Read the file
    res = tool.execute("read_file", {"path": "test.txt"})
    assert res.success is True
    assert res.output == "Hello World"
    
    # List dir
    res = tool.execute("list_directory", {"path": "."})
    assert res.success is True
    assert "test.txt" in res.output

    # Rename / move
    res = tool.execute("move_path", {"path": "test.txt", "destination": "moved.txt"})
    assert res.success is True
    
    # Old is gone
    res = tool.execute("read_file", {"path": "test.txt"})
    assert res.success is False
    assert "does not exist" in res.error

def test_file_manager_sandbox_escape(tmp_path):
    tool = FileManagerTool(sandbox_dir=str(tmp_path / "sandbox"))
    
    res = tool.execute("write_file", {"path": "../escaped.txt", "content": "Hacked"})
    # It should gracefully fail returning ToolResult(success=False, error=...)
    assert res.success is False
    assert "traversal detected" in res.error

def test_file_manager_overwrite_protection(tmp_path):
    tool = FileManagerTool(sandbox_dir=str(tmp_path))
    
    tool.execute("write_file", {"path": "fixed.txt", "content": "A"})
    
    # Fails by default
    res = tool.execute("write_file", {"path": "fixed.txt", "content": "B"})
    assert res.success is False
    assert "already exists" in res.error
    
    # Succeeds with override
    res = tool.execute("write_file", {"path": "fixed.txt", "content": "B", "overwrite": True})
    assert res.success is True
    assert tool.execute("read_file", {"path": "fixed.txt"}).output == "B"
