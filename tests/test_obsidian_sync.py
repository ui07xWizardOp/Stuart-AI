"""
Tests for Obsidian Sync System (Task 17.1)
"""

import os
from pathlib import Path
import pytest
from unittest.mock import Mock, MagicMock
import sys

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

from obsidian_sync import ObsidianVaultSynchronizer

def test_markdown_parsing(tmp_path):
    # Setup test file
    vault = tmp_path / "test_vault"
    vault.mkdir()
    
    file_path = vault / "test_note.md"
    file_content = "---\ntags: [ai, math]\ncategory: test\n---\n# Header\nThis is the body."
    file_path.write_text(file_content, encoding='utf-8')
    
    sync = ObsidianVaultSynchronizer(str(vault))
    docs = sync.read_all_documents()
    
    assert len(docs) == 1
    doc = docs[0]
    
    assert "test_note.md" in doc.filepath
    assert "# Header" in doc.content
    assert "This is the body." in doc.content
    assert "---" not in doc.content # Frontmatter should be stripped
    
    assert doc.frontmatter.get("category") == "test"
    assert doc.frontmatter.get("tags") == "[ai, math]"
