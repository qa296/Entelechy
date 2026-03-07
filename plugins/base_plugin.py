"""Base plugin class - all plugins must inherit from this."""

from __future__ import annotations


class BasePlugin:
    """Base class for all Entelechy plugins.

    Subclasses are automatically registered via __init_subclass__.
    """

    # Plugin metadata (override in subclasses)
    plugin_name: str = ""
    plugin_description: str = ""
    plugin_version: str = "1.0.0"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Lazy import to avoid circular dependency
        from plugins.registry import plugin_registry
        plugin_registry.register_plugin_class(cls)

    def __init__(self, context: dict | None = None):
        self.context = context or {}

    async def initialize(self):
        """Called when the plugin is activated. Override for setup logic."""
        pass

    async def terminate(self):
        """Called when the plugin is deactivated. Override for cleanup."""
        pass

    def get_tools(self) -> list[dict]:
        """Return tool definitions this plugin provides.

        Each tool dict should have: name, description, input_schema.
        Override in subclasses to expose tools.
        """
        return []

    async def execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool provided by this plugin.

        Args:
            tool_name: Name of the tool to execute.
            args: Tool arguments dict.

        Returns:
            String result of the tool execution.
        """
        return f"Tool '{tool_name}' not implemented in plugin '{self.plugin_name}'"
