"""Token counting utilities using tiktoken."""

from typing import Any

import tiktoken


_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string."""
    return len(_get_encoder().encode(text))


def estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total tokens across a list of messages.

    Each message contributes its content tokens plus a small overhead
    for role and message framing (~4 tokens per message).
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content) + 4
        elif isinstance(content, list):
            # Content blocks (tool_use, tool_result, text)
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        total += estimate_tokens(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        total += estimate_tokens(str(block.get("input", {})))
                    elif block.get("type") == "tool_result":
                        total += estimate_tokens(str(block.get("content", "")))
                    else:
                        total += estimate_tokens(str(block))
                else:
                    # Anthropic SDK content block objects
                    total += estimate_tokens(str(block))
            total += 4
    return total
