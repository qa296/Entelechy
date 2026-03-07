"""Message history tracking and persistence."""

import json
from pathlib import Path

import aiofiles
from loguru import logger


class MessageHistory:
    """Track and persist conversation message history."""

    def __init__(self, persist_path: Path | None = None):
        self.messages: list[dict] = []
        self.persist_path = persist_path

    def append(self, message: dict):
        """Append a message to history."""
        self.messages.append(message)

    def get_messages(self) -> list[dict]:
        """Get all messages."""
        return self.messages

    def set_messages(self, messages: list[dict]):
        """Replace the entire message history."""
        self.messages = messages

    def clear(self):
        """Clear all messages."""
        self.messages = []

    async def save(self):
        """Persist messages to disk (if persist_path is set)."""
        if self.persist_path is None:
            return

        self.persist_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize messages — convert non-serializable content blocks to strings
        serializable = []
        for msg in self.messages:
            s_msg = {"role": msg["role"]}
            content = msg.get("content", "")
            if isinstance(content, str):
                s_msg["content"] = content
            elif isinstance(content, list):
                s_msg["content"] = [
                    block if isinstance(block, dict) else _content_block_to_dict(block)
                    for block in content
                ]
            else:
                s_msg["content"] = str(content)
            serializable.append(s_msg)

        async with aiofiles.open(self.persist_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(serializable, ensure_ascii=False, indent=2))
        logger.debug(f"Saved {len(serializable)} messages to {self.persist_path}")

    async def load(self) -> bool:
        """Load messages from disk.

        Returns:
            True if messages were loaded, False otherwise.
        """
        if self.persist_path is None or not self.persist_path.exists():
            return False

        try:
            async with aiofiles.open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.loads(await f.read())
            self.messages = data
            logger.info(f"Loaded {len(data)} messages from {self.persist_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load message history: {e}")
            return False


def _content_block_to_dict(block) -> dict:
    """Convert an Anthropic SDK content block to a serializable dict."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if hasattr(block, "to_dict"):
        return block.to_dict()
    return {"type": "text", "text": str(block)}
