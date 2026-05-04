import pytest
from unittest.mock import MagicMock, patch
from core.orchestrator import Orchestrator
from memory.short_term import MemoryRole

@pytest.fixture
def mock_orchestrator():
    # Mocking dependencies for Orchestrator
    with patch("core.orchestrator.MemorySystem"), \
         patch("core.orchestrator.ModelRouter"), \
         patch("core.orchestrator.PromptManager"), \
         patch("core.orchestrator.SessionCheckpoint"):
        
        mock_checkpoint = MagicMock()
        orch = Orchestrator(
            event_bus=MagicMock(),
            memory=MagicMock(),
            router=MagicMock(),
            prompt_manager=MagicMock(),
            executor=MagicMock(),
            context_manager=MagicMock(),
            checkpoint=mock_checkpoint
        )
        return orch

def test_replay_events(mock_orchestrator):
    events = [
        {"role": "thought", "content": "I need to search for weather"},
        {"role": "observation", "content": "The weather is sunny", "metadata": {"tool": "weather_tool"}}
    ]
    
    mock_orchestrator.replay_events(events)
    
    # Verify that memory.commit_interaction was called
    assert mock_orchestrator.memory.commit_interaction.call_count == 2
    
    # Check first call
    args1 = mock_orchestrator.memory.commit_interaction.call_args_list[0]
    assert args1[0][0] == MemoryRole.THOUGHT
    assert args1[0][1] == "I need to search for weather"

def test_hydrate_session_no_checkpoint(mock_orchestrator):
    mock_orchestrator.checkpoint = None
    mock_orchestrator.hydrate_session("session_123")
    assert mock_orchestrator.memory.commit_interaction.call_count == 0

def test_hydrate_session_with_data(mock_orchestrator):
    mock_data = {
        "state": {
            "history": [
                {"role": "user", "content": "Hello"},
                {"role": "agent", "content": "Hi there!"}
            ]
        }
    }
    mock_orchestrator.checkpoint.load_latest.return_value = mock_data
    
    mock_orchestrator.hydrate_session("session_123")
    
    assert mock_orchestrator.memory.commit_interaction.call_count == 2
    args1 = mock_orchestrator.memory.commit_interaction.call_args_list[0]
    assert args1[0][0] == MemoryRole.USER
    assert args1[0][1] == "Hello"
