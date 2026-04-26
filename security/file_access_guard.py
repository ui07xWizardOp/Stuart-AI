"""
File Access Guard (Phase 9B)

Inspired by QwenPaw's File Access Guard and ZeroClaw's strict sandboxing.

Blocks the agent from reading, writing, or executing files in dangerous
system paths. Provides a configurable blocklist + allowlist system.

Usage:
    guard = FileAccessGuard()
    guard.check_path("C:\\Windows\\System32\\config")  # raises PermissionError
    guard.check_path("C:\\Users\\me\\project\\data.txt")  # returns True
"""

import os
from typing import List, Set
from pathlib import Path

from observability import get_logging_system


# Default blocked path patterns (case-insensitive on Windows)
DEFAULT_BLOCKED_PATHS: List[str] = [
    # SSH / GPG keys
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/.gpg"),

    # Cloud credentials
    os.path.expanduser("~/.aws"),
    os.path.expanduser("~/.azure"),
    os.path.expanduser("~/.config/gcloud"),
    os.path.expanduser("~/.kube"),

    # Environment / secrets
    os.path.expanduser("~/.env"),
    os.path.expanduser("~/.bashrc"),
    os.path.expanduser("~/.zshrc"),
    os.path.expanduser("~/.profile"),
    os.path.expanduser("~/.netrc"),

    # Windows system directories
    "C:\\Windows\\System32",
    "C:\\Windows\\SysWOW64",
    "C:\\Windows\\security",
    "C:\\Windows\\Prefetch",

    # Program data
    "C:\\ProgramData",

    # Registry / system config
    os.path.expanduser("~/AppData/Local/Microsoft"),
    os.path.expanduser("~/AppData/Roaming/Microsoft/Credentials"),

    # Browser data (credential theft prevention)
    os.path.expanduser("~/AppData/Local/Google/Chrome/User Data"),
    os.path.expanduser("~/AppData/Local/Microsoft/Edge/User Data"),
    os.path.expanduser("~/AppData/Roaming/Mozilla/Firefox/Profiles"),
]

# Dangerous file extensions that should never be written
BLOCKED_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".ps1", ".vbs", ".wsf", ".scr",
    ".dll", ".sys", ".msi", ".reg", ".com",
}


class FileAccessGuard:
    """Pre-execution security layer that validates file paths before agent interaction.

    Inspired by QwenPaw's File Access Guard and ZeroClaw's strict sandboxing.
    Blocks the agent from reading, writing, or executing files in dangerous
    system paths. Provides a configurable blocklist + allowlist system.

    Attributes:
        _blocked (Set[str]): Normalized set of paths that the agent is forbidden to access.
        _allowed (Set[str]): Normalized set of paths that explicitly bypass the blocklist.
        _block_extensions (bool): Whether to enforce the BLOCKED_EXTENSIONS policy.
    """

    def __init__(
        self,
        blocked_paths: List[str] = None,
        allowed_paths: List[str] = None,
        block_dangerous_extensions: bool = True,
    ):
        self.logger = get_logging_system()

        # Normalize all paths for consistent comparison
        self._blocked = set()
        for p in (blocked_paths or DEFAULT_BLOCKED_PATHS):
            normalized = self._normalize(p)
            if normalized:
                self._blocked.add(normalized)

        self._allowed = set()
        for p in (allowed_paths or []):
            normalized = self._normalize(p)
            if normalized:
                self._allowed.add(normalized)

        self._block_extensions = block_dangerous_extensions

        self.logger.info(
            f"FileAccessGuard initialized: {len(self._blocked)} blocked paths, "
            f"{len(self._allowed)} allowed paths (Phase 9B)."
        )

    def check_path(self, path: str, operation: str = "access") -> bool:
        """Validates a file path against the security blocklist and extension policy.

        Performs full path normalization (realpath) to prevent directory traversal
        attacks and compares against the internal DEFAULT_BLOCKED_PATHS set.

        Args:
            path (str): The raw file or directory path string to validate.
            operation (str): The intended file operation ("read", "write", "execute", "access").

        Returns:
            bool: True if the path is safe to access.

        Raises:
            PermissionError: If the path is blocked by the global security policy or could not be resolved.
            ValueError: If the file extension is dangerous for "write" or "execute" operations.
        """
        normalized = self._normalize(path)
        if not normalized:
            # Cannot normalize → reject as suspicious
            raise PermissionError(
                f"🛡️ FileAccessGuard: Path '{path}' could not be resolved. "
                f"Operation '{operation}' DENIED."
            )

        # Check allowlist first (explicit allows override blocks)
        for allowed in self._allowed:
            if normalized.startswith(allowed):
                return True

        # Check blocklist
        for blocked in self._blocked:
            if normalized.startswith(blocked):
                self.logger.warning(
                    f"🛡️ BLOCKED: Agent attempted to {operation} '{path}' "
                    f"(matches blocked path: {blocked})"
                )
                raise PermissionError(
                    f"🛡️ FileAccessGuard: Access to '{path}' is DENIED. "
                    f"This path is in the security blocklist. "
                    f"Operation: {operation}"
                )

        # Check dangerous extensions for write operations
        if operation in ("write", "execute") and self._block_extensions:
            ext = Path(path).suffix.lower()
            if ext in BLOCKED_EXTENSIONS:
                self.logger.warning(
                    f"🛡️ BLOCKED: Agent attempted to {operation} file with "
                    f"dangerous extension '{ext}': {path}"
                )
                raise PermissionError(
                    f"🛡️ FileAccessGuard: Writing/executing files with extension "
                    f"'{ext}' is DENIED for security. Path: {path}"
                )

        return True

    def is_safe(self, path: str, operation: str = "access") -> bool:
        """Non-throwing version of check_path. Returns True/False."""
        try:
            return self.check_path(path, operation)
        except PermissionError:
            return False

    def add_blocked_path(self, path: str):
        """Dynamically add a path to the blocklist."""
        normalized = self._normalize(path)
        if normalized:
            self._blocked.add(normalized)
            self.logger.info(f"Added to blocklist: {normalized}")

    def add_allowed_path(self, path: str):
        """Dynamically add a path to the allowlist."""
        normalized = self._normalize(path)
        if normalized:
            self._allowed.add(normalized)
            self.logger.info(f"Added to allowlist: {normalized}")

    def get_status(self) -> dict:
        """Return guard status for health endpoint."""
        return {
            "blocked_paths_count": len(self._blocked),
            "allowed_paths_count": len(self._allowed),
            "block_dangerous_extensions": self._block_extensions,
            "blocked_extensions": sorted(BLOCKED_EXTENSIONS),
        }

    @staticmethod
    def _normalize(path: str) -> str:
        """Normalize a path to absolute, resolved, lowercase (on Windows)."""
        try:
            resolved = str(Path(path).resolve())
            # Case-insensitive on Windows
            if os.name == 'nt':
                resolved = resolved.lower()
            return resolved
        except Exception:
            return ""
