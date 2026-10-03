"""System prompt builder - constructs the system prompt from personality and context."""

from pathlib import Path

from loguru import logger


def build_system_prompt(
    personality_path: Path | str = "PERSONALITY.md",
    tools: list[dict] | None = None,
) -> str:
    """Build the system prompt from the personality file and runtime context.

    Args:
        personality_path: Path to the PERSONALITY.md file.
        tools: Effective tool definitions (see agent_loop.build_tools). The tool
            listing is rendered from these rather than hand-written, so the
            prompt can never advertise a tool the API request omits.

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

    if tools is None:
        from agent.agent_loop import TOOLS

        tools = TOOLS

    tool_lines = "\n".join(
        f"- **{t['name']}**: {' '.join(t['description'].split())}"
        for t in tools
    )

    # Runtime context
    from datetime import datetime

    now = datetime.now()
    runtime_context = f"""
## Runtime Context

- Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}
- Timezone: Local

## Available Tools

You have access to the following tools:
{tool_lines}

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
- Use **recall** before making decisions to check if you've learned something relevant
- Only use the tools listed above; anything else does not exist for you.
"""

    return personality + "\n\n" + runtime_context
