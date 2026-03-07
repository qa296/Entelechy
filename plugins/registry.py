"""Plugin registry - auto-discovery and registration of plugins."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from loguru import logger

if TYPE_CHECKING:
    from plugins.base_plugin import BasePlugin


class PluginRegistry:
    """Registry for discovering and tracking plugin classes."""

    def __init__(self):
        self.plugin_classes: list[type[BasePlugin]] = []
        self.metadata: dict[str, dict] = {}

    def register_plugin_class(self, cls: type[BasePlugin]):
        """Register a plugin class (called automatically by __init_subclass__)."""
        if cls not in self.plugin_classes:
            self.plugin_classes.append(cls)
            name = getattr(cls, "plugin_name", "") or cls.__name__
            logger.debug(f"Registered plugin class: {name}")

    def discover_and_load(self, plugins_dir: Path):
        """Discover and import plugins from a directory.

        Each plugin is a subdirectory containing:
          - metadata.yaml: Plugin metadata
          - plugin.py: Plugin module with a BasePlugin subclass
        """
        plugins_dir = Path(plugins_dir)
        if not plugins_dir.exists():
            logger.warning(f"Plugins directory does not exist: {plugins_dir}")
            return

        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue

            metadata_file = plugin_dir / "metadata.yaml"
            plugin_file = plugin_dir / "plugin.py"

            if not plugin_file.exists():
                continue

            # Load metadata
            metadata = {}
            if metadata_file.exists():
                try:
                    with open(metadata_file, "r", encoding="utf-8") as f:
                        metadata = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.warning(f"Failed to load metadata for {plugin_dir.name}: {e}")

            plugin_name = metadata.get("name", plugin_dir.name)
            self.metadata[plugin_name] = metadata

            # Import the plugin module
            try:
                self._import_plugin(plugin_dir.name, plugin_file)
                logger.info(f"Loaded plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_name}: {e}")

    def _import_plugin(self, name: str, plugin_file: Path):
        """Import a plugin module, triggering __init_subclass__ registration."""
        module_name = f"plugins._loaded.{name}"

        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {plugin_file}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

    def get_plugin_class(self, name: str) -> type[BasePlugin] | None:
        """Get a plugin class by name."""
        for cls in self.plugin_classes:
            cls_name = getattr(cls, "plugin_name", "") or cls.__name__
            if cls_name == name:
                return cls
        return None

    def list_plugins(self) -> list[str]:
        """List all registered plugin names."""
        names = []
        for cls in self.plugin_classes:
            names.append(getattr(cls, "plugin_name", "") or cls.__name__)
        return names


# Global registry instance
plugin_registry = PluginRegistry()
