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

Plus any tools provided by active plugins.

## Important Guidelines

- Use **remember** with importance="critical" for truly important information
- Use **journal** to record daily activities and reflections
- Use **recall** before making decisions to check if you've learned something relevant
- Use **browser** for web interactions; sessions persist across calls
- Use **create_plugin** when you identify repeatable patterns worth automating
"""

    return personality + "\n\n" + runtime_context
