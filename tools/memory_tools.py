"""Memory tools - store and retrieve long-term memories."""

from memory.manager import MemoryManager


# Global memory manager instance (set during initialization)
_memory_manager: MemoryManager | None = None


def set_memory_manager(manager: MemoryManager):
    """Set the global memory manager instance."""
    global _memory_manager
    _memory_manager = manager


def _get_manager() -> MemoryManager:
    if _memory_manager is None:
        raise RuntimeError("Memory manager not initialized. Call set_memory_manager() first.")
    return _memory_manager


async def run_remember(content: str, category: str | None = None) -> str:
    """Store information to long-term memory.

    Args:
        content: The content to remember.
        category: Optional category (e.g., "python", "ai", "project-x").

    Returns:
        Confirmation message.
    """
    manager = _get_manager()
    return await manager.remember(content, category=category)


async def run_recall(query: str) -> str:
    """Search long-term memory.

    Args:
        query: Search query.

    Returns:
        Formatted search results.
    """
    manager = _get_manager()
    return await manager.recall(query)


async def run_journal(content: str) -> str:
    """Write a journal entry to today's daily journal.

    Args:
        content: The journal entry content.

    Returns:
        Confirmation message.
    """
    manager = _get_manager()
    return await manager.journal(content)
