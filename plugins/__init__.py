"""Plugin system for extensible agent capabilities."""

from plugins.base_plugin import BasePlugin
from plugins.registry import PluginRegistry
from plugins.manager import PluginManager

__all__ = ["BasePlugin", "PluginRegistry", "PluginManager"]
