"""
Tests for Long-Term Memory System (Task 16.2)
"""

import sys
import pytest
from unittest.mock import Mock, MagicMock

# Mock observability module

from memory.long_term import LongTermMemory


@pytest.fixture
def test_ltm(tmp_path):
    db_path = str(tmp_path / "test_long_term.db")
    return LongTermMemory(db_path=db_path)

def test_long_term_store_retrieve(test_ltm):
    test_ltm.store_fact("preferences", "theme", "dark")
    
    val = test_ltm.retrieve_fact("preferences", "theme")
    assert val == "dark"
    
def test_long_term_upsert(test_ltm):
    test_ltm.store_fact("user", "name", "Alice")
    test_ltm.store_fact("user", "name", "Bob")
    
    val = test_ltm.retrieve_fact("user", "name")
    assert val == "Bob"

def test_long_term_complex_types(test_ltm):
    prefs = {"notifications": False, "volume": 11}
    test_ltm.store_fact("settings", "app", prefs)
    
    val = test_ltm.retrieve_fact("settings", "app")
    assert isinstance(val, dict)
    assert val["volume"] == 11
    
def test_long_term_retrieve_category(test_ltm):
    test_ltm.store_fact("cat1", "k1", "v1")
    test_ltm.store_fact("cat1", "k2", "v2")
    test_ltm.store_fact("cat2", "kx", "vx")
    
    cat = test_ltm.retrieve_category("cat1")
    assert len(cat) == 2
    assert cat["k1"] == "v1"
    assert "kx" not in cat

def test_long_term_search(test_ltm):
    test_ltm.store_fact("notes", "idea", "build a robot")
    
    res = test_ltm.search_facts("robot")
    assert len(res) == 1
    assert res[0]["key"] == "idea"
    assert res[0]["value"] == "build a robot"

def test_long_term_delete(test_ltm):
    test_ltm.store_fact("temp", "x", "1")
    assert test_ltm.retrieve_fact("temp", "x") == "1"
    
    test_ltm.delete_fact("temp", "x")
    assert test_ltm.retrieve_fact("temp", "x") is None
