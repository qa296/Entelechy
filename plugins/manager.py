"""Plugin lifecycle manager."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from plugins.registry import PluginRegistry, plugin_registry

if TYPE_CHECKING:
    from plugins.base_plugin import BasePlugin


class PluginManager:
    """Manages plugin lifecycle: activation, deactivation, tool aggregation."""

    def __init__(self, plugins_dir: Path, registry: PluginRegistry | None = None):
        self.plugins_dir = Path(plugins_dir)
        self.registry = registry or plugin_registry
        self.active_plugins: dict[str, BasePlugin] = {}

    async def discover_and_activate_all(self):
        """Discover all plugins and activate them."""
        self.registry.discover_and_load(self.plugins_dir)
        for name in self.registry.list_plugins():
            await self.activate_plugin(name)

    async def activate_plugin(self, plugin_name: str):
        """Activate a plugin by name."""
        if plugin_name in self.active_plugins:
            logger.debug(f"Plugin already active: {plugin_name}")
            return

        cls = self.registry.get_plugin_class(plugin_name)
        if cls is None:
            logger.warning(f"Plugin class not found: {plugin_name}")
            return

        try:
            instance = cls(context={})
            await instance.initialize()
            self.active_plugins[plugin_name] = instance
            logger.info(f"Activated plugin: {plugin_name}")
        except Exception as e:
            logger.error(f"Failed to activate plugin {plugin_name}: {e}")

    async def deactivate_plugin(self, plugin_name: str):
        """Deactivate a plugin by name."""
        if plugin_name not in self.active_plugins:
            return

        try:
            await self.active_plugins[plugin_name].terminate()
        except Exception as e:
            logger.warning(f"Error terminating plugin {plugin_name}: {e}")

        del self.active_plugins[plugin_name]
        logger.info(f"Deactivated plugin: {plugin_name}")

    def get_all_tools(self) -> list[dict]:
        """Aggregate tool definitions from all active plugins."""
        tools = []
        for plugin in self.active_plugins.values():
            tools.extend(plugin.get_tools())
        return tools

    async def execute_plugin_tool(self, tool_name: str, args: dict) -> str | None:
        """Try to execute a tool from any active plugin.

        Returns:
            The tool result string, or None if no plugin handles this tool.
        """
        for plugin in self.active_plugins.values():
            for tool_def in plugin.get_tools():
                if tool_def["name"] == tool_name:
                    return await plugin.execute_tool(tool_name, args)
        return None

    async def reload_plugins(self):
        """Deactivate all, re-discover, re-activate."""
        names = list(self.active_plugins.keys())
        for name in names:
            await self.deactivate_plugin(name)
        self.registry.plugin_classes.clear()
        self.registry.metadata.clear()
        await self.discover_and_activate_all()
