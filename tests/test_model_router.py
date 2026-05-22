"""
Tests for Model Router (Task 9)
"""

import sys
from unittest.mock import Mock, MagicMock
import time

# Mock observability module

# Mock hybrid_planner

from core.model_router import ModelRouter, ModelTier, ModelEndpoint, CircuitBreaker

def test_circuit_breaker():
    breaker = CircuitBreaker(failure_threshold=2, reset_timeout_sec=0.1)
    
    assert breaker.is_available() is True
    
    breaker.record_failure()
    assert breaker.is_available() is True
    
    breaker.record_failure()
    assert breaker.is_available() is False
    
    # Wait for reset timeout
    time.sleep(0.15)
    assert breaker.is_available() is True
    assert breaker.state == "HALF_OPEN"
    
    breaker.record_success()
    assert breaker.is_available() is True
    assert breaker.state == "CLOSED"


def test_model_selection():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.BALANCED, 100, 0, 0),
        ModelEndpoint("p3", "m3", ModelTier.REASONING, 50, 0, 0),
    ])
    
    # Select exact match
    sel = router.select_model(ModelTier.FAST_CHEAP)
    assert sel.provider == "p1"
    
    # Select higher tier
    sel = router.select_model(ModelTier.BALANCED)
    assert sel.provider == "p2"
    
def test_fallback_selection():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.BALANCED, 100, 0, 0),
    ])
    
    # Select reasoning (doesn't exist, should fallback to best available)
    sel = router.select_model(ModelTier.REASONING, fallback_allowed=True)
    # The current fallback logic just returns the first available if no strict matches
    assert sel is not None
    
def test_failover_execution():
    router = ModelRouter([
        ModelEndpoint("p1", "m1", ModelTier.FAST_CHEAP, 1000, 0, 0),
        ModelEndpoint("p2", "m2", ModelTier.FAST_CHEAP, 800, 0, 0),
    ])
    
    # Mock function that fails on the first endpoint but succeeds on second
    call_count = 0
    def mock_call(endpoint):
        nonlocal call_count
        call_count += 1
        if endpoint.provider == "p1":
            raise ValueError("API error")
        return "success"
        
    result = router.execute_with_failover(mock_call, ModelTier.FAST_CHEAP)
    
    assert result == "success"
    assert call_count == 2
    assert router.circuit_breakers["p1:m1"].failures == 1
    assert router.circuit_breakers["p2:m2"].failures == 0


def test_default_endpoints_initialization():
    router = ModelRouter()
    assert len(router.endpoints) == 4
    
    # Check default models for each tier
    fast_cheap_ep = router.select_model(ModelTier.FAST_CHEAP)
    assert fast_cheap_ep.provider == "ollama"
    assert fast_cheap_ep.model == "llama3:latest"
    
    balanced_ep = router.select_model(ModelTier.BALANCED)
    assert balanced_ep.provider == "openai"
    assert balanced_ep.model == "gpt-4o-mini"
    
    reasoning_ep = router.select_model(ModelTier.REASONING)
    assert reasoning_ep.provider == "openai"
    assert reasoning_ep.model == "gpt-4o"
    
    max_compute_ep = router.select_model(ModelTier.MAX_COMPUTE)
    assert max_compute_ep.provider == "openai"
    assert max_compute_ep.model == "gpt-4o"


def test_complexity_routing_execution():
    router = ModelRouter()
    mock_local = MagicMock()
    mock_cloud = MagicMock()
    router.local_client = mock_local
    router.cloud_client = mock_cloud
    
    # 1. FAST_CHEAP (Ollama)
    messages_cheap = [{"role": "user", "content": "Hello"}]
    mock_local.generate_chat.return_value = "local_response"
    res = router.execute_with_failover(messages_cheap)
    assert res == "local_response"
    mock_local.generate_chat.assert_called_once_with(messages_cheap, model_name="llama3:latest")
    mock_local.reset_mock()
    
    # 2. BALANCED (Cloud / openai)
    messages_balanced = [{"role": "user", "content": "Hello " * 700}]
    mock_cloud.generate_chat.return_value = "balanced_response"
    res = router.execute_with_failover(messages_balanced)
    assert res == "balanced_response"
    mock_cloud.generate_chat.assert_called_once_with(messages_balanced, model_name="gpt-4o-mini")
    mock_cloud.reset_mock()
    
    # 3. REASONING (Cloud / openai)
    messages_reasoning = [{"role": "user", "content": "Write a python script to sort a list"}]
    mock_cloud.generate_chat.return_value = "reasoning_response"
    res = router.execute_with_failover(messages_reasoning)
    assert res == "reasoning_response"
    mock_cloud.generate_chat.assert_called_once_with(messages_reasoning, model_name="gpt-4o")
    mock_cloud.reset_mock()
    
    # 4. MAX_COMPUTE (Cloud / openai)
    messages_max = [{"role": "user", "content": "Explain distributed system design"}]
    mock_cloud.generate_chat.return_value = "max_response"
    res = router.execute_with_failover(messages_max)
    assert res == "max_response"
    mock_cloud.generate_chat.assert_called_once_with(messages_max, model_name="gpt-4o")


from unittest.mock import patch

@patch('requests.post')
def test_ollama_client_overrides_and_chat(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "mocked local response"}}
    mock_response.raise_for_status = MagicMock()
    mock_post.return_value = mock_response
    
    from core.llm_clients import OllamaClient
    client = OllamaClient()
    
    messages = [{"role": "user", "content": "test"}]
    res = client.chat(messages, model_name="custom-llama", temperature=0.7)
    
    assert res == "mocked local response"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs['json']['model'] == "custom-llama"
    assert kwargs['json']['options']['temperature'] == 0.7


def test_openai_client_overrides_and_chat():
    from core.llm_clients import OpenAIClient
    
    client = OpenAIClient()
    mock_openai_client = MagicMock()
    client.client = mock_openai_client
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "mocked cloud response"
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    messages = [{"role": "user", "content": "test"}]
    res = client.chat(messages, model_name="gpt-o1-custom", temperature=0.0)
    
    assert res == "mocked cloud response"
    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-o1-custom",
        messages=messages,
        temperature=0.0
    )

