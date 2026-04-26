"""
Obsidian Sync Layer (Task 17.1)

Provides the file-system bridge to an Obsidian Markdown Vault.
Parses existing .md files and uses Watchdog to listen for live edits.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from observability import get_logging_system

class MarkdownDocument:
    def __init__(self, filepath: str, content: str, frontmatter: Dict[str, Any]):
        self.filepath = filepath
        self.content = content
        self.frontmatter = frontmatter

class VaultHandler(FileSystemEventHandler):
    def __init__(self, sync_callback: Callable[[str], None]):
        self.sync_callback = sync_callback
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            self.sync_callback(event.src_path)
            
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            self.sync_callback(event.src_path)

class ObsidianVaultSynchronizer:
    
    def __init__(self, vault_path: str):
        self.logger = get_logging_system()
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        self.observer = None
        self._sync_callback = None
        
        self.logger.info(f"Obsidian Synchronizer bound to {self.vault_path}")

    def _parse_markdown(self, filepath: str) -> MarkdownDocument:
        """Extracts YAML frontmatter and raw body content from a markdown file."""
        text = Path(filepath).read_text(encoding='utf-8', errors='ignore')
        
        frontmatter = {}
        body = text
        
        # Regex to detect YAML frontmatter wrapped in ---
        match = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if match:
            yaml_str = match.group(1)
            body = match.group(2)
            
            # Very crude YAML parse for simplicity
            for line in yaml_str.split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    frontmatter[key.strip()] = val.strip()
                    
        return MarkdownDocument(filepath=filepath, content=body.strip(), frontmatter=frontmatter)

    def read_all_documents(self) -> List[MarkdownDocument]:
        """Loops through the entire vault and reads all .md entries."""
        docs = []
        for root, dirs, files in os.walk(self.vault_path):
            # Skip hidden folders like .obsidian or .git
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.endswith('.md'):
                    full_path = os.path.join(root, file)
                    docs.append(self._parse_markdown(full_path))
                    
        return docs

    def watch_for_changes(self, on_change_callback: Callable[[str], None]) -> None:
        """Starts a background daemon thread that triggers when Obsidian files change."""
        if self.observer is not None:
            return
            
        self._sync_callback = on_change_callback
        event_handler = VaultHandler(on_change_callback)
        
        self.observer = Observer()
        self.observer.schedule(event_handler, str(self.vault_path), recursive=True)
        self.observer.start()
        self.logger.info("Watchdog started observing Obsidian Vault.")

    def stop_watching(self) -> None:
        """Kills the active watchdog daemon safely."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.logger.info("Watchdog stopped observing Obsidian Vault.")
