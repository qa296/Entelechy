"""LLM Client abstraction layer - supports Anthropic and OpenAI-compatible APIs."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, cast

from loguru import logger


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def create_message(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse:
        """Create a message and return standardized response."""
        pass


class LLMResponse:
    """Standardized LLM response."""

    def __init__(
        self,
        content_blocks: list[dict[str, Any]],
        stop_reason: str,
        tool_calls: list[ToolCall] | None = None,
    ):
        self.content_blocks = content_blocks
        self.stop_reason = stop_reason
        self.tool_calls = tool_calls or []


class ToolCall:
    """Standardized tool call."""

    def __init__(self, id: str, name: str, input: dict[str, Any]):
        self.id = id
        self.name = name
        self.input = input


class AnthropicClient(BaseLLMClient):
    """Anthropic API client."""

    def __init__(self):
        import anthropic
        self._client = anthropic.AsyncAnthropic()

    async def create_message(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse:
        """Create message using Anthropic API."""
        response = await self._client.messages.create(
            model=model,
            system=system_prompt,
            messages=cast(Any, messages),
            tools=cast(Any, tools),
            max_tokens=max_tokens,
        )

        # Extract content blocks
        content_blocks = []
        tool_calls = []
        for block in response.content:
            if hasattr(block, "model_dump"):
                content_blocks.append(block.model_dump())
            elif isinstance(block, dict):
                content_blocks.append(block)
            else:
                content_blocks.append({"type": "text", "text": str(block)})

            if hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))

        return LLMResponse(
            content_blocks=content_blocks,
            stop_reason=str(response.stop_reason or "end_turn"),
            tool_calls=tool_calls,
        )


class OpenAIClient(BaseLLMClient):
    """OpenAI-compatible API client."""

    def __init__(self, base_url: str | None = None):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=base_url or os.environ.get("OPENAI_BASE_URL"),
        )

    async def create_message(
        self,
        model: str,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> LLMResponse:
        """Create message using OpenAI-compatible API."""
        # Convert Anthropic-style tools to OpenAI format
        openai_tools = self._convert_tools(tools)

        # Build message list with system prompt
        all_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Convert messages
        for msg in messages:
            converted = self._convert_message(msg)
            if converted:
                all_messages.append(converted)

        response = await self._client.chat.completions.create(
            model=model,
            messages=cast(Any, all_messages),
            tools=cast(Any, openai_tools if openai_tools else None),
            max_tokens=max_tokens,
        )

        choice = response.choices[0]

        # Extract content
        content_blocks = []
        tool_calls = []

        if choice.message.content:
            content_blocks.append({"type": "text", "text": choice.message.content})

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                import json
                if not hasattr(tc, "function"):
                    continue
                tc_any = cast(Any, tc)
                function = tc_any.function
                tool_calls.append(ToolCall(
                    id=tc_any.id,
                    name=function.name,
                    input=json.loads(function.arguments) if function.arguments else {},
                ))
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc_any.id,
                    "name": function.name,
                    "input": json.loads(function.arguments) if function.arguments else {},
                })

        stop_reason = "tool_use" if tool_calls else "end_turn"
        if choice.finish_reason == "length":
            stop_reason = "max_tokens"

        return LLMResponse(
            content_blocks=content_blocks,
            stop_reason=stop_reason,
            tool_calls=tool_calls,
        )

    def _convert_tools(self, anthropic_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic-style tools to OpenAI format."""
        openai_tools = []
        for tool in anthropic_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                }
            })
        return openai_tools

    def _convert_message(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        """Convert Anthropic-style message to OpenAI format."""
        role = msg.get("role")
        content = msg.get("content")

        if role == "user":
            if isinstance(content, str):
                return {"role": "user", "content": content}
            elif isinstance(content, list):
                # Handle tool results
                texts = []
                tool_results = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "tool_result":
                            tool_results.append(block)
                        elif block.get("type") == "text":
                            texts.append(block.get("text", ""))

                if tool_results:
                    # Convert tool results to OpenAI format
                    result_msg: dict[str, Any] = {"role": "tool", "content": ""}
                    for tr in tool_results:
                        result_msg["tool_call_id"] = tr.get("tool_use_id", "")
                        result_msg["content"] = tr.get("content", "")
                    return result_msg
                elif texts:
                    return {"role": "user", "content": "\n".join(texts)}

        elif role == "assistant":
            if isinstance(content, str):
                return {"role": "assistant", "content": content}
            elif isinstance(content, list):
                texts = []
                tool_uses = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            texts.append(block.get("text", ""))
                        elif block.get("type") == "tool_use":
                            tool_uses.append(block)

                result: dict[str, Any] = {"role": "assistant"}
                if texts:
                    result["content"] = "\n".join(texts)
                if tool_uses:
                    import json
                    result["tool_calls"] = [
                        {
                            "id": tu.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tu.get("name", ""),
                                "arguments": json.dumps(tu.get("input", {})),
                            }
                        }
                        for tu in tool_uses
                    ]
                return result

        return None


def create_client(provider: str = "anthropic", base_url: str | None = None) -> BaseLLMClient:
    """Factory function to create LLM client based on provider.

    Args:
        provider: "anthropic" or "openai"
        base_url: Base URL for OpenAI-compatible API (optional)

    Returns:
        LLM client instance.
    """
    if provider == "openai":
        logger.info("Using OpenAI-compatible API")
        return OpenAIClient(base_url=base_url)
    else:
        logger.info("Using Anthropic API")
        return AnthropicClient()
