"""Bash tool - execute shell commands with safety checks."""

import asyncio
from pathlib import Path

from loguru import logger

DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "shutdown",
    "reboot",
    "> /dev/sd",
    "mkfs.",
    "dd if=",
    ":(){:|:&};:",
]


async def run_bash(command: str, workdir: Path | None = None, timeout: int = 120) -> str:
    """Execute a shell command.

    Args:
        command: The shell command to execute.
        workdir: Working directory (defaults to cwd).
        timeout: Timeout in seconds.

    Returns:
        Command output (stdout + stderr) or error message.
    """
    # Safety check
    cmd_lower = command.lower().strip()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd_lower:
            return f"Error: Dangerous command blocked (matched: {pattern})"

    logger.debug(f"Executing: {command}")

    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workdir) if workdir else None,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = (stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")).strip()

        if not output:
            return f"(no output, exit code: {proc.returncode})"

        # Truncate very long output
        if len(output) > 50000:
            output = output[:50000] + "\n\n... (output truncated at 50000 chars)"

        return output
    except asyncio.TimeoutError:
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"
