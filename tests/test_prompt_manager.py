"""
Tests for Prompt Manager (Task 10)
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Mock observability module

# Mock events module
mock_event_bus = MagicMock()

from cognitive.prompt_manager import PromptManager


def test_prompt_inline_fallback(tmp_path):
    manager = PromptManager(prompts_directory=str(tmp_path))
    
    # Should fall back to inline default if file missing
    text = manager.get_prompt_text("intent_classification", "v1")
    assert "Classify the following user command" in text


def test_prompt_render_success(tmp_path):
    # Setup test file
    test_file = tmp_path / "hello_v1.txt"
    test_file.write_text("Hello {name}, welcome to {place}!", encoding="utf-8")
    
    manager = PromptManager(prompts_directory=str(tmp_path))
    rendered = manager.render_prompt("hello", "v1", name="Alice", place="Wonderland")
    
    assert rendered == "Hello Alice, welcome to Wonderland!"


def test_prompt_render_missing_args(tmp_path):
    # Setup test file
    test_file = tmp_path / "hello_v1.txt"
    test_file.write_text("Hello {name}!", encoding="utf-8")
    
    manager = PromptManager(prompts_directory=str(tmp_path))
    
    try:
        manager.render_prompt("hello", "v1")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "missing parameter" in str(e)


def test_prompt_caching(tmp_path):
    # Setup test file
    test_file = tmp_path / "cachetest_v1.txt"
    test_file.write_text("Version A", encoding="utf-8")
    
    manager = PromptManager(prompts_directory=str(tmp_path))
    res1 = manager.get_prompt_text("cachetest", "v1")
    assert res1 == "Version A"
    
    # Modify file directly behind its back but without triggering mtime change dramatically
    # We'll just test that `clear_cache` drops it.
    test_file.write_text("Version B", encoding="utf-8")
    
    manager.clear_cache()
    res2 = manager.get_prompt_text("cachetest", "v1")
    assert res2 == "Version B"
