"""Memory retrieval - search and recall from stored memories."""

import aiofiles
from pathlib import Path


class MemoryRetrieval:
    """Search and retrieve memories using keyword matching."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)

    async def search(self, query: str, max_results: int = 50) -> list[dict]:
        """Search memories by keyword matching across all priority folders.

        Args:
            query: Search query string. Matches against file content.
            max_results: Maximum number of results to return.

        Returns:
            List of matching memory dicts with path, score, and preview.
        """
        query_lower = query.lower()
        keywords = query_lower.split()
        results = []

        # Search across all markdown files
        for md_file in sorted(self.base_path.rglob("*.md"), reverse=True):
            try:
                async with aiofiles.open(md_file, "r", encoding="utf-8") as f:
                    content = await f.read()
            except (OSError, UnicodeDecodeError):
                continue

            content_lower = content.lower()
            score = sum(1 for kw in keywords if kw in content_lower)

            if score > 0:
                # Determine priority from path
                rel = md_file.relative_to(self.base_path)
                parts = rel.parts
                if "critical" in parts:
                    priority = "critical"
                    score += 2  # Boost critical memories
                elif "journals" in parts:
                    priority = "journal"
                else:
                    priority = "normal"

                # Extract a relevant snippet around the first match
                snippet = self._extract_snippet(content, keywords)

                results.append({
                    "path": str(md_file),
                    "priority": priority,
                    "score": score,
                    "snippet": snippet,
                })

        # Sort by score descending, then by path (most recent first)
        results.sort(key=lambda r: (-r["score"], r["path"]))
        return results[:max_results]

    @staticmethod
    def _extract_snippet(content: str, keywords: list[str], context_chars: int = 200) -> str:
        """Extract a text snippet around the first keyword match."""
        content_lower = content.lower()
        best_pos = -1

        for kw in keywords:
            pos = content_lower.find(kw)
            if pos >= 0:
                best_pos = pos
                break

        if best_pos < 0:
            return content[:context_chars]

        start = max(0, best_pos - context_chars // 2)
        end = min(len(content), best_pos + context_chars // 2)
        snippet = content[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet
