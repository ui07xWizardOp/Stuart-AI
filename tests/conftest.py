"""
Pytest configuration for Stuart-AI test suite.
Ensures the project root is on sys.path so all package imports resolve.
"""

import sys
import os

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock heavy/external dependencies to allow test collection
from unittest.mock import MagicMock
import sys

# Mock database
mock_psycopg2 = MagicMock()
sys.modules["psycopg2"] = mock_psycopg2
sys.modules["psycopg2.extras"] = MagicMock()
sys.modules["psycopg2.pool"] = MagicMock()

# Mock Qdrant
import types
qdrant_mock = MagicMock()
sys.modules["qdrant_client"] = qdrant_mock
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["qdrant_client.http.models"] = MagicMock()
sys.modules["qdrant_client.models"] = MagicMock()

# Mock OpenAI
sys.modules["openai"] = MagicMock()

# Mock other external tools
sys.modules["schedule"] = MagicMock()
sys.modules["watchdog"] = MagicMock()
sys.modules["watchdog.observers"] = MagicMock()
sys.modules["watchdog.events"] = MagicMock()

# Mock Observability to avoid "Logging system not initialized"
mock_obs = MagicMock()
sys.modules["observability"] = mock_obs
# Ensure get_logging_system returns a mock logger that has info/error methods
mock_logger = MagicMock()
mock_obs.get_logging_system.return_value = mock_logger
mock_obs.get_tracing_system.return_value = MagicMock()

# Mock Events
mock_events = MagicMock()
sys.modules["events"] = mock_events
sys.modules["events.event_bus"] = MagicMock()
mock_events.get_event_bus.return_value = MagicMock()
