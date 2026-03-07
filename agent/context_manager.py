"""Context manager - AI summary compaction for long conversations."""

from __future__ import annotations

from loguru import logger

from agent.llm_client import BaseLLMClient
from utils.token_counter import estimate_messages_tokens


class ContextManager:
    """Manage context window size using AI-powered summarization."""

    def __init__(
        self,
        client: BaseLLMClient,
        model: str,
        context_window: int = 200000,
        compact_threshold: float = 0.9,
    ):
        self.client = client
        self.model = model
        self.context_window = context_window
        self.compact_threshold = compact_threshold
        self.max_tokens = int(context_window * compact_threshold)

    async def maybe_compact(self, messages: list[dict]) -> list[dict]:
        """Check if messages exceed the threshold and compact if needed.

        Args:
            messages: Current message history.

        Returns:
            Possibly compacted message history.
        """
        tokens = estimate_messages_tokens(messages)

        if tokens < self.max_tokens:
            return messages

        logger.info(
            f"Context compaction triggered: {tokens} tokens "
            f"(threshold: {self.max_tokens})"
        )

        return await self._compact(messages)

    async def _compact(self, messages: list[dict]) -> list[dict]:
        """Compact messages by summarizing older ones.

        Strategy:
        1. Split messages into two halves
        2. Summarize the first half using the LLM
        3. Keep the second half intact
        4. Prepend the summary as the first message
        """
        if len(messages) <= 2:
            return messages

        # Find the split point — keep at least the last 30% of messages intact
        keep_count = max(2, len(messages) * 3 // 10)
        to_summarize = messages[:-keep_count]
        to_keep = messages[-keep_count:]

        if not to_summarize:
            return messages

        # Build the summary
        summary = await self._summarize_messages(to_summarize)

        # Assemble new message list with summary prepended
        summary_message = {
            "role": "user",
            "content": (
                f"[Context Summary - Previous conversation compressed]\n\n"
                f"{summary}\n\n"
                f"[End of Summary - Recent conversation follows]"
            ),
        }

        compacted = [summary_message] + to_keep

        new_tokens = estimate_messages_tokens(compacted)
        logger.info(
            f"Compacted: {len(messages)} -> {len(compacted)} messages, "
            f"{estimate_messages_tokens(messages)} -> {new_tokens} tokens"
        )

        # If still over budget, compact again recursively
        if new_tokens > self.max_tokens and len(compacted) > 3:
            return await self._compact(compacted)

        return compacted

    async def _summarize_messages(self, messages: list[dict]) -> str:
        """Use the LLM to summarize a chunk of messages.

        Args:
            messages: Messages to summarize.

        Returns:
            Summary text.
        """
        # Format messages for summarization
        formatted_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Flatten content blocks
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            text_parts.append(
                                f"[Tool call: {block.get('name', '?')}({block.get('input', {})})]"
                            )
                        elif block.get("type") == "tool_result":
                            result_content = str(block.get("content", ""))
                            if len(result_content) > 500:
                                result_content = result_content[:500] + "..."
                            text_parts.append(f"[Tool result: {result_content}]")
                    else:
                        text_parts.append(str(block))
                content = "\n".join(text_parts)
            formatted_parts.append(f"**{role}**: {content}")

        conversation_text = "\n\n".join(formatted_parts)

        # Truncate if extremely long
        if len(conversation_text) > 100000:
            conversation_text = conversation_text[:100000] + "\n\n... (truncated)"

        try:
            response = await self.client.create_message(
                model=self.model,
                system_prompt=(
                    "You are a conversation summarizer. Create a concise but comprehensive "
                    "summary of the following conversation. Preserve:\n"
                    "- Key decisions made\n"
                    "- Important facts and information learned\n"
                    "- Open questions or pending tasks\n"
                    "- User preferences and constraints\n"
                    "- Tool actions taken and their results\n"
                    "- Any errors encountered and how they were resolved\n\n"
                    "Be thorough but concise. Use bullet points."
                ),
                messages=[
                    {
                        "role": "user",
                        "content": f"Summarize this conversation:\n\n{conversation_text}",
                    },
                ],
                tools=[],
                max_tokens=4000,
            )

            summary_parts: list[str] = []
            for block in response.content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str):
                        summary_parts.append(text)

            summary = "".join(summary_parts)

            return summary or "No summary generated."
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            # Fallback: create a basic summary
            return (
                f"[Summarization failed - {len(messages)} messages dropped]\n"
                f"Messages covered roles: "
                f"{', '.join(set(m.get('role', '?') for m in messages))}"
            )
