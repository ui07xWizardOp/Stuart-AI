import pytest
from core.system_mode_manager import SystemModeManager, SystemMode
from tools.base import ToolRiskLevel

def test_mode_transitions():
    manager = SystemModeManager()
    assert manager.current_mode == SystemMode.NORMAL
    
    manager.set_mode(SystemMode.SAFE_MODE)
    assert manager.current_mode == SystemMode.SAFE_MODE
    
    manager.set_mode(SystemMode.DEGRADED)
    assert manager.current_mode == SystemMode.DEGRADED

def test_tool_allowance_in_normal():
    manager = SystemModeManager()
    # Everything allowed in normal
    assert manager.is_tool_allowed(ToolRiskLevel.LOW) is True
    assert manager.is_tool_allowed(ToolRiskLevel.MEDIUM) is True
    assert manager.is_tool_allowed(ToolRiskLevel.HIGH) is True
    assert manager.is_tool_allowed(ToolRiskLevel.CRITICAL) is True

def test_tool_allowance_in_safe():
    manager = SystemModeManager()
    manager.set_mode(SystemMode.SAFE_MODE)
    
    assert manager.is_tool_allowed(ToolRiskLevel.LOW) is True
    assert manager.is_tool_allowed(ToolRiskLevel.MEDIUM) is True
    assert manager.is_tool_allowed(ToolRiskLevel.HIGH) is False
    assert manager.is_tool_allowed(ToolRiskLevel.CRITICAL) is False

def test_tool_allowance_in_degraded():
    manager = SystemModeManager()
    manager.set_mode(SystemMode.DEGRADED)
    
    assert manager.is_tool_allowed(ToolRiskLevel.LOW) is True
    assert manager.is_tool_allowed(ToolRiskLevel.MEDIUM) is True
    assert manager.is_tool_allowed(ToolRiskLevel.HIGH) is True
    assert manager.is_tool_allowed(ToolRiskLevel.CRITICAL) is False

def test_tool_allowance_in_emergency():
    manager = SystemModeManager()
    manager.set_mode(SystemMode.EMERGENCY)
    
    # Only LOW risk tools allowed (or maybe nothing, but our logic says LOW is safe)
    assert manager.is_tool_allowed(ToolRiskLevel.LOW) is True
    assert manager.is_tool_allowed(ToolRiskLevel.MEDIUM) is False
    assert manager.is_tool_allowed(ToolRiskLevel.HIGH) is False
