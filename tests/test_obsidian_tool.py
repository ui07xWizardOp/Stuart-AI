"""
Tests for Obsidian Tool Wrapper (Task 17.4)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch

# Mock observability module
mock_logger = MagicMock()
sys.modules['observability'] = MagicMock()
sys.modules['observability'].get_logging_system = Mock(return_value=mock_logger)

# We need to mock OpenAI and Qdrant before importing ObsidianTool since it initializes them
with patch('knowledge.vector_db.QdrantClient'):
    with patch('knowledge.vectorizer.openai.Client'):
        from tools.core.obsidian_tool import ObsidianTool

def test_obsidian_tool_write_note(tmp_path):
    vault = tmp_path / "vault"
    
    # Needs mock instances because __init__ hit the mocked classes
    with patch.object(ObsidianTool, '__init__', lambda self, v: setattr(self, 'vault_path', Path(v))):
        tool = ObsidianTool(str(vault))
        tool.vault_path.mkdir(parents=True, exist_ok=True)
        
        tool.execute("write_note", {
            "filename": "ideas",
            "content": "# Big Idea\nRobots are cool.",
            "tags": ["future", "tech"]
        })
        
        file = vault / "ideas.md"
        assert file.exists()
        
        content = file.read_text(encoding='utf-8')
        assert "---" in content
        assert "author: Stuart-AI" in content
        assert "tags: [future, tech]" in content
        assert "Robots are cool." in content

def test_obsidian_tool_read_note(tmp_path):
    vault = tmp_path / "vault2"
    vault.mkdir()
    
    file = vault / "diary.md"
    file.write_text("Hello there!")
    
    with patch.object(ObsidianTool, '__init__', lambda self, v: setattr(self, 'vault_path', Path(v))):
        tool = ObsidianTool(str(vault))
        
        res = tool.execute("read_note", {"filename": "diary.md"})
        assert res.success is True
        assert res.output == "Hello there!"
