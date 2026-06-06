"""Agent loop - core LLM call → tool execution → result cycle."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from agent.context_manager import ContextManager
from agent.llm_client import BaseLLMClient
from agent.scheduler import SchedulerManager
from agent.todo_manager import TodoManager
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
    {
        "name": "todo_add",
        "description": (
            "Add a new task to the TODO list. Use when planning work or breaking down goals.\n"
            "You can add multiple tasks at once by calling this tool repeatedly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Clear, actionable task description",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "todo_list",
        "description": "View all TODO tasks and their status (pending / completed).",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "todo_complete",
        "description": (
            "Mark the current task as completed. You MUST call this when you "
            "have finished the current task. If you don't, the same task will "
            "be given to you again next turn."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Brief summary of what was accomplished",
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "schedule_add",
        "description": (
            "Add a timed schedule. When due, the task is injected into the "
            "TODO list head for immediate attention.\n\n"
            "Two modes:\n"
            "  1. Cron: provide 'cron' for periodic tasks (e.g. '0 9 * * *' for daily 9am).\n"
            "  2. One-shot: provide 'delay_minutes' for a one-time delayed reminder.\n"
            "Provide exactly one of 'cron' or 'delay_minutes'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Task description for when the schedule triggers",
                },
                "cron": {
                    "type": "string",
                    "description": "Cron expression (minute-level precision, e.g. '0 9 * * *')",
                },
                "delay_minutes": {
                    "type": "integer",
                    "description": "Delay in minutes for a one-shot reminder",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "schedule_list",
        "description": "View all scheduled tasks and their status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "schedule_remove",
        "description": "Remove a scheduled task by its ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "The schedule ID to remove",
                },
            },
            "required": ["id"],
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
        todo_manager: TodoManager | None = None,
        scheduler_manager: SchedulerManager | None = None,
    ):
        self.client = client
        self.system_prompt = system_prompt
        self.model = model
        self.max_tokens = max_tokens
        self.context_manager = context_manager
        self.workdir = workdir
        self.plugin_manager = plugin_manager
        self.core_context_provider = core_context_provider
        self.todo_manager = todo_manager
        self.scheduler_manager = scheduler_manager

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
            elif name == "todo_add":
                if not self.todo_manager:
                    return "Error: TODO manager not initialized"
                task = self.todo_manager.add(args["description"])
                await self.todo_manager.save()
                return f"Task added: [{task.id}] {task.description}"
            elif name == "todo_list":
                if not self.todo_manager:
                    return "Error: TODO manager not initialized"
                return self.todo_manager.format_status()
            elif name == "todo_complete":
                if not self.todo_manager:
                    return "Error: TODO manager not initialized"
                current = self.todo_manager.get_next()
                if not current:
                    return "No pending task to complete."
                summary = args.get("summary", "")
                self.todo_manager.complete(current.id)
                await self.todo_manager.save()
                logger.info(f"Task completed via todo_complete: [{current.id}] {current.description} — {summary}")

                # Check and trigger due schedules
                if self.scheduler_manager:
                    await self.scheduler_manager.check_and_trigger(self.todo_manager)

                return f"Task completed: {summary}"
            elif name == "schedule_add":
                if not self.scheduler_manager:
                    return "Error: Scheduler manager not initialized"
                description = args["description"]
                cron = args.get("cron")
                delay_minutes = args.get("delay_minutes")
                try:
                    schedule = self.scheduler_manager.add(
                        description, cron=cron, delay_minutes=delay_minutes,
                    )
                    await self.scheduler_manager.save()
                    return (
                        f"Schedule added: [{schedule.id}] {schedule.description}\n"
                        f"Type: {schedule.schedule_type}, "
                        f"{'cron: ' + schedule.cron if schedule.cron else 'run_at: ' + schedule.run_at}"
                    )
                except ValueError as e:
                    return f"Error: {e}"
            elif name == "schedule_list":
                if not self.scheduler_manager:
                    return "Error: Scheduler manager not initialized"
                return self.scheduler_manager.format_list()
            elif name == "schedule_remove":
                if not self.scheduler_manager:
                    return "Error: Scheduler manager not initialized"
                removed = self.scheduler_manager.remove(args["id"])
                if removed:
                    await self.scheduler_manager.save()
                    return f"Schedule removed: {args['id']}"
                return f"Schedule not found: {args['id']}"
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
