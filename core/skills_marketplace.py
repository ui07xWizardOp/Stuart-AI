"""
Skills Marketplace (Phase 13: Tier 3 Differentiators)

Provides a plugin hub for discovering, installing, and removing community skills.
Skills are defined in a JSON registry and downloaded as single-file Python plugins
into the `plugins/` directory for hot-loading by the PluginManager.
"""

import os
import json
import shutil
from typing import Dict, Any, List, Optional

from observability import get_logging_system


class SkillsMarketplace:
    """
    Manages a registry of available skills (plugins) that can be
    installed into the Stuart agent at runtime.
    """

    REGISTRY_PATH = os.path.join("config", "skills_registry.json")

    def __init__(self, plugins_dir: str = "plugins"):
        self.logger = get_logging_system()
        self.plugins_dir = plugins_dir
        self.registry: List[Dict[str, Any]] = []
        self._load_registry()
        self.logger.info(f"SkillsMarketplace initialized with {len(self.registry)} skills in registry.")

    def _load_registry(self):
        """Load the skills registry from disk."""
        if not os.path.exists(self.REGISTRY_PATH):
            self.logger.warning(f"Skills registry not found at {self.REGISTRY_PATH}")
            self.registry = []
            return

        try:
            with open(self.REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.registry = data.get("skills", [])
        except Exception as e:
            self.logger.error(f"Failed to load skills registry: {e}")
            self.registry = []

    def list_available(self) -> List[Dict[str, Any]]:
        """Returns all skills in the registry with their install status."""
        results = []
        for skill in self.registry:
            installed = os.path.exists(os.path.join(self.plugins_dir, skill["filename"]))
            results.append({
                "name": skill["name"],
                "version": skill.get("version", "1.0.0"),
                "description": skill.get("description", "No description."),
                "author": skill.get("author", "Unknown"),
                "installed": installed
            })
        return results

    def install_skill(self, name: str) -> str:
        """
        Installs a skill by name from the registry.
        Currently supports local-source skills (bundled templates).
        Can be extended to fetch from GitHub raw URLs.
        """
        skill = self._find_skill(name)
        if not skill:
            return f"? Skill '{name}' not found in the registry."

        target_path = os.path.join(self.plugins_dir, skill["filename"])
        if os.path.exists(target_path):
            return f"?? Skill '{name}' is already installed."

        source = skill.get("source")
        if not source:
            return f"? Skill '{name}' has no source defined in the registry."

        # Source type: "bundled" means the content is inline in the registry
        if source.get("type") == "bundled":
            try:
                content = source["content"]
                os.makedirs(self.plugins_dir, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.logger.info(f"Installed skill '{name}' to {target_path}")
                return f"? Skill **{name}** installed successfully! Restart Stuart or hot-reload to activate."
            except Exception as e:
                return f"? Failed to install skill '{name}': {e}"

        # Source type: "url" ? fetch from remote
        elif source.get("type") == "url":
            try:
                import urllib.request
                url = source["url"]
                urllib.request.urlretrieve(url, target_path)
                self.logger.info(f"Downloaded skill '{name}' from {url}")
                return f"? Skill **{name}** downloaded and installed! Restart Stuart to activate."
            except Exception as e:
                return f"? Failed to download skill '{name}': {e}"

        return f"? Unknown source type for skill '{name}'."

    def remove_skill(self, name: str) -> str:
        """Removes an installed skill."""
        skill = self._find_skill(name)
        if not skill:
            return f"? Skill '{name}' not found in the registry."

        target_path = os.path.join(self.plugins_dir, skill["filename"])
        if not os.path.exists(target_path):
            return f"?? Skill '{name}' is not currently installed."

        try:
            os.remove(target_path)
            # Also remove __pycache__ for it
            cache_path = os.path.join(self.plugins_dir, "__pycache__")
            if os.path.exists(cache_path):
                module_name = skill["filename"][:-3]
                for cached in os.listdir(cache_path):
                    if cached.startswith(module_name):
                        os.remove(os.path.join(cache_path, cached))

            self.logger.info(f"Removed skill '{name}'")
            return f"? Skill **{name}** removed. It will be unloaded on next restart."
        except Exception as e:
            return f"? Failed to remove skill '{name}': {e}"

    def _find_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a skill by name (case-insensitive)."""
        name_lower = name.lower().strip()
        for skill in self.registry:
            if skill["name"].lower() == name_lower:
                return skill
        return None
