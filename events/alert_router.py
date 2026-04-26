"""
Alert Router (Phase 11: Ecosystem & Extensibility)

Listens to the EventBus for high-severity events (FLASH, PRIORITY)
and routes them to the appropriate output channels, such as
native OS Desktop Notifications.
"""

import os
import subprocess
from typing import Dict, Any

from observability import get_logging_system
from events.event_bus import EventBus
from events.event_types import Event, EventSeverity


class AlertRouter:
    """
    Subscribes to all events and routes high-severity alerts
    to external channels like Desktop Notifications.
    """
    
    def __init__(self, event_bus: EventBus):
        self.logger = get_logging_system()
        self.event_bus = event_bus
        
        # Subscribe to all events, filtering internally
        self.event_bus.subscribe("*", self._handle_event)
        self.logger.info("AlertRouter initialized. Listening for high-severity events.")

    def _handle_event(self, event: Event):
        """Processes incoming events and routes based on severity."""
        if getattr(event, 'severity', EventSeverity.ROUTINE) == EventSeverity.ROUTINE:
            return

        title = f"Stuart {event.severity.value.upper()}: {event.event_type}"
        message = str(event.payload.get("message", "No message provided."))
        
        if event.severity == EventSeverity.FLASH:
            self._send_desktop_notification(title, message, is_critical=True)
            self.logger.warning(f"FLASH Alert routed: {title} - {message}")
            
        elif event.severity == EventSeverity.PRIORITY:
            self._send_desktop_notification(title, message, is_critical=False)
            self.logger.info(f"PRIORITY Alert routed: {title} - {message}")

    def _send_desktop_notification(self, title: str, message: str, is_critical: bool = False):
        """
        Sends a native Windows Toast notification using PowerShell.
        """
        if os.name != 'nt':
            self.logger.debug("Desktop notifications currently only supported on Windows.")
            return

        # Escape quotes
        title = title.replace("'", "''").replace('"', '""')
        message = message.replace("'", "''").replace('"', '""')
        
        icon = "SystemAsterisk" if is_critical else "SystemInformation"

        # Construct a simple PowerShell script to generate a generic balloon/toast
        ps_script = f"""
        [reflection.assembly]::loadwithpartialname("System.Windows.Forms") | Out-Null;
        $notify = New-Object system.windows.forms.notifyicon;
        $notify.icon = [System.Drawing.SystemIcons]::{icon};
        $notify.visible = $true;
        $notify.showballoontip(10, '{title}', '{message}', [system.windows.forms.tooltipicon]::Info);
        Start-Sleep -s 5;
        $notify.Dispose();
        """
        
        try:
            # Run asynchronously so it doesn't block the event bus thread
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception as e:
            self.logger.error(f"Failed to send desktop notification: {e}")
