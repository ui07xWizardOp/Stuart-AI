"""
Tests for StuartHealthMonitor (Periodic Health Checks)
"""

import sys
from unittest.mock import Mock, MagicMock, patch

# Mock the psutil module so tests run even if it is not installed
mock_psutil = MagicMock()
sys.modules['psutil'] = mock_psutil

import pytest
from automation.health_monitor import StuartHealthMonitor
from events.event_bus import EventBus
from events.event_types import Event, EventType, EventSeverity

def test_health_monitor_init():
    event_bus = MagicMock(spec=EventBus)
    orchestrator = MagicMock()
    cron_manager = MagicMock()
    file_access_guard = MagicMock()

    monitor = StuartHealthMonitor(
        event_bus=event_bus,
        orchestrator=orchestrator,
        cron_manager=cron_manager,
        file_access_guard=file_access_guard,
        check_interval=10
    )

    assert monitor.event_bus == event_bus
    assert monitor.orchestrator == orchestrator
    assert monitor.cron_manager == cron_manager
    assert monitor.file_access_guard == file_access_guard
    assert monitor.check_interval == 10
    assert monitor.running is False

def test_health_monitor_all_healthy():
    event_bus = MagicMock(spec=EventBus)
    orchestrator = MagicMock()
    
    # Router status
    router_mock = MagicMock()
    router_mock.get_status.return_value = {
        "ollama": {"state": "closed"},
        "cloud": {"state": "closed"},
        "quota": {}
    }
    orchestrator.router = router_mock
    
    # Compactor status
    compactor_mock = MagicMock()
    compactor_mock.get_status.return_value = {}
    orchestrator.compactor = compactor_mock

    # Checkpoint status
    checkpoint_mock = MagicMock()
    checkpoint_mock.get_status.return_value = {}
    orchestrator.checkpoint = checkpoint_mock

    # Cron manager status
    cron_mock = MagicMock()
    cron_mock.get_status.return_value = {"scheduler_running": True}
    
    # File guard status
    guard_mock = MagicMock()
    guard_mock.get_status.return_value = {}

    monitor = StuartHealthMonitor(
        event_bus=event_bus,
        orchestrator=orchestrator,
        cron_manager=cron_mock,
        file_access_guard=guard_mock,
        check_interval=10
    )

    with patch("shutil.disk_usage") as mock_disk:
        # Mock 50% free disk space (e.g. total=100, used=50, free=50)
        mock_disk.return_value = (100, 50, 50)
        
        # Mock 50% memory usage
        mem_instance = MagicMock()
        mem_instance.percent = 50.0
        mock_psutil.virtual_memory.return_value = mem_instance

        monitor.perform_checks()

    # Since everything is healthy, no events should be published
    event_bus.publish.assert_not_called()

def test_health_monitor_low_disk():
    event_bus = MagicMock(spec=EventBus)
    orchestrator = MagicMock()
    
    # Subsystem states: healthy
    orchestrator.router.get_status.return_value = {"ollama": {"state": "closed"}, "cloud": {"state": "closed"}}
    orchestrator.compactor.get_status.return_value = {}
    orchestrator.checkpoint.get_status.return_value = {}
    cron_mock = MagicMock()
    cron_mock.get_status.return_value = {"scheduler_running": True}
    guard_mock = MagicMock()
    guard_mock.get_status.return_value = {}

    monitor = StuartHealthMonitor(
        event_bus=event_bus,
        orchestrator=orchestrator,
        cron_manager=cron_mock,
        file_access_guard=guard_mock,
        check_interval=10
    )

    with patch("shutil.disk_usage") as mock_disk:
        # Mock 5% free disk space (e.g. total=100, used=95, free=5) -> trips < 10%
        mock_disk.return_value = (100, 95, 5)
        
        # Mock 50% memory usage
        mem_instance = MagicMock()
        mem_instance.percent = 50.0
        mock_psutil.virtual_memory.return_value = mem_instance

        monitor.perform_checks()

    # Verify event bus received failure event
    assert event_bus.publish.call_count == 1
    published_event = event_bus.publish.call_args[0][0]
    assert published_event.event_type == EventType.HEALTH_CHECK_FAILED.value
    assert published_event.severity == EventSeverity.PRIORITY
    assert "disk space" in published_event.payload["message"]

def test_health_monitor_subsystem_down():
    event_bus = MagicMock(spec=EventBus)
    orchestrator = MagicMock()
    
    # Subsystem states: Router is missing, Compactor throws an exception
    orchestrator.router = None
    orchestrator.compactor.get_status.side_effect = Exception("Compactor error")
    orchestrator.checkpoint.get_status.return_value = {}
    
    cron_mock = MagicMock()
    # Cron scheduler not running
    cron_mock.get_status.return_value = {"scheduler_running": False}
    
    guard_mock = MagicMock()
    guard_mock.get_status.return_value = {}

    monitor = StuartHealthMonitor(
        event_bus=event_bus,
        orchestrator=orchestrator,
        cron_manager=cron_mock,
        file_access_guard=guard_mock,
        check_interval=10
    )

    with patch("shutil.disk_usage") as mock_disk:
        mock_disk.return_value = (100, 50, 50)
        mem_instance = MagicMock()
        mem_instance.percent = 50.0
        mock_psutil.virtual_memory.return_value = mem_instance

        monitor.perform_checks()

    # Router unavailable, Compactor error, Cron scheduler not running -> 3 events
    assert event_bus.publish.call_count == 3
    published_messages = [args[0][0].payload["message"] for args in event_bus.publish.call_args_list]
    
    assert any("ModelRouter is unavailable" in msg for msg in published_messages)
    assert any("Failed to check ContextCompactor" in msg for msg in published_messages)
    assert any("AutomationScheduler clock thread is not running" in msg for msg in published_messages)

def test_health_monitor_circuit_breaker_open():
    event_bus = MagicMock(spec=EventBus)
    orchestrator = MagicMock()
    
    # Subsystems healthy except circuit breaker is open
    router_mock = MagicMock()
    router_mock.get_status.return_value = {
        "ollama": {"state": "open"},
        "cloud": {"state": "closed"},
        "quota": {}
    }
    orchestrator.router = router_mock
    orchestrator.compactor.get_status.return_value = {}
    orchestrator.checkpoint.get_status.return_value = {}
    cron_mock = MagicMock()
    cron_mock.get_status.return_value = {"scheduler_running": True}
    guard_mock = MagicMock()
    guard_mock.get_status.return_value = {}

    monitor = StuartHealthMonitor(
        event_bus=event_bus,
        orchestrator=orchestrator,
        cron_manager=cron_mock,
        file_access_guard=guard_mock,
        check_interval=10
    )

    with patch("shutil.disk_usage") as mock_disk:
        mock_disk.return_value = (100, 50, 50)
        mem_instance = MagicMock()
        mem_instance.percent = 50.0
        mock_psutil.virtual_memory.return_value = mem_instance

        monitor.perform_checks()

    # Ollama circuit breaker open -> 1 event
    assert event_bus.publish.call_count == 1
    published_event = event_bus.publish.call_args[0][0]
    assert published_event.event_type == EventType.HEALTH_CHECK_FAILED.value
    assert published_event.severity == EventSeverity.FLASH
    assert "Ollama circuit breaker is OPEN" in published_event.payload["message"]
