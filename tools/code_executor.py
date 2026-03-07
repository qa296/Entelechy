"""Code executor - allows the AI to create new plugins at runtime."""


import yaml
from loguru import logger

from plugins.manager import PluginManager


# Global plugin manager (set during initialization)
_plugin_manager: PluginManager | None = None


def set_plugin_manager(manager: PluginManager):
    """Set the global plugin manager instance."""
    global _plugin_manager
    _plugin_manager = manager


async def run_create_plugin(code: str, name: str, description: str) -> str:
    """Create a new plugin from code.

    The AI can call this to dynamically create new capabilities.

    Args:
        code: Python code for the plugin (must define a BasePlugin subclass).
        name: Plugin name (used as directory name).
        description: Human-readable description.

    Returns:
        Success or error message.
    """
    if _plugin_manager is None:
        return "Error: Plugin manager not initialized."

    plugins_dir = _plugin_manager.plugins_dir
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Write plugin.py
        plugin_file = plugin_dir / "plugin.py"
        plugin_file.write_text(code, encoding="utf-8")

        # Write metadata.yaml
        metadata = {
            "name": name,
            "description": description,
            "author": "AI Generated",
            "version": "1.0.0",
        }
        metadata_file = plugin_dir / "metadata.yaml"
        with open(metadata_file, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, allow_unicode=True)

        # Write __init__.py
        (plugin_dir / "__init__.py").write_text("", encoding="utf-8")

        # Reload and activate
        _plugin_manager.registry.discover_and_load(plugins_dir)
        await _plugin_manager.activate_plugin(name)

        logger.info(f"Plugin '{name}' created and activated")
        return f"Plugin '{name}' created and activated successfully at {plugin_dir}"
    except Exception as e:
        logger.error(f"Failed to create plugin '{name}': {e}")
        return f"Error creating plugin '{name}': {e}"
