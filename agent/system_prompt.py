"""System prompt builder - constructs the system prompt from personality and context."""

from pathlib import Path

from loguru import logger


def build_system_prompt(personality_path: Path | str = "PERSONALITY.md") -> str:
    """Build the system prompt from the personality file and runtime context.

    Args:
        personality_path: Path to the PERSONALITY.md file.

    Returns:
        The complete system prompt string.
    """
    personality_path = Path(personality_path)

    # Load personality
    if personality_path.exists():
        personality = personality_path.read_text(encoding="utf-8")
    else:
        logger.warning(f"Personality file not found: {personality_path}")
        personality = "You are a helpful AI assistant."

    # Runtime context
    from datetime import datetime

    now = datetime.now()
    runtime_context = f"""
## Runtime Context

- Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}
- Timezone: Local

## Available Tools

You have access to the following tools:
- **bash**: Execute shell commands (ls, find, grep, git, python, etc.)
- **read_file**: Read file contents
- **write_file**: Write/create files
- **edit_file**: Replace exact text in files
- **remember**: Store important info to long-term memory (critical/normal priority)
- **recall**: Search and retrieve from long-term memory
- **journal**: Write to today's daily journal
- **create_plugin**: Create new plugin capabilities with Python code
- **browser**: Web automation (navigate, click, type, screenshot, extract)
- **todo_add**: Add a new task to your TODO list
- **todo_list**: View all TODO tasks and their status
- **todo_complete**: Mark the current task as completed (MUST call when done)

Plus any tools provided by active plugins.

## TODO Task System

You operate on a task-driven loop. The system gives you tasks one at a time.

### Rules:
1. When given a **[任务]**, work on it and call **todo_complete** when done
2. If you do NOT call todo_complete, the SAME task will appear again next turn
3. When told there are no pending tasks, plan new ones with **todo_add** (add 3-5 tasks)
4. You can also call **todo_add** at any time to add tasks you discover along the way

### Planning tips:
- Ensure **variety**: mix learning, exploration, creation, and reflection
- Break large goals into small, concrete tasks
- Do NOT repeat the same action consecutively

## Important Guidelines

- Do **NOT** repeat the same action consecutively. If something didn't work, try a different approach.
- Use **remember** with importance="critical" for truly important information
- Use **journal** to record daily activities and reflections
- Use **recall** before making decisions to check if you've learned something relevant
- Use **browser** for web interactions; sessions persist across calls
- Use **create_plugin** when you identify repeatable patterns worth automating
"""

    return personality + "\n\n" + runtime_context
