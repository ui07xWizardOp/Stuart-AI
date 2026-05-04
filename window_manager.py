# --- window_manager.py ---
# This module contains the core logic for managing the application's desktop window.
# Its primary responsibility is to apply the necessary settings to prevent the window
# from being captured by screen recording or sharing software (e.g., Teams, Zoom, OBS).
# This is the "stealth" feature of the Stuart application.

import os
import ctypes
import ctypes.wintypes as wintypes
import webview
import time
import tkinter as tk
import platform
from typing import Optional
from threading import Thread
from pynput import keyboard

# --- Scroll Configuration ---
# Configurable via .env — controls Alt+Up/Down scroll behaviour
# SCROLL_SPEED_PX: pixels per scroll tick (higher = faster). Default: 200
# SCROLL_INTERVAL_MS: milliseconds between ticks while key is held. Default: 50
SCROLL_AMOUNT_PX = int(os.environ.get("SCROLL_SPEED_PX", "200"))
SCROLL_INTERVAL_MS = int(os.environ.get("SCROLL_INTERVAL_MS", "50"))

# --- Win32 API Constants ---
# These flags are used with the SetWindowDisplayAffinity function.
# WDA_EXCLUDEFROMCAPTURE is a comprehensive flag that prevents the window from being
# captured by most common methods, rendering it as a black rectangle in recordings.
WDA_EXCLUDEFROMCAPTURE = 0x00000011
SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNOACTIVATE = 4  # Show window without giving it focus - crucial for stealth

# --- Win32 Function Loading ---
# We use the ctypes library to load functions directly from user32.dll, a core
# Windows library for UI management. This gives us low-level control over the window.

# Load the user32 library
_user32 = ctypes.windll.user32

# Define the function signature for SetWindowDisplayAffinity
# This tells ctypes what kind of arguments the function expects (a window handle and a flag)
# and what it returns (a boolean indicating success).
_user32.SetWindowDisplayAffinity.restype  = wintypes.BOOL
_user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)

# Define the function signature for FindWindowW
# This is a fallback method to find a window by its title if the primary method fails.
_user32.FindWindowW.restype               = wintypes.HWND
_user32.FindWindowW.argtypes              = (wintypes.LPCWSTR, wintypes.LPCWSTR)

# Define function signatures for ShowWindow and IsWindowVisible
_user32.ShowWindow.argtypes = (wintypes.HWND, wintypes.INT)
_user32.ShowWindow.restype = wintypes.BOOL
_user32.IsWindowVisible.argtypes = (wintypes.HWND,)
_user32.IsWindowVisible.restype = wintypes.BOOL

# Screen sharing indicator detection constants
SCREEN_SHARE_INDICATORS = [
    # Generic Windows indicators
    "Screen sharing indicator",
    "You're sharing your screen",
    "Screen Share Notification", 
    "Screen Recording Indicator",
    "Sharing indicator",
    "Recording indicator",
    "You are sharing your screen",
    "Screen share active",
    "Recording in progress",
    
    # Browser-specific indicators
    "Chrome is sharing your screen",
    "Microsoft Edge is sharing your screen", 
    "Firefox is sharing your screen",
    "Safari is sharing your screen",
    "Opera is sharing your screen",
    "Brave is sharing your screen",
    "is sharing your screen",
    "wants to share your screen",
    "Screen capture in progress",
    "Display capture active",
    
    # Video conferencing platforms
    "Zoom is sharing your screen",
    "Microsoft Teams is sharing your screen",
    "Google Meet is sharing your screen",
    "Skype is sharing your screen",
    "Discord is sharing your screen",
    "Slack is sharing your screen",
    "WebEx is sharing your screen",
    "GoToMeeting is sharing your screen",
    "BlueJeans is sharing your screen",
    "Jitsi is sharing your screen",
    "BigBlueButton is sharing your screen",
    
    # Screen recording software
    "OBS is recording your screen",
    "OBS Studio is recording",
    "Camtasia is recording",
    "Bandicam is recording",
    "Fraps is recording",
    "XSplit is recording",
    "Streamlabs is recording",
    "Action! is recording",
    "Nvidia ShadowPlay",
    "AMD ReLive",
    "Windows Game Bar recording",
    "Xbox Game Bar recording",
    
    # Remote desktop and sharing tools
    "TeamViewer is sharing your screen",
    "AnyDesk is sharing your screen", 
    "Chrome Remote Desktop",
    "Windows Remote Desktop",
    "VNC is sharing your screen",
    "LogMeIn is sharing your screen",
    "Splashtop is sharing your screen",
    "Parsec is sharing your screen",
    
    # Generic patterns
    "sharing your desktop",
    "recording your desktop", 
    "capturing your screen",
    "desktop sharing active",
    "screen capture active",
    "display recording",
    "monitor sharing",
    "window sharing",
    "application sharing",
    "presentation mode active",
    
    # Notification variations
    "Screen share notification",
    "Recording notification", 
    "Capture notification",
    "Privacy indicator",
    "Camera and microphone access",
    "Microphone access",
    "Screen access granted",
    
    # Development and testing tools
    "Selenium is controlling",
    "Puppeteer is controlling",
    "Playwright is controlling",
    "Automated testing in progress",
    "Browser automation active"
]

class WindowManager:
    def __init__(self):
        self.hwnd: Optional[int] = None
        self.is_windows = platform.system() == "Windows"
        self.current_transparency = 1.0
        self.is_ghost_mode = False
        self.screen_share_monitor_active = False
        self.hidden_screen_share_windows = set()
        
        # Continuous scrolling state
        self.scrolling_up = False
        self.scrolling_down = False
        self.scroll_thread = None
        self.hotkey_listener = None
        self.alt_pressed = False

        if self.is_windows:
            self._setup_win32_api_definitions()

    def _setup_win32_api_definitions(self):
        """Defines all necessary Win32 API functions, constants, and types."""
        # Constants
        self.GWL_EXSTYLE = -20
        self.WS_EX_LAYERED = 0x80000
        self.WS_EX_TOPMOST = 0x8
        self.WS_EX_TRANSPARENT = 0x20
        self.WS_EX_TOOLWINDOW = 0x80  # Added for taskbar hiding
        self.LWA_ALPHA = 0x2
        self.HWND_TOPMOST = -1
        self.HWND_NOTOPMOST = -2
        self.SWP_NOMOVE = 0x2
        self.SWP_NOSIZE = 0x1
        self.SWP_NOACTIVATE = 0x10  # Don't activate the window when moving
        self.SWP_NOZORDER = 0x4     # Don't change Z-order

        self.user32 = ctypes.windll.user32
        
        # Correctly define SetWindowLongPtr and GetWindowLongPtr for 32/64-bit
        is_64bit = platform.architecture()[0] == '64bit'
        if True:
            self.GetWindowLongPtr = self.user32.GetWindowLongPtrW
            self.SetWindowLongPtr = self.user32.SetWindowLongPtrW
        else:
            self.GetWindowLongPtr = getattr(self.user32, 'GetWindowLongPtrW', self.user32.GetWindowLongW)
            self.SetWindowLongPtr = getattr(self.user32, 'SetWindowLongPtrW', self.user32.SetWindowLongW)

        self.GetWindowLongPtr.restype = wintypes.LPARAM
        self.GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
        self.SetWindowLongPtr.restype = wintypes.LPARAM
        self.SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LPARAM]

        # SetLayeredWindowAttributes
        self.SetLayeredWindowAttributes = self.user32.SetLayeredWindowAttributes
        self.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, wintypes.BYTE, wintypes.DWORD]
        self.SetLayeredWindowAttributes.restype = wintypes.BOOL

        # SetWindowPos
        self.SetWindowPos = self.user32.SetWindowPos
        self.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.SetWindowPos.restype = wintypes.BOOL

        # EnumWindows for finding all windows
        self.EnumWindows = self.user32.EnumWindows
        self.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
        self.EnumWindows.restype = wintypes.BOOL

        # GetWindowText for getting window titles
        self.GetWindowTextW = self.user32.GetWindowTextW
        self.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.GetWindowTextW.restype = ctypes.c_int

        # GetClassName for getting window class names
        self.GetClassNameW = self.user32.GetClassNameW
        self.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.GetClassNameW.restype = ctypes.c_int

        # Define RECT structure for GetWindowRect
        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long),
                ("top", ctypes.c_long),
                ("right", ctypes.c_long),
                ("bottom", ctypes.c_long)
            ]
        
        self.RECT = RECT

        # GetWindowRect for getting window position and size
        self.GetWindowRect = self.user32.GetWindowRect
        self.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        self.GetWindowRect.restype = wintypes.BOOL
            
    def set_window_handle(self, window_handle: int):
        """Set the window handle for transparency operations"""
        self.hwnd = window_handle
        if self.is_windows and self.hwnd:
            self._enable_transparency()
        
    def _enable_transparency(self):
        """Enable transparency capability for the window"""
        if not self.is_windows or not self.hwnd:
            return False
            
        try:
            # Get current window style
            ex_style = self.GetWindowLongPtr(self.hwnd, self.GWL_EXSTYLE)
            
            # Add layered window style if not present
            if not (ex_style & self.WS_EX_LAYERED):
                new_style = ex_style | self.WS_EX_LAYERED
                self.SetWindowLongPtr(self.hwnd, self.GWL_EXSTYLE, new_style)
                
            return True
        except Exception as e:
            print(f"Error enabling transparency: {e}")
            return False
    
    def set_transparency(self, transparency: float) -> bool:
        """
        Set window transparency level
        Args:
            transparency: Float between 0.0 (fully transparent) and 1.0 (fully opaque)
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.is_windows or not self.hwnd:
            print("Transparency not supported on this platform or no window handle")
            return False
            
        # Clamp transparency value
        transparency = max(0.0, min(1.0, transparency))
        self.current_transparency = transparency
        
        try:
            # Convert to Windows alpha value (0-255)
            alpha = int(transparency * 255)
            
            # Apply transparency
            result = self.SetLayeredWindowAttributes(
                self.hwnd,
                0,  # colorkey (not used)
                alpha,  # alpha value
                self.LWA_ALPHA  # use alpha
            )
            
            if result:
                print(f"✅ Window transparency set to {transparency*100:.0f}%")
                return True
            else:
                print("❌ Failed to set window transparency")
                return False
                
        except Exception as e:
            print(f"❌ Error setting transparency: {e}")
            return False
    
    def get_transparency(self) -> float:
        """Get current transparency level"""
        return self.current_transparency
    
    def set_transparency_percent(self, percent: int) -> bool:
        """
        Set transparency as percentage
        Args:
            percent: Integer between 0 (fully transparent) and 100 (fully opaque)
        """
        transparency = percent / 100.0
        return self.set_transparency(transparency)
    
    def make_transparent(self) -> bool:
        """Make window 60% transparent (40% opacity) - good for interviews"""
        return self.set_transparency(0.4)
    
    def make_semi_transparent(self) -> bool:
        """Make window semi-transparent (70% opacity)"""
        return self.set_transparency(0.7)
    
    def make_opaque(self) -> bool:
        """Make window fully opaque"""
        return self.set_transparency(1.0)
    
    def find_window_by_title(self, title: str) -> bool:
        """Find a window by its exact title and current process ID."""
        if not self.is_windows:
            return False

        try:
            import ctypes
            from ctypes import wintypes
            import os
            
            # Use EnumWindows to find all windows, then filter by title and PID
            # This is more robust than FindWindowW which might return a window from another process
            found_hwnd = None
            my_pid = os.getpid()
            
            def enum_windows_proc(hwnd, lParam):
                nonlocal found_hwnd
                
                # Check window title
                length = self.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self.user32.GetWindowTextW(hwnd, buff, length + 1)

                    if buff.value == title:
                        # Found a window with the right title, now check the PID
                        pid = ctypes.c_ulong()
                        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                        if pid.value == my_pid:
                            found_hwnd = hwnd
                            return False # Stop enumerating

                return True

            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, ctypes.POINTER(ctypes.c_int))
            self.user32.EnumWindows(EnumWindowsProc(enum_windows_proc), 0)
            
            if found_hwnd:
                self.hwnd = found_hwnd
                self.title = title
                print(f"🎯 Found window '{title}' (PID: {my_pid}, HWND: {hex(found_hwnd)})")
                return found_hwnd
                
            return None

        except Exception as e:
            print(f"❌ Error finding window '{title}': {e}")
            return None    def hide_from_taskbar(self) -> bool:
        """Hide the window from the taskbar by setting WS_EX_TOOLWINDOW."""
        if not self.is_windows or not self.hwnd:
            print("Cannot hide from taskbar: Not on Windows or no window handle")
            return False
        try:
            # Get current extended style
            ex_style = self.GetWindowLongPtr(self.hwnd, self.GWL_EXSTYLE)
            # Add WS_EX_TOOLWINDOW and remove WS_EX_APPWINDOW (0x40000) if present
            new_style = (ex_style | self.WS_EX_TOOLWINDOW) & ~0x40000
            # Set the new style
            self.SetWindowLongPtr(self.hwnd, self.GWL_EXSTYLE, new_style)
            print("✅ Window hidden from taskbar")
            return True
        except Exception as e:
            print(f"❌ Error hiding from taskbar: {e}")
            return False

    def _start_hotkey_listener_thread(self):
        """The actual listener thread for global hotkeys."""
        print("🎧 Starting global hotkey listener thread...")

        def on_hide_show():
            self.toggle_visibility()
            return False

        def on_toggle_ghost():
            self.toggle_ghost_mode()
            return False

        def on_toggle_vision_mode():
            """Toggle vision mode (Alt+V)"""
            self.send_vision_command("toggle_vision_mode")
            return False

        def on_capture_screenshot():
            """Capture screenshot (Alt+S)"""
            self.send_vision_command("capture_screenshot")
            return False

        def on_process_screenshots():
            """Process screenshots with AI (Alt+P)"""
            self.send_vision_command("process_screenshots")
            return False

        def on_switch_primary():
            """Switch to primary AI preset (Alt+Q)"""
            self.send_preset_switch_signal("primary")
            return False

        def on_switch_secondary():
            """Switch to secondary AI preset (Alt+W)"""
            self.send_preset_switch_signal("secondary")
            return False

        def on_auto_select():
            """Auto-select best available AI preset (Alt+E)"""
            self.send_context_aware_command("auto_select_preset")
            return False

        def on_switch_vision_model():
            """Switch vision model (Alt+T)"""
            self.send_vision_switch_command("switch_vision_model")
            return False

        def on_transparency_transparent():
            """Set window to transparent (40% opacity) - Alt+1"""
            self.send_transparency_command("transparent")
            return False

        def on_transparency_semi():
            """Set window to semi-transparent (70% opacity) - Alt+2"""
            self.send_transparency_command("semi")
            return False

        def on_transparency_opaque():
            """Set window to opaque (100% opacity) - Alt+3"""
            self.send_transparency_command("opaque")
            return False

        def on_toggle_mic_mute():
            """Toggle microphone mute (Alt+M)"""
            self.send_audio_command("toggle_mic_mute")
            return False

        def on_toggle_universal_mute():
            """Toggle universal mute/pause (Alt+U)"""
            self.send_audio_command("toggle_universal_mute")
            return False

        def on_reset_screenshot_queue():
            """Reset/clear screenshot queue (Alt+R)"""
            self.send_vision_command("reset_screenshot_queue")
            return False

        def on_enable_proctoring_stealth():
            """Enable proctoring stealth mode (Alt+Shift+S)"""
            self.enable_proctoring_stealth_mode()
            return False

        def on_move_left():
            """Move window left (Alt+Left)"""
            self.move_window(-20, 0)
            return False

        def on_move_right():
            """Move window right (Alt+Right)"""
            self.move_window(20, 0)
            return False

        def on_move_up():
            """Move window up (Alt+I) - SWAPPED"""
            self.move_window(0, -20)
            return False

        def on_move_down():
            """Move window down (Alt+J) - SWAPPED"""
            self.move_window(0, 20)
            return False

        def on_reset_interview():
            """Reset interview session (Alt+O)"""
            self.send_interview_command("reset_interview")
            return False

        # Add single press scroll handlers for initial response
        def on_scroll_up_start():
            """Start continuous scroll up (Alt+Up)"""
            if not self.scrolling_up:
                self.scrolling_up = True
                self._start_continuous_scrolling()
                print("🔼 Starting continuous scroll up")
            return False

        def on_scroll_down_start():
            """Start continuous scroll down (Alt+Down)"""
            if not self.scrolling_down:
                self.scrolling_down = True
                self._start_continuous_scrolling()
                print("🔽 Starting continuous scroll down")
            return False

        # Create a separate listener for key releases to stop scrolling
        def start_release_listener():
            """Background thread to handle key releases for stopping continuous scroll"""
            import threading
            
            def on_key_release(key):
                try:
                    if key == keyboard.Key.up and self.scrolling_up:
                        self.scrolling_up = False
                        print("🛑 Stopped continuous scroll up")
                    elif key == keyboard.Key.down and self.scrolling_down:
                        self.scrolling_down = False
                        print("🛑 Stopped continuous scroll down")
                except:
                    pass

            def on_key_press(key):
                # We don't need to handle press here since GlobalHotKeys handles it
                pass

            release_listener = keyboard.Listener(
                on_press=on_key_press,
                on_release=on_key_release,
                suppress=False
            )
            release_listener.start()
            release_listener.join()

        # Start the release listener in background
        release_thread = Thread(target=start_release_listener, daemon=True)
        release_thread.start()

        # Regular hotkeys using the proven GlobalHotKeys approach
        hotkey_map = {
            '<ctrl>+<alt>+x': on_toggle_ghost,
            '<ctrl>+<alt>+z': on_hide_show,
            '<ctrl>+<alt>+v': on_toggle_vision_mode,  # Toggle vision mode
            '<ctrl>+<alt>+s': on_capture_screenshot,  # Capture screenshot (replaces screen share hide)
            '<ctrl>+<alt>+p': on_process_screenshots, # Process screenshots
            '<ctrl>+<alt>+r': on_reset_screenshot_queue, # Reset screenshot queue
            '<ctrl>+<alt>+q': on_switch_primary,      # Switch to primary preset
            '<ctrl>+<alt>+w': on_switch_secondary,    # Switch to secondary preset
            '<ctrl>+<alt>+e': on_auto_select,         # Auto-select best AI preset
            '<ctrl>+<alt>+t': on_switch_vision_model,   # Switch vision model
            '<ctrl>+<alt>+m': on_toggle_mic_mute,     # Toggle microphone mute
            '<ctrl>+<alt>+u': on_toggle_universal_mute, # Toggle universal mute (pause)
            '<ctrl>+<alt>+1': on_transparency_transparent,  # 40% opacity (transparent)
            '<ctrl>+<alt>+2': on_transparency_semi,         # 70% opacity (semi-transparent)
            '<ctrl>+<alt>+3': on_transparency_opaque,       # 100% opacity (opaque)
            '<ctrl>+<alt>+<shift>+s': on_enable_proctoring_stealth,  # Enable proctoring stealth mode
            '<ctrl>+<alt>+<left>': on_move_left,      # Move window left
            '<ctrl>+<alt>+<right>': on_move_right,    # Move window right
            '<ctrl>+<alt>+i': on_move_up,             # Move window up (SWAPPED)
            '<ctrl>+<alt>+j': on_move_down,           # Move window down (SWAPPED)
            '<ctrl>+<alt>+o': on_reset_interview,     # Reset interview session
            '<ctrl>+<alt>+<up>': on_scroll_up_start,  # Start continuous scroll up (NEW)
            '<ctrl>+<alt>+<down>': on_scroll_down_start,  # Start continuous scroll down (NEW)
        }
        
        with keyboard.GlobalHotKeys(hotkey_map) as h:
            h.join()

    def send_preset_switch_signal(self, preset_key: str):
        """Send preset switch signal to the application"""
        try:
            from datetime import datetime
            print(f"🔄 Global hotkey triggered: Switching to {preset_key} preset")
            self._write_command_file({
                "command": "switch_preset",
                "preset_key": preset_key,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending preset switch signal: {e}")

    def send_vision_command(self, command: str):
        """Send vision-related command to the application"""
        try:
            from datetime import datetime
            print(f"👁️ Global hotkey triggered: {command}")
            self._write_command_file({
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending vision command: {e}")

    def send_transparency_command(self, level: str):
        """Send transparency command to the application"""
        try:
            from datetime import datetime
            print(f"🔍 Global hotkey triggered: set_transparency_{level}")
            self._write_command_file({
                "command": "set_transparency",
                "level": level,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending transparency command: {e}")

    def send_audio_command(self, command: str):
        """Send audio-related command to the application"""
        try:
            from datetime import datetime
            print(f"🎤 Global hotkey triggered: {command}")
            self._write_command_file({
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending audio command: {e}")

    def send_context_aware_command(self, command: str):
        """Send command for context-aware actions like auto-selecting presets."""
        try:
            from datetime import datetime
            print(f"🔄 Global hotkey triggered: {command}")
            self._write_command_file({
                "command": "context_aware_action",
                "action": command,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending context-aware command: {e}")

    def send_vision_switch_command(self, command: str):
        """Send command to switch vision model"""
        try:
            from datetime import datetime
            print(f"👁️ Global hotkey triggered: {command}")
            self._write_command_file({
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending vision switch command: {e}")

    def send_interview_command(self, command: str):
        """Send interview-related command to the application"""
        try:
            from datetime import datetime
            print(f"🎤 Global hotkey triggered: {command}")
            self._write_command_file({
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending interview command: {e}")

    def send_scroll_command(self, direction: str):
        """Send scroll command to the application"""
        try:
            from datetime import datetime
            print(f"📜 Global hotkey triggered: scroll_{direction} ({SCROLL_AMOUNT_PX}px)")
            self._write_command_file({
                "command": "scroll",
                "direction": direction,
                "amount": SCROLL_AMOUNT_PX,
                "timestamp": datetime.now().isoformat(),
                "source": "global_hotkey"
            })
        except Exception as e:
            print(f"❌ Error sending scroll command: {e}")

    def _continuous_scroll_loop(self):
        """Continuous scrolling loop that runs while scroll keys are held"""
        import time
        while self.scrolling_up or self.scrolling_down:
            try:
                if self.scrolling_up:
                    self.send_scroll_command("up")
                elif self.scrolling_down:
                    self.send_scroll_command("down")
                
                # Wait between scroll commands for smooth scrolling
                time.sleep(SCROLL_INTERVAL_MS / 1000)
            except Exception as e:
                print(f"❌ Error in continuous scroll loop: {e}")
                break
        
        # Reset scroll thread when loop exits
        self.scroll_thread = None
        print("🔄 Continuous scroll loop ended")

    def _start_continuous_scrolling(self):
        """Start the continuous scrolling thread if not already running"""
        if self.scroll_thread is None or not self.scroll_thread.is_alive():
            self.scroll_thread = Thread(target=self._continuous_scroll_loop, daemon=True)
            self.scroll_thread.start()
            print("🔄 Started continuous scroll loop")

    def _write_command_file(self, command_data: dict):
        """Write command to temp file for inter-process communication"""
        import tempfile
        import json
        import os
        
        # Write command to a temp file that could be monitored
        temp_dir = tempfile.gettempdir()
        command_file = os.path.join(temp_dir, "stuart_command.json")
        
        with open(command_file, "w") as f:
            json.dump(command_data, f)
        
        print(f"📄 Command written to: {command_file}")

    def start_hotkey_listener(self):
        """Starts the global hotkey listener in a separate thread."""
        if not self.is_windows:
            print("Global hotkeys not supported on this platform.")
            return

        print("🚀 Initializing global hotkey listener...")
        print("   Alt+X: Toggle ghost mode (click-through)")
        print("   Alt+Z: Toggle window visibility (stealth - no focus)")
        print("   Alt+Left/Right Arrow: Move window left/right (stealth - no focus)")
        print("   Alt+I: Move window up (stealth - no focus)")
        print("   Alt+J: Move window down (stealth - no focus)")
        print("   Alt+Up Arrow: Continuous scroll up (hold for continuous)")
        print("   Alt+Down Arrow: Continuous scroll down (hold for continuous)")
        print("   Alt+V: Toggle vision mode")
        print("   Alt+S: Capture screenshot")
        print("   Alt+P: Process screenshots with AI")
        print("   Alt+R: Reset screenshot queue")
        print("   Alt+O: Reset interview session")
        print("   Alt+Q: Switch to primary AI preset")
        print("   Alt+W: Switch to secondary AI preset")
        print("   Alt+E: Auto-select best AI preset")
        print("   Alt+T: Switch vision model")
        print("   Alt+M: Toggle microphone mute")
        print("   Alt+U: Toggle universal mute (pause)")
        print("   Alt+1: Set transparent (40% opacity)")
        print("   Alt+2: Set semi-transparent (70% opacity)")
        print("   Alt+3: Set opaque (100% opacity)")
        print("   Alt+Shift+S: Enable proctoring stealth mode")
        
        # Ensure we have the handle before starting
        if not self.hwnd:
            if not self.find_window_by_title("Stuart"):
                 print("❌ Cannot start hotkey listener: Stuart window not found.")
                 return
        
        listener_thread = Thread(target=self._start_hotkey_listener_thread, daemon=True)
        listener_thread.start()

# Global instance
window_manager = WindowManager()

# Convenience functions for easy use
def set_app_transparency(transparency: float) -> bool:
    """Set app window transparency (0.0 to 1.0)"""
    return window_manager.set_transparency(transparency)

def set_app_transparency_percent(percent: int) -> bool:
    """Set app window transparency as percentage (0 to 100)"""
    return window_manager.set_transparency_percent(percent)

def make_app_transparent() -> bool:
    """Make app window 60% transparent (good for interviews)"""
    return window_manager.make_transparent()

def make_app_semi_transparent() -> bool:
    """Make app window semi-transparent"""
    return window_manager.make_semi_transparent()

def make_app_opaque() -> bool:
    """Make app window fully opaque"""
    return window_manager.make_opaque()

def find_stuart_window() -> bool:
    """Find and set Stuart window for transparency control"""
    hwnd = window_manager.find_window_by_title("Stuart")
    return hwnd is not None

def set_app_always_on_top(on_top: bool) -> bool:
    """Set app window to always stay on top"""
    return window_manager.set_always_on_top(on_top)

def get_transparency_info() -> dict:
    """Get current transparency information"""
    return window_manager.get_window_info()

def hide_screen_share_indicators() -> int:
    """Hide all screen sharing indicators and return count hidden"""
    return window_manager.hide_all_screen_share_indicators()

def start_screen_share_monitor():
    """Start automatically monitoring and hiding screen share indicators"""
    window_manager.start_screen_share_monitor()

def stop_screen_share_monitor():
    """Stop monitoring screen share indicators"""
    window_manager.stop_screen_share_monitor()

def enable_proctoring_stealth_mode():
    """Enable complete stealth mode for proctoring environments"""
    return window_manager.enable_proctoring_stealth_mode()

def move_window(dx: int, dy: int) -> bool:
    """Move window by specified offset without changing focus"""
    return window_manager.move_window(dx, dy)

def test_screen_share_detection():
    """Test function to show all currently detected screen sharing indicators"""
    print("🔍 Testing screen share indicator detection...")
    indicators = window_manager.find_screen_share_indicators()
    
    if not indicators:
        print("✅ No screen sharing indicators currently detected")
        return []
    
    print(f"🚨 Found {len(indicators)} screen sharing indicator(s):")
    for i, indicator in enumerate(indicators, 1):
        print(f"   {i}. Title: '{indicator['title']}'")
        print(f"      Class: '{indicator['class']}'") 
        print(f"      HWND: {hex(indicator['hwnd'])}")
        print()
    
    return indicators


def apply_capture_protection(window):
    hwnd = None
    print("🛡️ APPLYING SCREEN CAPTURE PROTECTION...")

    hwnd = getattr(window, '_hwnd', None)
    print(f"🔍 Method 1 (window._hwnd): {hex(hwnd) if hwnd else 'Not found'}")

    if not hwnd:
        import time
        import ctypes
        import os

        print("⚠️ Private attribute not found, trying robust process-based title search...")

        for attempt in range(25):
            time.sleep(0.1)
            temp_hwnd = _user32.FindWindowW(None, window.title)
            if temp_hwnd:
                pid = ctypes.c_ulong()
                _user32.GetWindowThreadProcessId(temp_hwnd, ctypes.byref(pid))
                if pid.value == os.getpid():
                    hwnd = temp_hwnd
                    print(f"🔍 Method 2 (Verified Title '{window.title}'): Found {hex(hwnd)}")
                    break
        
    if not hwnd:
        print("❌ CRITICAL: Could not obtain window handle! Screen capture protection NOT applied!")
        return False

    print(f"🛡️ Applying WDA_EXCLUDEFROMCAPTURE (0x{WDA_EXCLUDEFROMCAPTURE:08X}) to window {hex(hwnd)}...")
    success = _user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)

    if success:
        print(f"✅ SUCCESS: Window {hex(hwnd)} is now HIDDEN from screen capture!")
        window_manager.set_window_handle(hwnd)
        window_manager.hide_from_taskbar()
        window_manager.start_screen_share_monitor()
        verify_protection(hwnd)
        return True
    else:
        error_code = ctypes.GetLastError()
        print(f"❌ FAILED: SetWindowDisplayAffinity failed! Error Code: {error_code}")
        return False

def verify_protection(hwnd):
    """Verify that capture protection is actually applied"""
    try:
        # Try to get current display affinity (this is a read-only check)
        print(f"🔬 Verifying protection on window {hex(hwnd)}...")
        
        # Note: There's no direct way to read the current display affinity,
        # but we can check if the window handle is still valid
        is_window_valid = _user32.IsWindow(hwnd)
        if is_window_valid:
            print("✅ Window handle is valid - protection likely applied")
        else:
            print("❌ Window handle is invalid - protection may have failed")
            
    except Exception as e:
        print(f"⚠️ Could not verify protection: {e}")


# --- Example Usage (for testing this module directly) ---
if __name__ == '__main__':
    print("Running window_manager.py in test mode...")

    # Create a pywebview window for testing purposes
    test_window = webview.create_window(
        'Stuart Stealth Test',
        html='<h1>This window should be black in screen recordings.</h1>',
        width=800,
        height=600
    )

    # Hook our protection function to the 'shown' event. This is critical.
    # The 'shown' event fires after the window is created and visible, ensuring
    # that a window handle exists.
    test_window.events.shown += lambda: apply_capture_protection(test_window)

    # Start the GUI event loop
    webview.start()
# This function is not called if DEV_MODE in main.py is True
    print("--- Running window_manager.py in test mode ---")