"""Agent loop - core LLM call → tool execution → result cycle."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from agent.context_manager import ContextManager
from agent.llm_client import BaseLLMClient
from tools.bash_tool import run_bash
from tools.file_tools import run_read, run_write, run_edit
from tools.code_executor import run_create_plugin
from tools.browser_tool import run_browser
from tools.memory_tools import run_recall, run_remember


# Tool definitions sent to the API
TOOLS = [
    {
        "name": "bash",
        "description": "Execute a shell command. Use for: ls, find, grep, git, python, npm, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"}
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents. Returns UTF-8 text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "limit": {"type": "integer", "description": "Max lines to read (default: all)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in a file. Finds old_text and replaces with new_text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
                "old_text": {"type": "string", "description": "Exact text to find"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "remember",
        "description": (
            "Store information to long-term memory.\n"
            "Use for: important information, preferences, decisions, lessons learned.\n"
            "Organize by category (e.g., 'python', 'ai', 'project-x')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Information to store"},
                "category": {"type": "string", "description": "Category for organizing memories"},
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall",
        "description": "Search long-term memory for relevant information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "create_plugin",
        "description": (
            "Create a new plugin with Python code. The code must define a class "
            "inheriting from BasePlugin. Use when you identify repeatable patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python plugin code"},
                "name": {"type": "string", "description": "Plugin name"},
                "description": {"type": "string", "description": "Plugin description"},
            },
            "required": ["code", "name", "description"],
        },
    },
    {
        "name": "browser",
        "description": (
            "Browser automation. Actions: navigate, click, type, screenshot, extract.\n"
            "Maintains cookies and login state across calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "screenshot", "extract"],
                    "description": "Browser action to perform",
                },
                "url": {"type": "string", "description": "URL (for navigate)"},
                "selector": {"type": "string", "description": "CSS selector (for click/type)"},
                "text": {"type": "string", "description": "Text to type (for type action)"},
            },
            "required": ["action"],
        },
    },
]


class AgentLoop:
    """Core agent loop: LLM call → tool execution → result append → continue."""

    def __init__(
        self,
        client: BaseLLMClient,
        system_prompt: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 8000,
        context_manager: ContextManager | None = None,
        workdir: Path | None = None,
        plugin_manager=None,
        core_context_provider=None,
    ):
        self.client = client
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.context_manager = context_manager
        self.workdir = workdir
        self.plugin_manager = plugin_manager
        self.core_context_provider = core_context_provider

    async def run(self, messages: list[dict]) -> list[dict]:
        """Run the agent loop until the model stops calling tools.

        Args:
            messages: Conversation history (modified in place).

        Returns:
            Updated messages list.
        """
        while True:
            # Context compaction
            if self.context_manager:
                messages = await self.context_manager.maybe_compact(messages)

            # Gather all tools (built-in + plugin)
            all_tools = list(TOOLS)
            if self.plugin_manager:
                all_tools.extend(self.plugin_manager.get_all_tools())

            # Call LLM
            try:
                response = await self.client.create_message(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    messages=messages,
                    tools=all_tools,
                    max_tokens=self.max_tokens,
                )
            except Exception as e:
                logger.error(f"API error: {e}")
                messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"[API Error: {e}]"}],
                })
                break

            # Extract text and tool calls
            for block in response.content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if text:
                        logger.info(f"Assistant: {text[:200]}")

            # If no tool calls, conversation turn is done
            if response.stop_reason != "tool_use":
                messages.append({
                    "role": "assistant",
                    "content": response.content_blocks,
                })
                break

            # Execute tools and collect results
            results = []
            for tc in response.tool_calls:
                logger.info(f"Tool: {tc.name}({_preview_args(tc.input)})")
                output = await self._execute_tool(tc.name, tc.input)
                logger.debug(f"Result: {output[:200]}")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tc.id,
                    "content": output,
                })

            # Append assistant message and tool results
            messages.append({
                "role": "assistant",
                "content": response.content_blocks,
            })
            messages.append({
                "role": "user",
                "content": results,
            })

        return messages

    async def _execute_tool(self, name: str, args: dict) -> str:
        """Dispatch a tool call to the appropriate handler."""
        try:
            if name == "bash":
                return await run_bash(args["command"], workdir=self.workdir)
            elif name == "read_file":
                return await run_read(
                    args["path"], workdir=self.workdir, limit=args.get("limit")
                )
            elif name == "write_file":
                return await run_write(args["path"], args["content"], workdir=self.workdir)
            elif name == "edit_file":
                return await run_edit(
                    args["path"], args["old_text"], args["new_text"], workdir=self.workdir
                )
            elif name == "remember":
                category = args.get("category")
                if category is not None and not isinstance(category, str):
                    return "Error: category must be a string"
                return await run_remember(
                    args["content"],
                    category=category,
                )
            elif name == "recall":
                return await run_recall(args["query"])
            elif name == "create_plugin":
                return await run_create_plugin(
                    args["code"], args["name"], args["description"]
                )
            elif name == "browser":
                return await run_browser(
                    args["action"],
                    url=args.get("url", ""),
                    selector=args.get("selector", ""),
                    text=args.get("text", ""),
                )
            else:
                # Try plugin tools
                if self.plugin_manager:
                    result = await self.plugin_manager.execute_plugin_tool(name, args)
                    if result is not None:
                        return result
                return f"Unknown tool: {name}"
        except Exception as e:
            logger.error(f"Tool execution error ({name}): {e}")
            return f"Error executing {name}: {e}"


def _preview_args(args: dict, max_len: int = 100) -> str:
    """Create a short preview of tool arguments for logging."""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > max_len:
            s = s[:max_len] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)
