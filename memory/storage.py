"""Markdown file storage for memories with CORE.md + category folders."""

import aiofiles
from datetime import datetime
from pathlib import Path

import yaml


class MemoryStorage:
    """Memory storage: CORE.md + category folders."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.core_path = self.base_path / "CORE.md"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create necessary directories."""
        self.base_path.mkdir(parents=True, exist_ok=True)
        # Create CORE.md if it doesn't exist
        if not self.core_path.exists():
            self.core_path.write_text(
                "# 核心记忆（最高优先级）\n\n"
                "这个文件存放最重要的信息，每次LLM调用时都会注入。\n\n"
                "## 核心原则\n\n"
                "### 诚实原则\n\n"
                "**记忆诚实：**\n\n"
                "当你写入记忆时：\n"
                "- 只记录**真实发生**的事情\n"
                "\n"
            )

    async def store(self, content: str, category: str | None = None) -> Path:
        """Store a memory as a markdown file with frontmatter.

        Args:
            content: The markdown content to store.
            category: Optional category folder (e.g., "python", "ai", "project-x").

        Returns:
            The path to the created file.
        """
        if category:
            # Store in category folder
            category_path = self.base_path / category
            category_path.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = category_path / f"{timestamp}.md"
        else:
            # Store in root memory directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = self.base_path / f"{timestamp}.md"

        frontmatter = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
        }

        text = self._format_with_frontmatter(frontmatter, content)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(text)

        return file_path

    async def load_core(self) -> str:
        """Load the highest priority CORE.md memory."""
        if self.core_path.exists():
            return self.core_path.read_text(encoding="utf-8")
        return ""

    async def load_category(self, category: str) -> str:
        """Load all memories from a category folder."""
        category_path = self.base_path / category
        if not category_path.exists():
            return ""

        parts = []
        for md_file in sorted(category_path.rglob("*.md")):
            async with aiofiles.open(md_file, "r", encoding="utf-8") as f:
                parts.append(await f.read())
        return "\n\n---\n\n".join(parts)

    async def list_categories(self) -> list[str]:
        """List all category folders."""
        categories = []
        for item in self.base_path.iterdir():
            if item.is_dir() and item.name not in {".git", "__pycache__"}:
                categories.append(item.name)
        return sorted(categories)

    async def list_memories(self, category: str | None = None) -> list[dict]:
        """List all stored memories with their metadata."""
        results = []

        if category:
            # List specific category
            category_path = self.base_path / category
            if category_path.exists():
                for md_file in sorted(category_path.rglob("*.md")):
                    results.append(await self._load_memory_metadata(md_file, category))
        else:
            # List all categories + root memories
            # Core memory
            if self.core_path.exists():
                results.append({
                    "path": str(self.core_path),
                    "category": "CORE",
                    "is_core": True,
                    "preview": self.core_path.read_text()[:200],
                })

            # Category folders
            for cat in await self.list_categories():
                category_path = self.base_path / cat
                for md_file in sorted(category_path.rglob("*.md")):
                    results.append(await self._load_memory_metadata(md_file, cat))

        return results

    async def _load_memory_metadata(self, file_path: Path, category: str) -> dict:
        """Load metadata and preview from a memory file."""
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        frontmatter, body = self._parse_frontmatter(content)
        preview = body[:200] if len(body) > 200 else body

        return {
            "path": str(file_path),
            "category": category,
            "is_core": False,
            "metadata": frontmatter,
            "preview": preview,
        }

    @staticmethod
    def _format_with_frontmatter(frontmatter: dict, content: str) -> str:
        fm_text = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip()
        return f"---\n{fm_text}\n---\n\n{content}"

    @staticmethod
    def _parse_frontmatter(text: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown text."""
        if not text.startswith("---"):
            return {}, text
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            fm = {}
        body = parts[2].strip()
        return fm, body

    async def journal(self, content: str) -> Path:
        """Write a journal entry to today's daily journal file.

        Args:
            content: The journal entry content.

        Returns:
            The path to the journal file.
        """
        journal_dir = self.base_path / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        journal_path = journal_dir / f"{today}.md"

        # Append to existing journal or create new one
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"\n\n## {timestamp}\n\n{content}\n"

        if journal_path.exists():
            async with aiofiles.open(journal_path, "a", encoding="utf-8") as f:
                await f.write(entry)
        else:
            frontmatter = {
                "date": today,
                "type": "journal",
            }
            text = self._format_with_frontmatter(frontmatter, f"# Journal - {today}\n{entry}")
            async with aiofiles.open(journal_path, "w", encoding="utf-8") as f:
                await f.write(text)

        return journal_path

    async def load_recent_journal(self, days: int = 3) -> str:
        """Load recent journal entries.

        Args:
            days: Number of days to look back.

        Returns:
            Combined journal entries.
        """
        journal_dir = self.base_path / "journal"
        if not journal_dir.exists():
            return ""

        from datetime import timedelta

        parts = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            journal_path = journal_dir / f"{date.strftime('%Y-%m-%d')}.md"
            if journal_path.exists():
                async with aiofiles.open(journal_path, "r", encoding="utf-8") as f:
                    parts.append(await f.read())

        return "\n\n---\n\n".join(parts)
