"""Memory manager - high-level interface for memory operations."""

from pathlib import Path

from memory.storage import MemoryStorage
from memory.retrieval import MemoryRetrieval


class MemoryManager:
    """High-level interface for storing and retrieving memories."""

    def __init__(self, base_path: Path):
        self.storage = MemoryStorage(base_path)
        self.retrieval = MemoryRetrieval(base_path)

    async def remember(self, content: str, category: str | None = None) -> str:
        """Store a new memory.

        Args:
            content: The content to remember.
            category: Optional category for organization.

        Returns:
            Confirmation message with the file path.
        """
        path = await self.storage.store(content, category=category)
        return f"Memory stored at {path}"

    async def recall(self, query: str, max_results: int = 50) -> str:
        """Search memories and return formatted results.

        Args:
            query: Search query.
            max_results: Maximum results to return.

        Returns:
            Formatted search results string.
        """
        results = await self.retrieval.search(query, max_results=max_results)
        if not results:
            return "No memories found matching the query."

        parts = [f"Found {len(results)} matching memories:\n"]
        for i, r in enumerate(results, 1):
            parts.append(
                f"{i}. [{r['category']}] {r['path']}\n"
                f"   {r['preview']}\n"
            )
        return "\n".join(parts)

    async def load_core(self) -> str:
        """Load the highest priority CORE.md memory."""
        return await self.storage.load_core()

    async def list_categories(self) -> list[str]:
        """List all category folders."""
        return await self.storage.list_categories()

    async def list_memories(self, category: str | None = None) -> list[dict]:
        """List all stored memories with their metadata."""
        return await self.storage.list_memories(category)

    async def journal(self, content: str) -> str:
        """Write a journal entry to today's daily journal file.

        Args:
            content: The journal entry content.

        Returns:
            Confirmation message with the file path.
        """
        path = await self.storage.journal(content)
        return f"Journal entry added to {path}"

    async def load_critical(self) -> str:
        """Load critical memories (CORE.md)."""
        return await self.storage.load_core()

    async def load_recent_journal(self, days: int = 3) -> str:
        """Load recent journal entries.

        Args:
            days: Number of days to look back.

        Returns:
            Combined journal entries.
        """
        return await self.storage.load_recent_journal(days)
